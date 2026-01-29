import { v4 as uuidv4 } from 'uuid';
import { getLogger } from '../../config/logger.js';
import { getConfig } from '../../config/index.js';
import { getAgentManager } from '../../agent/agent-manager.js';
import { getSocketManager } from '../../socket/socket-manager.js';
import {
  createConversationInternal,
  createMessageInternal,
} from '../conversation/conversation.service.js';
import type { AgentMessageData } from '../../agent/types.js';

export async function sendMessage(
  message: string,
  userId: string,
  conversationId?: string | null
) {
  const logger = getLogger();
  const agentManager = getAgentManager();

  // Create conversation if needed
  if (!conversationId) {
    const conv = await createConversationInternal(userId, message.slice(0, 50));
    conversationId = conv.id;
  }

  // Create reply ID
  const replyId = uuidv4();

  // Save user message
  const userMessageId = uuidv4();
  await createMessageInternal(conversationId, 'user', message, userMessageId);

  // Broadcast replying state via Socket.IO
  try {
    const socketManager = getSocketManager();
    await socketManager.broadcastReplyingState({
      replying: true,
      conversation_id: conversationId,
    });
  } catch {
    // Socket not ready
  }

  // Get model config from TOML (simplified - use env or defaults)
  const config = getConfig();
  const studioUrl = `http://localhost:${config.port}`;

  // Build query JSON
  const query = JSON.stringify([{ type: 'text', text: message }]);

  // Spawn agent
  await agentManager.spawnAgent({
    conversationId,
    replyId,
    userId,
    query,
    studioUrl,
    llmProvider: config.llm.provider,
    modelName: config.llm.modelName,
    apiKey: config.llm.apiKey,
  });

  return {
    conversation_id: conversationId,
    reply_id: replyId,
    status: 'processing',
    timestamp: new Date().toISOString(),
  };
}

export interface SSEStreamOptions {
  message: string;
  userId: string;
  conversationId?: string | null;
  uploadedFiles?: string[];
}

export async function* sendMessageStreaming(
  options: SSEStreamOptions
): AsyncGenerator<Record<string, unknown>> {
  const { message, userId, uploadedFiles } = options;
  let { conversationId } = options;
  const logger = getLogger();
  const agentManager = getAgentManager();
  const config = getConfig();

  // Create conversation if needed
  if (!conversationId) {
    const conv = await createConversationInternal(userId, message.slice(0, 50));
    conversationId = conv.id;
  }

  const replyId = uuidv4();
  const userMessageId = uuidv4();

  // Save user message
  await createMessageInternal(conversationId, 'user', message, userMessageId);

  // Broadcast replying state
  try {
    const socketManager = getSocketManager();
    await socketManager.broadcastReplyingState({
      replying: true,
      conversation_id: conversationId,
    });
  } catch {
    // Socket not ready
  }

  // Yield start event
  yield {
    type: 'start',
    conversation_id: conversationId,
    reply_id: replyId,
  };

  // Build query JSON with context
  const queryBlocks: Array<{ type: string; text: string }> = [];

  if (uploadedFiles && uploadedFiles.length > 0) {
    const filesInfo = uploadedFiles.join(', ');
    queryBlocks.push({
      type: 'text',
      text: `[SYSTEM CONTEXT]\nuser_id: ${userId}\nconversation_id: ${conversationId}\nuploaded_files: ${filesInfo}\n[/SYSTEM CONTEXT]`,
    });
  } else {
    queryBlocks.push({
      type: 'text',
      text: `[SYSTEM CONTEXT]\nuser_id: ${userId}\nconversation_id: ${conversationId}\nuploaded_files: (none)\n[/SYSTEM CONTEXT]`,
    });
  }
  queryBlocks.push({ type: 'text', text: message });

  const query = JSON.stringify(queryBlocks);
  const studioUrl = `http://localhost:${config.port}`;

  // Spawn agent
  await agentManager.spawnAgent({
    conversationId,
    replyId,
    userId,
    query,
    studioUrl,
    llmProvider: config.llm.provider,
    modelName: config.llm.modelName,
    apiKey: config.llm.apiKey,
  });

  // Consume messages from agent manager via callback
  const messageQueue: Array<AgentMessageData | null> = [];
  let resolveWaiting: (() => void) | null = null;

  agentManager.registerSSECallback(replyId, (msg) => {
    messageQueue.push(msg);
    if (resolveWaiting) {
      resolveWaiting();
      resolveWaiting = null;
    }
  });

  try {
    while (true) {
      // Wait for message or timeout
      if (messageQueue.length === 0) {
        const timeoutPromise = new Promise<void>((resolve) => {
          const timer = setTimeout(resolve, 30000);
          resolveWaiting = () => {
            clearTimeout(timer);
            resolve();
          };
        });
        await timeoutPromise;
      }

      // Process all available messages
      while (messageQueue.length > 0) {
        const msg = messageQueue.shift()!;

        if (msg === null) {
          // End signal — yield done and exit
          yield {
            type: 'done',
            conversation_id: conversationId,
            timestamp: new Date().toISOString(),
          };
          return;
        }

        yield msg as unknown as Record<string, unknown>;
      }

      // If no messages came (timeout), check if agent still running
      if (messageQueue.length === 0 && !agentManager.isRunning(replyId)) {
        break;
      }

      // Send heartbeat on timeout
      if (messageQueue.length === 0) {
        yield { type: 'heartbeat' };
      }
    }

    // Agent stopped without sending end signal — yield done anyway
    yield {
      type: 'done',
      conversation_id: conversationId,
      timestamp: new Date().toISOString(),
    };
  } finally {
    agentManager.removeSSECallbacks(replyId);

    // Broadcast replying state off
    try {
      const socketManager = getSocketManager();
      await socketManager.broadcastReplyingState({
        replying: false,
        conversation_id: null,
      });
    } catch {
      // Socket not ready
    }
  }
}

export async function interruptAgent(replyId: string): Promise<boolean> {
  const agentManager = getAgentManager();
  const success = await agentManager.terminateAgent(replyId);

  if (success) {
    // Broadcast cancelled via Socket.IO
    try {
      const socketManager = getSocketManager();
      await socketManager.broadcastReplyingState({
        replying: false,
        conversation_id: null,
      });
      await socketManager.broadcastCancelled(replyId);
    } catch {
      // Socket not ready
    }
  }

  return success;
}

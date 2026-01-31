import { getAgentManager } from '../../agent/agent-manager.js';
import { getSocketManager } from '../../socket/socket-manager.js';
import { getLogger } from '../../config/logger.js';
import type { AgentMessageData, AgentEvent } from '../../agent/types.js';

/**
 * Handle new structured events payload from agent hook
 */
export async function handlePushEvents(replyId: string, events: AgentEvent[]): Promise<void> {
  const logger = getLogger();
  const agentManager = getAgentManager();

  logger.info({ replyId, eventCount: events.length }, 'Hook: received agent events');

  await agentManager.handleAgentEvents(replyId, events);

  // Broadcast via Socket.IO
  const reply = agentManager.getPendingReply(replyId);
  if (reply) {
    try {
      const socketManager = getSocketManager();
      await socketManager.broadcastMessage(reply.conversationId, replyId, { events });
    } catch (err) {
      logger.error({ err, replyId }, 'Failed to broadcast events via Socket.IO');
    }
  }
}

/**
 * Handle legacy msg payload from agent hook (backward compatible)
 */
export async function handlePushMessage(replyId: string, msg: Record<string, unknown>): Promise<void> {
  const logger = getLogger();
  const agentManager = getAgentManager();

  logger.info({ replyId }, 'Hook: received agent message (legacy)');

  await agentManager.handleAgentMessage(replyId, msg as AgentMessageData);

  // Also broadcast via Socket.IO
  const reply = agentManager.getPendingReply(replyId);
  if (reply) {
    try {
      const socketManager = getSocketManager();
      await socketManager.broadcastMessage(reply.conversationId, replyId, msg);
    } catch (err) {
      logger.error({ err, replyId }, 'Failed to broadcast message via Socket.IO');
    }
  }
}

export async function handlePushFinished(replyId: string): Promise<void> {
  const logger = getLogger();
  const agentManager = getAgentManager();

  logger.info({ replyId }, 'Hook: received agent finished signal');

  // Get reply data before finishing (for socket broadcast)
  const reply = agentManager.getPendingReply(replyId);

  await agentManager.handleAgentFinished(replyId);

  // Broadcast via Socket.IO
  if (reply) {
    try {
      const socketManager = getSocketManager();
      await socketManager.broadcastReplyingState({
        replying: false,
        conversation_id: null,
      });
      await socketManager.broadcastFinished(replyId);
    } catch (err) {
      logger.error({ err, replyId }, 'Failed to broadcast finished via Socket.IO');
    }
  }
}

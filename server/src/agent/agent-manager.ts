import type { ChildProcess } from 'child_process';
import { getRedis } from '../config/redis.js';
import { getPrisma } from '../config/database.js';
import { getLogger } from '../config/logger.js';
import { spawnAgentProcess } from './process-spawner.js';
import { CacheKeys, CacheTTL } from '../cache/cache-keys.js';
import type { SpawnAgentParams, PendingReply, AgentMessageData, AgentEvent } from './types.js';
import { getToolDisplayName, isToolHidden } from './tool-display.js';
import * as planService from '../modules/plan/plan.service.js';

const AGENT_REPLY_TTL = CacheTTL.agentReply;

export class AgentManager {
  /** Active child processes by replyId */
  private processes = new Map<string, ChildProcess>();
  /** Conversation → set of active replyIds */
  private conversationAgents = new Map<string, Set<string>>();
  /** Pending reply data by replyId */
  private pendingReplies = new Map<string, PendingReply>();
  /** SSE message queues by replyId (callbacks waiting for messages) */
  private messageCallbacks = new Map<string, Array<(msg: AgentMessageData | null) => void>>();
  /** Track replyIds that have already had testcases extracted */
  private extractedTestcaseReplies = new Set<string>();
  /** Track tool call IDs that belong to hidden tools (for filtering tool_result by id) */
  private hiddenToolCallIds = new Set<string>();

  private get logger() {
    return getLogger();
  }

  /**
   * Spawn a new agent subprocess
   */
  async spawnAgent(params: SpawnAgentParams): Promise<string> {
    const { replyId, conversationId, userId } = params;

    // Initialize pending reply
    this.pendingReplies.set(replyId, {
      conversationId,
      replyId,
      userId,
      messages: [],
      finished: false,
    });

    // Track conversation → agent mapping
    if (!this.conversationAgents.has(conversationId)) {
      this.conversationAgents.set(conversationId, new Set());
    }
    this.conversationAgents.get(conversationId)!.add(replyId);

    // Store agent state in Redis
    const redis = getRedis();
    try {
      await redis.setex(
        CacheKeys.agentReply(replyId),
        AGENT_REPLY_TTL,
        JSON.stringify({
          conversationId,
          replyId,
          userId,
          status: 'starting',
          startedAt: new Date().toISOString(),
        })
      );
    } catch (err) {
      this.logger.error({ err, replyId }, 'Failed to store agent state in Redis');
    }

    // Create AgentSession record in DB
    const prisma = getPrisma();
    try {
      await prisma.agentSession.create({
        data: {
          conversationId,
          userId,
          replyId,
          agentType: 'CHAT',
          status: 'STARTING',
        },
      });
    } catch (err) {
      this.logger.error({ err, replyId }, 'Failed to create AgentSession record');
    }

    // Spawn the process
    const child = spawnAgentProcess(params);
    this.processes.set(replyId, child);

    // Update status to RUNNING
    try {
      await prisma.agentSession.update({
        where: { replyId },
        data: { status: 'RUNNING', pid: child.pid ?? null },
      });
      await redis.setex(
        CacheKeys.agentReply(replyId),
        AGENT_REPLY_TTL,
        JSON.stringify({
          conversationId,
          replyId,
          userId,
          status: 'running',
          startedAt: new Date().toISOString(),
        })
      );
    } catch (err) {
      this.logger.error({ err, replyId }, 'Failed to update agent status');
    }

    // Handle process exit
    child.on('exit', async () => {
      this.processes.delete(replyId);
      const convAgents = this.conversationAgents.get(conversationId);
      if (convAgents) {
        convAgents.delete(replyId);
        if (convAgents.size === 0) {
          this.conversationAgents.delete(conversationId);
        }
      }
    });

    this.logger.info(
      { replyId, conversationId, pid: child.pid },
      'Agent process spawned'
    );

    return replyId;
  }

  /**
   * Handle incoming message from agent hook
   */
  async handleAgentMessage(replyId: string, msg: AgentMessageData): Promise<void> {
    const reply = this.pendingReplies.get(replyId);
    if (!reply) {
      this.logger.warn({ replyId }, 'No pending reply found for agent message');
      return;
    }

    // Parse content
    let textContent = '';
    let thinkingContent = '';
    const content = msg.content;

    if (Array.isArray(content)) {
      for (const block of content) {
        if (typeof block === 'object' && block !== null) {
          if (block.type === 'text') {
            textContent += block.text ?? '';
          } else if (block.type === 'thinking') {
            thinkingContent += block.thinking ?? '';
          }
        }
      }
    } else if (typeof content === 'string') {
      textContent = content;
    }

    // Accumulate content per message id
    const messageId = msg.id ?? '';
    const existingIdx = reply.messages.findIndex((m) => m.id === messageId && messageId !== '');

    if (existingIdx >= 0) {
      const existing = reply.messages[existingIdx];
      const accumulated = (existing._accumulated_content ?? '') + textContent;
      reply.messages[existingIdx] = {
        ...existing,
        _accumulated_content: accumulated,
        content: [{ type: 'text', text: accumulated }],
      };
    } else {
      reply.messages.push({
        ...msg,
        _accumulated_content: textContent,
      });
    }

    // Push to SSE queue
    if (thinkingContent) {
      this.pushToSSEQueue(replyId, { type: 'thinking', content: thinkingContent } as unknown as AgentMessageData);
    }
    if (textContent) {
      this.pushToSSEQueue(replyId, { type: 'chunk', content: textContent } as unknown as AgentMessageData);
    }

    // Also push raw msg for testcase extraction
    await this.extractAndPushTestcases(replyId, textContent);
  }

  /**
   * Handle structured events from the new agent hook format.
   *
   * - Text events: accumulated for DB storage, forwarded to SSE.
   * - Tool events: logged with original names, then filtered (hidden tools)
   *   and mapped (Chinese display names) before pushing to SSE.
   */
  async handleAgentEvents(replyId: string, events: AgentEvent[]): Promise<void> {
    const reply = this.pendingReplies.get(replyId);
    if (!reply) {
      this.logger.warn({ replyId }, 'No pending reply found for agent events');
      return;
    }

    for (const event of events) {
      if (event.type === 'text') {
        // Accumulate text content for DB storage
        const existing = reply.messages[0];
        if (existing) {
          const accumulated = (existing._accumulated_content ?? '') + event.content;
          reply.messages[0] = {
            ...existing,
            _accumulated_content: accumulated,
            content: [{ type: 'text', text: accumulated }],
          };
        } else {
          reply.messages.push({
            _accumulated_content: event.content,
            content: [{ type: 'text', text: event.content }],
            role: 'assistant',
          });
        }

        // Push text as chunk event to SSE (same format as before for text)
        this.pushToSSEQueue(replyId, {
          type: 'chunk',
          content: event.content,
        } as unknown as AgentMessageData);

        // Extract testcases from accumulated text
        const accumulatedText = reply.messages[0]?._accumulated_content ?? '';
        await this.extractAndPushTestcases(replyId, accumulatedText);
      } else if (event.type === 'thinking') {
        // Forward thinking content to SSE for display
        this.pushToSSEQueue(replyId, {
          type: 'thinking',
          content: event.content,
        } as unknown as AgentMessageData);
      } else if (event.type === 'tool_call') {
        // Skip hidden tools — do not push to frontend
        if (isToolHidden(event.name)) {
          this.hiddenToolCallIds.add(event.id);
          this.logger.info(
            { replyId, tool: event.name, toolId: event.id },
            'Tool call hidden from frontend'
          );
          continue;
        }
        // Map tool name to Chinese display name for frontend
        const displayEvent = {
          ...event,
          name: getToolDisplayName(event.name),
        };
        this.pushToSSEQueue(replyId, displayEvent as unknown as AgentMessageData);
      } else if (event.type === 'tool_result') {
        // Skip results for hidden tools (match by name or by tracked id)
        if (isToolHidden(event.name) || this.hiddenToolCallIds.has(event.id)) {
          continue;
        }
        const displayEvent = {
          ...event,
          name: getToolDisplayName(event.name),
        };
        this.pushToSSEQueue(replyId, displayEvent as unknown as AgentMessageData);
      } else if (event.type === 'coordinator_event') {
        // Persist coordinator events to database
        await this.handleCoordinatorEvent(replyId, event.event_type, event.data);

        // Forward coordinator events to frontend for plan card rendering
        this.pushToSSEQueue(replyId, {
          type: 'coordinator_event',
          event_type: event.event_type,
          data: event.data,
        } as unknown as AgentMessageData);
      }
    }
  }

  /**
   * Handle agent finished signal
   */
  async handleAgentFinished(replyId: string): Promise<void> {
    const reply = this.pendingReplies.get(replyId);
    const prisma = getPrisma();
    const redis = getRedis();

    if (reply) {
      reply.finished = true;

      // Save accumulated messages to database
      for (const msg of reply.messages) {
        const accumulated = msg._accumulated_content ?? '';
        if (accumulated) {
          const msgId = msg.id ?? undefined;
          try {
            await prisma.message.create({
              data: {
                ...(msgId ? { id: msgId } : {}),
                conversationId: reply.conversationId,
                role: 'assistant',
                content: accumulated,
              },
            });
          } catch (err) {
            // Message might already exist
            this.logger.warn({ err, replyId }, 'Failed to save agent message');
          }
        }
      }
    }

    // Send end signal to SSE queue
    this.pushToSSEQueue(replyId, null);

    // Update AgentSession
    try {
      await prisma.agentSession.update({
        where: { replyId },
        data: { status: 'COMPLETED', finishedAt: new Date() },
      });
    } catch (err) {
      this.logger.error({ err, replyId }, 'Failed to update AgentSession');
    }

    // Clean up Redis
    try {
      await redis.del(CacheKeys.agentReply(replyId));
    } catch {
      // Non-critical
    }

    // Clean up process reference
    const child = this.processes.get(replyId);
    if (child) {
      try {
        child.kill();
      } catch {
        // Already dead
      }
      this.processes.delete(replyId);
    }

    this.logger.info({ replyId }, 'Agent finished');
  }

  /**
   * Terminate agent by replyId
   */
  async terminateAgent(replyId: string): Promise<boolean> {
    const reply = this.pendingReplies.get(replyId);
    const child = this.processes.get(replyId);
    const prisma = getPrisma();

    if (!reply) {
      this.logger.warn({ replyId }, 'No pending reply to terminate');
      return false;
    }

    // Save accumulated messages before termination
    for (const msg of reply.messages) {
      const accumulated = msg._accumulated_content ?? '';
      if (accumulated) {
        const msgId = msg.id ?? undefined;
        try {
          await prisma.message.create({
            data: {
              ...(msgId ? { id: msgId } : {}),
              conversationId: reply.conversationId,
              role: 'assistant',
              content: accumulated,
            },
          });
        } catch {
          // Might already exist
        }
      }
    }

    // Kill process
    if (child) {
      try {
        child.kill('SIGTERM');
        // Force kill after 5 seconds
        setTimeout(() => {
          try {
            child.kill('SIGKILL');
          } catch {
            // Already dead
          }
        }, 5000);
      } catch {
        // Already dead
      }
      this.processes.delete(replyId);
    }

    reply.finished = true;
    reply.cancelled = true;

    // Push cancel event to SSE
    this.pushToSSEQueue(replyId, { type: 'cancelled', message: '用户终止了请求' } as unknown as AgentMessageData);
    this.pushToSSEQueue(replyId, null);

    // Update DB
    try {
      await prisma.agentSession.update({
        where: { replyId },
        data: { status: 'CANCELLED', finishedAt: new Date() },
      });
    } catch (err) {
      this.logger.error({ err, replyId }, 'Failed to update AgentSession on cancel');
    }

    this.logger.info({ replyId }, 'Agent terminated');
    return true;
  }

  /**
   * Terminate all agents for a conversation
   */
  async terminateConversation(conversationId: string): Promise<void> {
    const replyIds = this.conversationAgents.get(conversationId);
    if (!replyIds) return;

    for (const replyId of replyIds) {
      await this.terminateAgent(replyId);
    }
  }

  /**
   * Get active agent replyIds for a conversation
   */
  getConversationAgents(conversationId: string): string[] {
    const agents = this.conversationAgents.get(conversationId);
    return agents ? [...agents] : [];
  }

  /**
   * Check if a replyId is still running
   */
  isRunning(replyId: string): boolean {
    const child = this.processes.get(replyId);
    if (!child) return false;
    return child.exitCode === null && !child.killed;
  }

  /**
   * Get pending reply data
   */
  getPendingReply(replyId: string): PendingReply | undefined {
    return this.pendingReplies.get(replyId);
  }

  /**
   * Register an SSE message callback for a replyId
   */
  registerSSECallback(replyId: string, callback: (msg: AgentMessageData | null) => void): void {
    if (!this.messageCallbacks.has(replyId)) {
      this.messageCallbacks.set(replyId, []);
    }
    this.messageCallbacks.get(replyId)!.push(callback);
  }

  /**
   * Remove SSE callbacks for a replyId
   */
  removeSSECallbacks(replyId: string): void {
    this.messageCallbacks.delete(replyId);
  }

  /**
   * Push message to SSE queue callbacks
   */
  pushToSSEQueue(replyId: string, msg: AgentMessageData | null): void {
    const callbacks = this.messageCallbacks.get(replyId);
    if (callbacks) {
      for (const cb of callbacks) {
        cb(msg);
      }
    }
  }

  /**
   * Handle coordinator events and persist to database
   */
  private async handleCoordinatorEvent(
    replyId: string,
    eventType: string,
    data: Record<string, unknown>
  ): Promise<void> {
    const reply = this.pendingReplies.get(replyId);
    if (!reply) {
      this.logger.warn({ replyId, eventType }, 'No pending reply for coordinator event');
      return;
    }

    const { conversationId } = reply;

    try {
      switch (eventType) {
        case 'plan_created': {
          // 创建或更新计划
          // Python 发送: { task_id, phases (count), plan (full plan dict) }
          // plan.to_dict() 包含 objective, phases, completion_criteria 等
          const planData = (data.plan as Record<string, unknown>) ?? {};
          const objective = (planData.objective as string) ?? '';

          await planService.upsertPlan(conversationId, {
            objective,
            plan: planData,
            status: 'running',
          });
          break;
        }

        case 'phase_started': {
          // 更新活跃 phase
          // Python 发送: { task_id, phase (1-indexed), name, parallel, workers }
          const phaseNumber = (data.phase as number) ?? 1;
          await planService.updatePhaseStarted(conversationId, phaseNumber);
          break;
        }

        case 'phase_completed': {
          // 标记 phase 完成
          // Python 发送: { task_id, phase (1-indexed), status, evaluation }
          const phaseNumber = (data.phase as number) ?? 1;
          const evaluation = data.evaluation as Record<string, unknown> | undefined;
          await planService.updatePhaseCompleted(conversationId, phaseNumber, evaluation);
          break;
        }

        case 'task_completed': {
          // 计划执行完成
          await planService.updatePlanStatus(conversationId, 'completed');
          break;
        }

        case 'execution_failed':
        case 'task_failed': {
          // 计划执行失败
          await planService.updatePlanStatus(conversationId, 'failed');
          break;
        }

        default:
          this.logger.debug({ eventType, conversationId }, 'Unhandled coordinator event type');
      }
    } catch (err) {
      this.logger.error({ err, eventType, conversationId }, 'Failed to handle coordinator event');
    }
  }

  /**
   * Extract testcases from text and push as SSE event
   */
  private async extractAndPushTestcases(replyId: string, textContent: string): Promise<void> {
    if (this.extractedTestcaseReplies.has(replyId)) return;
    if (!textContent || textContent.length < 100) return;

    const keywords = ['"testcases"', '"interface_name"', 'generate_positive_cases', 'generate_negative_cases'];
    if (!keywords.some((kw) => textContent.includes(kw))) return;

    try {
      const match = textContent.match(/\{.*"testcases".*\}/s);
      if (!match) return;

      const data = JSON.parse(match[0]);
      const testcases = data.testcases;
      if (!Array.isArray(testcases) || testcases.length === 0) return;

      this.extractedTestcaseReplies.add(replyId);

      this.pushToSSEQueue(replyId, {
        type: 'testcases',
        data: {
          status: data.status ?? 'unknown',
          count: data.count ?? testcases.length,
          testcases,
        },
      } as unknown as AgentMessageData);

      this.logger.info({ replyId, count: testcases.length }, 'Testcases extracted and pushed');
    } catch {
      // JSON parse failure, non-critical
    }
  }

  /**
   * Clean up all processes (called on shutdown)
   */
  cleanup(): void {
    this.logger.info({ count: this.processes.size }, 'Cleaning up all agent processes');

    for (const [replyId, child] of this.processes) {
      try {
        child.kill('SIGTERM');
        setTimeout(() => {
          try {
            child.kill('SIGKILL');
          } catch {
            // Already dead
          }
        }, 3000);
      } catch {
        // Already dead
      }
      this.logger.info({ replyId }, 'Agent process killed');
    }

    this.processes.clear();
    this.conversationAgents.clear();
    this.pendingReplies.clear();
    this.messageCallbacks.clear();
    this.extractedTestcaseReplies.clear();
    this.hiddenToolCallIds.clear();
  }
}

let _agentManager: AgentManager | null = null;

export function getAgentManager(): AgentManager {
  if (!_agentManager) {
    _agentManager = new AgentManager();
  }
  return _agentManager;
}

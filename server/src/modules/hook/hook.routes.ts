import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getLogger } from '../../config/logger.js';
import * as hookService from './hook.service.js';
import type { AgentEvent } from '../../agent/types.js';

export async function registerHookRoutes(app: FastifyInstance): Promise<void> {
  const logger = getLogger();

  // POST /trpc/pushMessageToChatAgent
  // Supports both new format { replyId, events: AgentEvent[] }
  // and legacy format { replyId, msg: Record<string, unknown> }
  app.post('/trpc/pushMessageToChatAgent', { config: { rateLimit: false } }, async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = request.body as {
        replyId: string;
        events?: AgentEvent[];
        msg?: Record<string, unknown>;
      };

      if (!body.replyId) {
        return reply.status(400).send({ success: false, error: 'Missing replyId' });
      }

      if (body.events && Array.isArray(body.events)) {
        // New structured events format
        await hookService.handlePushEvents(body.replyId, body.events);
      } else if (body.msg) {
        // Legacy format
        await hookService.handlePushMessage(body.replyId, body.msg);
      } else {
        return reply.status(400).send({ success: false, error: 'Missing events or msg' });
      }

      return { success: true };
    } catch (err) {
      logger.error({ err }, 'Hook: failed to handle agent message');
      return { success: false, error: String(err) };
    }
  });

  // POST /trpc/pushFinishedSignalToChatAgent
  app.post('/trpc/pushFinishedSignalToChatAgent', { config: { rateLimit: false } }, async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = request.body as { replyId: string };

      if (!body.replyId) {
        return reply.status(400).send({ success: false, error: 'Missing replyId' });
      }

      await hookService.handlePushFinished(body.replyId);

      return { success: true };
    } catch (err) {
      logger.error({ err }, 'Hook: failed to handle finished signal');
      return { success: false, error: String(err) };
    }
  });
}

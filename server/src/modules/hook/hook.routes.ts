import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getLogger } from '../../config/logger.js';
import * as hookService from './hook.service.js';

export async function registerHookRoutes(app: FastifyInstance): Promise<void> {
  const logger = getLogger();

  // POST /trpc/pushMessageToChatAgent
  app.post('/trpc/pushMessageToChatAgent', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = request.body as { replyId: string; msg: Record<string, unknown> };

      if (!body.replyId || !body.msg) {
        return reply.status(400).send({ success: false, error: 'Missing replyId or msg' });
      }

      await hookService.handlePushMessage(body.replyId, body.msg);

      return { success: true };
    } catch (err) {
      logger.error({ err }, 'Hook: failed to handle agent message');
      return { success: false, error: String(err) };
    }
  });

  // POST /trpc/pushFinishedSignalToChatAgent
  app.post('/trpc/pushFinishedSignalToChatAgent', async (request: FastifyRequest, reply: FastifyReply) => {
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

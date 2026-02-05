import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { authenticate } from '../../plugins/auth.js';
import {
  createConversationSchema,
  updateConversationSchema,
  createMessageSchema,
  paginationSchema,
} from './conversation.schemas.js';
import * as conversationService from './conversation.service.js';

export async function registerConversationRoutes(app: FastifyInstance): Promise<void> {
  // POST /api/conversations
  app.post(
    '/api/conversations',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const body = createConversationSchema.parse(request.body);
      const result = await conversationService.createConversation(
        request.currentUser!.user_id,
        body.title
      );
      return reply.status(201).send(result);
    }
  );

  // GET /api/conversations
  app.get(
    '/api/conversations',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const query = paginationSchema.parse(request.query);
      return conversationService.listConversations(
        request.currentUser!.user_id,
        query.limit,
        query.offset
      );
    }
  );

  // GET /api/conversations/:id
  app.get(
    '/api/conversations/:id',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      return conversationService.getConversation(id, request.currentUser!.user_id);
    }
  );

  // PUT /api/conversations/:id
  app.put(
    '/api/conversations/:id',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      const body = updateConversationSchema.parse(request.body);
      return conversationService.updateConversation(
        id,
        request.currentUser!.user_id,
        body.title
      );
    }
  );

  // DELETE /api/conversations/:id
  app.delete(
    '/api/conversations/:id',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      return conversationService.deleteConversation(id, request.currentUser!.user_id);
    }
  );

  // POST /api/conversations/:id/messages
  app.post(
    '/api/conversations/:id/messages',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      const body = createMessageSchema.parse(request.body);
      const result = await conversationService.createMessage(
        id,
        request.currentUser!.user_id,
        body.role,
        body.content
      );
      return reply.status(201).send(result);
    }
  );

  // GET /api/conversations/:id/messages
  app.get(
    '/api/conversations/:id/messages',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      const query = paginationSchema.parse(request.query);
      return conversationService.listMessages(
        id,
        request.currentUser!.user_id,
        query.limit,
        query.offset
      );
    }
  );

  // GET /api/conversations/:id/plan
  app.get(
    '/api/conversations/:id/plan',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      return conversationService.getConversationPlan(id, request.currentUser!.user_id);
    }
  );
}

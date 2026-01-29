import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { authenticate } from '../../plugins/auth.js';
import * as reportService from './report.service.js';

export async function registerReportRoutes(app: FastifyInstance): Promise<void> {
  // GET /api/reports/:taskId
  app.get(
    '/api/reports/:taskId',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { taskId } = request.params as { taskId: string };
      return reportService.getReportData(taskId);
    }
  );

  // GET /api/reports/:taskId/markdown
  app.get(
    '/api/reports/:taskId/markdown',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const { taskId } = request.params as { taskId: string };
      const markdown = await reportService.getMarkdownReport(taskId);
      return reply.type('text/markdown').send(markdown);
    }
  );
}

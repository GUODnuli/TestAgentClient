import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { authenticate } from '../../plugins/auth.js';
import { createTaskSchema, updateTaskStatusSchema, listTasksQuerySchema } from './task.schemas.js';
import * as taskService from './task.service.js';

export async function registerTaskRoutes(app: FastifyInstance): Promise<void> {
  // POST /api/tasks
  app.post(
    '/api/tasks',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const body = createTaskSchema.parse(request.body);
      const result = await taskService.createTask(
        request.currentUser!.user_id,
        body.task_type,
        body.parameters
      );
      return reply.status(201).send(result);
    }
  );

  // GET /api/tasks
  app.get(
    '/api/tasks',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const query = listTasksQuerySchema.parse(request.query);
      return taskService.listTasks(request.currentUser!.user_id, {
        status: query.status,
        taskType: query.task_type,
        limit: query.limit,
        offset: query.offset,
        orderBy: query.order_by,
        orderDir: query.order_dir,
      });
    }
  );

  // GET /api/tasks/statistics — must be registered before :id route
  app.get(
    '/api/tasks/statistics',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      return taskService.getTaskStatistics(request.currentUser!.user_id);
    }
  );

  // GET /api/tasks/:id
  app.get(
    '/api/tasks/:id',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      return taskService.getTask(id);
    }
  );

  // PUT /api/tasks/:id/status
  app.put(
    '/api/tasks/:id/status',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      const body = updateTaskStatusSchema.parse(request.body);
      return taskService.updateTaskStatus(id, body.status, body.error_message);
    }
  );

  // DELETE /api/tasks/:id
  app.delete(
    '/api/tasks/:id',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const { id } = request.params as { id: string };
      return taskService.deleteTask(id);
    }
  );
}

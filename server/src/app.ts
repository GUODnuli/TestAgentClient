import Fastify, { type FastifyInstance } from 'fastify';
import multipart from '@fastify/multipart';
import { getLogger } from './config/logger.js';
import { registerCors } from './plugins/cors.js';
import { registerErrorHandler } from './plugins/error-handler.js';
import { registerRateLimit } from './plugins/rate-limit.js';
import { registerAuthPlugin } from './plugins/auth.js';
import { registerSocketIO } from './plugins/socket-io.js';
import { registerAuthRoutes } from './modules/auth/auth.routes.js';
import { registerConversationRoutes } from './modules/conversation/conversation.routes.js';
import { registerChatRoutes } from './modules/chat/chat.routes.js';
import { registerHookRoutes } from './modules/hook/hook.routes.js';
import { registerTaskRoutes } from './modules/task/task.routes.js';
import { registerReportRoutes } from './modules/report/report.routes.js';

export async function buildApp(): Promise<FastifyInstance> {
  const logger = getLogger();

  const app = Fastify({
    logger: false,
  });

  // Core plugins
  await registerCors(app);
  await registerErrorHandler(app);
  await registerRateLimit(app);
  await registerAuthPlugin(app);

  // Multipart for file uploads
  await app.register(multipart, {
    limits: {
      fileSize: 50 * 1024 * 1024, // 50MB
    },
  });

  // Health check
  app.get('/health', async () => ({
    status: 'ok',
    timestamp: new Date().toISOString(),
  }));

  // Root endpoint
  app.get('/', async () => ({
    service: 'MCP 智能体',
    version: '2.0.0',
    status: 'running',
  }));

  // Register route modules
  await registerAuthRoutes(app);
  await registerConversationRoutes(app);
  await registerChatRoutes(app);
  await registerHookRoutes(app);
  await registerTaskRoutes(app);
  await registerReportRoutes(app);

  // Socket.IO (after all routes registered)
  await registerSocketIO(app);

  logger.info('Fastify app built successfully');

  return app;
}

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { authenticate, requireAdmin } from '../../plugins/auth.js';
import {
  registerSchema,
  loginSchema,
  changePasswordSchema,
  updateProfileSchema,
  updateUserStatusSchema,
} from './auth.schemas.js';
import * as authService from './auth.service.js';
import { getClientIp, getDeviceInfo } from '../../common/utils.js';
import { getLogger } from '../../config/logger.js';

export async function registerAuthRoutes(app: FastifyInstance): Promise<void> {
  const logger = getLogger();

  // POST /auth/register
  app.post('/auth/register', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = registerSchema.parse(request.body);
    logger.info({ username: body.username }, 'Register request');

    const user = await authService.register(body);
    return reply.status(201).send(user);
  });

  // POST /auth/login
  app.post('/auth/login', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = loginSchema.parse(request.body);
    const deviceInfo = getDeviceInfo(request);
    const ipAddress = getClientIp(request);

    logger.info({ username: body.username, ip: ipAddress }, 'Login request');

    const result = await authService.login(
      body.username,
      body.password,
      deviceInfo,
      ipAddress
    );

    return reply.send(result);
  });

  // POST /auth/logout
  app.post(
    '/auth/logout',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      await authService.logout(request.currentUser!.user_id);
      return reply.send({ message: '登出成功' });
    }
  );

  // GET /auth/me
  app.get(
    '/auth/me',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      return request.currentUser;
    }
  );

  // PUT /auth/password
  app.put(
    '/auth/password',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const body = changePasswordSchema.parse(request.body);

      await authService.changePassword(
        request.currentUser!.user_id,
        body.old_password,
        body.new_password
      );

      return reply.send({ message: '密码修改成功，请重新登录' });
    }
  );

  // PUT /auth/profile
  app.put(
    '/auth/profile',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const body = updateProfileSchema.parse(request.body);

      const user = await authService.updateProfile(
        request.currentUser!.user_id,
        body
      );

      return reply.send(user);
    }
  );

  // GET /auth/session
  app.get(
    '/auth/session',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const sessionInfo = await authService.getSessionInfo(request.currentUser!.user_id);
      if (sessionInfo) {
        return {
          user_id: request.currentUser!.user_id,
          device_info: sessionInfo.device_info,
          ip_address: sessionInfo.ip_address,
          created_at: sessionInfo.created_at,
        };
      }
      return { user_id: request.currentUser!.user_id, message: '会话管理未启用' };
    }
  );

  // GET /auth/users (admin)
  app.get(
    '/auth/users',
    { preHandler: [authenticate, requireAdmin] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const query = request.query as { status?: string; role?: string; limit?: string; offset?: string };
      const users = await authService.listUsers(
        query.status,
        query.role,
        query.limit ? parseInt(query.limit, 10) : 100,
        query.offset ? parseInt(query.offset, 10) : 0
      );
      return users;
    }
  );

  // PUT /auth/users/:user_id/status (admin)
  app.put(
    '/auth/users/:user_id/status',
    { preHandler: [authenticate, requireAdmin] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const { user_id } = request.params as { user_id: string };
      const body = updateUserStatusSchema.parse(request.body);

      await authService.updateUserStatus(user_id, body.new_status);

      return reply.send({ message: `用户状态已更新为 ${body.new_status}` });
    }
  );
}

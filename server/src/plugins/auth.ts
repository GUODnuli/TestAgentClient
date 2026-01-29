import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getConfig } from '../config/index.js';
import { getRedis } from '../config/redis.js';
import { getPrisma } from '../config/database.js';
import { getLogger } from '../config/logger.js';
import { UnauthorizedError, ForbiddenError } from '../common/errors.js';
import type { JwtPayload } from '../common/types.js';
import jwt from 'jsonwebtoken';

declare module 'fastify' {
  interface FastifyRequest {
    currentUser?: {
      user_id: string;
      username: string;
      email: string | null;
      display_name: string | null;
      role: string;
      status: string;
    };
  }
}

function extractToken(request: FastifyRequest): string | null {
  const authHeader = request.headers.authorization;
  if (!authHeader) return null;

  const parts = authHeader.split(' ');
  if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer') return null;

  return parts[1];
}

export async function authenticate(request: FastifyRequest, _reply: FastifyReply): Promise<void> {
  const logger = getLogger();
  const config = getConfig();
  const redis = getRedis();
  const prisma = getPrisma();

  const token = extractToken(request);
  if (!token) {
    throw new UnauthorizedError('未提供认证凭证');
  }

  let payload: JwtPayload;
  try {
    payload = jwt.verify(token, config.jwt.secret) as JwtPayload;
  } catch {
    throw new UnauthorizedError('Token无效或已过期');
  }

  const { sub: userId, jti } = payload;
  if (!userId || !jti) {
    throw new UnauthorizedError('Token格式错误');
  }

  // Validate session in Redis
  const sessionKey = `session:${userId}`;
  try {
    const sessionData = await redis.get(sessionKey);
    if (sessionData) {
      const session = JSON.parse(sessionData);
      if (session.token_jti !== jti) {
        logger.warn({ userId }, 'Session invalidated (kicked out)');
        throw new UnauthorizedError('会话已失效，请重新登录');
      }
    }
  } catch (err) {
    if (err instanceof UnauthorizedError) throw err;
    // Redis error - allow access gracefully
    logger.error({ err }, 'Redis session check failed');
  }

  // Get user from DB
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new UnauthorizedError('用户不存在');
  }

  if (user.status !== 'ACTIVE') {
    throw new ForbiddenError('账户已被禁用');
  }

  request.currentUser = {
    user_id: user.id,
    username: user.username,
    email: user.email,
    display_name: user.displayName,
    role: user.role.toLowerCase(),
    status: user.status.toLowerCase(),
  };
}

export async function requireAdmin(request: FastifyRequest, _reply: FastifyReply): Promise<void> {
  if (!request.currentUser) {
    throw new UnauthorizedError('未提供认证凭证');
  }
  if (request.currentUser.role !== 'admin') {
    throw new ForbiddenError('需要管理员权限');
  }
}

export async function registerAuthPlugin(app: FastifyInstance): Promise<void> {
  app.decorate('authenticate', authenticate);
  app.decorate('requireAdmin', requireAdmin);
}

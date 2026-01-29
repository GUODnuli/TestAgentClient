import bcrypt from 'bcryptjs';
import { v4 as uuidv4 } from 'uuid';
import { getPrisma } from '../../config/database.js';
import { getRedis } from '../../config/redis.js';
import { getLogger } from '../../config/logger.js';
import { getConfig } from '../../config/index.js';
import { createAccessToken, getTokenExpiresInSeconds } from './jwt.service.js';
import { ValidationError, UnauthorizedError, ConflictError } from '../../common/errors.js';
import { formatUser } from '../../common/utils.js';
import { CacheKeys, CacheTTL } from '../../cache/cache-keys.js';
import type { UserRole, UserStatus } from '@prisma/client';

// Session management

async function createSession(
  userId: string,
  tokenJti: string,
  deviceInfo: string,
  ipAddress: string
): Promise<void> {
  const logger = getLogger();
  const redis = getRedis();
  const sessionKey = CacheKeys.session(userId);
  const sessionTtl = getConfig().jwt.expiresInHours * 3600;

  try {
    const oldSession = await redis.get(sessionKey);
    if (oldSession) {
      const old = JSON.parse(oldSession);
      logger.info({ userId, oldJti: old.token_jti?.slice(0, 8) }, 'Kicking out old session');
    }

    const sessionData = {
      token_jti: tokenJti,
      device_info: deviceInfo,
      ip_address: ipAddress,
      created_at: new Date().toISOString(),
    };

    await redis.setex(sessionKey, sessionTtl, JSON.stringify(sessionData));
    logger.info({ userId, jti: tokenJti.slice(0, 8) }, 'Session created');
  } catch (err) {
    logger.error({ err }, 'Failed to create session');
  }
}

async function invalidateSession(userId: string): Promise<void> {
  const logger = getLogger();
  const redis = getRedis();
  const sessionKey = CacheKeys.session(userId);

  try {
    await redis.del(sessionKey);
    logger.info({ userId }, 'Session invalidated');
  } catch (err) {
    logger.error({ err }, 'Failed to invalidate session');
  }
}

async function getSessionInfo(userId: string): Promise<Record<string, unknown> | null> {
  const redis = getRedis();
  const sessionKey = CacheKeys.session(userId);

  try {
    const data = await redis.get(sessionKey);
    if (data) {
      return JSON.parse(data);
    }
    return null;
  } catch {
    return null;
  }
}

// Auth operations

export async function register(input: {
  username: string;
  password: string;
  email?: string | null;
  display_name?: string | null;
}) {
  const prisma = getPrisma();
  const logger = getLogger();

  const existingUser = await prisma.user.findUnique({ where: { username: input.username } });
  if (existingUser) {
    throw new ConflictError('用户名已存在');
  }

  if (input.email) {
    const existingEmail = await prisma.user.findUnique({ where: { email: input.email } });
    if (existingEmail) {
      throw new ConflictError('邮箱已被使用');
    }
  }

  const passwordHash = await bcrypt.hash(input.password, 10);

  const user = await prisma.user.create({
    data: {
      username: input.username,
      passwordHash,
      email: input.email ?? null,
      displayName: input.display_name ?? input.username,
    },
  });

  logger.info({ userId: user.id, username: user.username }, 'User registered');

  return formatUser(user);
}

export async function login(
  username: string,
  password: string,
  deviceInfo: string,
  ipAddress: string
) {
  const prisma = getPrisma();
  const logger = getLogger();

  const user = await prisma.user.findUnique({ where: { username } });
  if (!user) {
    logger.warn({ username }, 'Login failed: user not found');
    throw new UnauthorizedError('用户名或密码错误');
  }

  if (user.status !== 'ACTIVE') {
    logger.warn({ username }, 'Login failed: user disabled');
    throw new UnauthorizedError('账户已被禁用');
  }

  const passwordValid = await bcrypt.compare(password, user.passwordHash);
  if (!passwordValid) {
    logger.warn({ username }, 'Login failed: wrong password');
    throw new UnauthorizedError('用户名或密码错误');
  }

  const { token, jti } = createAccessToken(
    user.id,
    user.username,
    user.role.toLowerCase()
  );

  await createSession(user.id, jti, deviceInfo, ipAddress);

  await prisma.user.update({
    where: { id: user.id },
    data: { lastLoginAt: new Date() },
  });

  logger.info({ userId: user.id, username, ip: ipAddress }, 'User logged in');

  return {
    access_token: token,
    token_type: 'bearer',
    expires_in: getTokenExpiresInSeconds(),
    user: formatUser(user),
  };
}

export async function logout(userId: string): Promise<void> {
  const logger = getLogger();
  await invalidateSession(userId);
  logger.info({ userId }, 'User logged out');
}

export async function changePassword(
  userId: string,
  oldPassword: string,
  newPassword: string
): Promise<void> {
  const prisma = getPrisma();
  const logger = getLogger();

  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new ValidationError('用户不存在');
  }

  const passwordValid = await bcrypt.compare(oldPassword, user.passwordHash);
  if (!passwordValid) {
    throw new ValidationError('旧密码错误');
  }

  const newHash = await bcrypt.hash(newPassword, 10);
  await prisma.user.update({
    where: { id: userId },
    data: { passwordHash: newHash },
  });

  await invalidateSession(userId);
  logger.info({ userId }, 'Password changed');
}

export async function updateProfile(
  userId: string,
  input: { display_name?: string | null; email?: string | null }
) {
  const prisma = getPrisma();

  const data: Record<string, unknown> = {};
  if (input.display_name !== undefined) {
    data.displayName = input.display_name;
  }
  if (input.email !== undefined) {
    data.email = input.email;
  }

  const user = await prisma.user.update({
    where: { id: userId },
    data,
  });

  return formatUser(user);
}

export async function getUserById(userId: string) {
  const prisma = getPrisma();
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) return null;
  return formatUser(user);
}

export async function listUsers(
  status?: string,
  role?: string,
  limit: number = 100,
  offset: number = 0
) {
  const prisma = getPrisma();

  const where: Record<string, unknown> = {};
  if (status) {
    where.status = status.toUpperCase() as UserStatus;
  }
  if (role) {
    where.role = role.toUpperCase() as UserRole;
  }

  const users = await prisma.user.findMany({
    where,
    orderBy: { createdAt: 'desc' },
    take: limit,
    skip: offset,
  });

  return users.map(formatUser);
}

export async function updateUserStatus(userId: string, newStatus: string): Promise<void> {
  const prisma = getPrisma();

  await prisma.user.update({
    where: { id: userId },
    data: { status: newStatus.toUpperCase() as UserStatus },
  });

  if (newStatus === 'inactive' || newStatus === 'banned') {
    await invalidateSession(userId);
  }
}

export { getSessionInfo, invalidateSession };

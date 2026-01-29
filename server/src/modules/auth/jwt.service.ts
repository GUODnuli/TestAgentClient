import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import { getConfig } from '../../config/index.js';
import { getLogger } from '../../config/logger.js';
import type { JwtPayload } from '../../common/types.js';

export interface TokenResult {
  token: string;
  jti: string;
  expiresAt: Date;
}

export function createAccessToken(userId: string, username: string, role: string): TokenResult {
  const config = getConfig();
  const logger = getLogger();

  const jti = uuidv4();
  const now = Math.floor(Date.now() / 1000);
  const expiresInSeconds = config.jwt.expiresInHours * 3600;
  const expiresAt = new Date((now + expiresInSeconds) * 1000);

  const payload: JwtPayload = {
    sub: userId,
    username,
    role,
    jti,
    iat: now,
    exp: now + expiresInSeconds,
  };

  const token = jwt.sign(payload, config.jwt.secret);

  logger.info({ userId, jti: jti.slice(0, 8) }, 'JWT token created');

  return { token, jti, expiresAt };
}

export function verifyToken(token: string): JwtPayload | null {
  const config = getConfig();
  const logger = getLogger();

  try {
    return jwt.verify(token, config.jwt.secret) as JwtPayload;
  } catch (err) {
    if (err instanceof jwt.TokenExpiredError) {
      logger.warn('Token expired');
    } else {
      logger.warn({ err }, 'Invalid token');
    }
    return null;
  }
}

export function decodeTokenUnsafe(token: string): JwtPayload | null {
  try {
    return jwt.decode(token) as JwtPayload | null;
  } catch {
    return null;
  }
}

export function getTokenExpiresInSeconds(): number {
  return getConfig().jwt.expiresInHours * 3600;
}

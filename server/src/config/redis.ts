import Redis from 'ioredis';
import { getConfig } from './index.js';
import { getLogger } from './logger.js';

let redis: Redis | null = null;

export function getRedis(): Redis {
  if (!redis) {
    const config = getConfig();
    const logger = getLogger();

    redis = new Redis(config.redis.url, {
      maxRetriesPerRequest: null,
      enableReadyCheck: true,
      retryStrategy(times) {
        const delay = Math.min(times * 200, 5000);
        return delay;
      },
    });

    redis.on('connect', () => {
      logger.info('Redis connected');
    });

    redis.on('error', (err) => {
      logger.error({ err }, 'Redis connection error');
    });

    redis.on('close', () => {
      logger.warn('Redis connection closed');
    });
  }
  return redis;
}

export async function disconnectRedis(): Promise<void> {
  if (redis) {
    await redis.quit();
    redis = null;
  }
}

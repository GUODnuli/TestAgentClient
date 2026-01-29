import { getRedis } from '../config/redis.js';
import { getLogger } from '../config/logger.js';

export async function getCache(key: string): Promise<string | null> {
  try {
    return await getRedis().get(key);
  } catch (err) {
    getLogger().error({ err, key }, 'Cache get failed');
    return null;
  }
}

export async function setCache(key: string, value: string, ttlSeconds: number): Promise<void> {
  try {
    await getRedis().setex(key, ttlSeconds, value);
  } catch (err) {
    getLogger().error({ err, key }, 'Cache set failed');
  }
}

export async function deleteCache(key: string): Promise<void> {
  try {
    await getRedis().del(key);
  } catch (err) {
    getLogger().error({ err, key }, 'Cache delete failed');
  }
}

export async function deleteCachePattern(pattern: string): Promise<void> {
  const redis = getRedis();
  try {
    const keys = await redis.keys(pattern);
    if (keys.length > 0) {
      await redis.del(...keys);
    }
  } catch (err) {
    getLogger().error({ err, pattern }, 'Cache pattern delete failed');
  }
}

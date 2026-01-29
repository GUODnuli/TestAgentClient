import path from 'path';
import fs from 'fs';
import { getConfig } from '../config/index.js';
import { getLogger } from '../config/logger.js';
import { validateStoragePath } from './path-validator.js';

export function ensureStorageDirectories(): void {
  const config = getConfig();
  const root = path.resolve(config.storage.root);

  const dirs = [
    root,
    path.join(root, 'tasks'),
    path.join(root, 'templates'),
    path.join(root, 'vectordb'),
    path.join(root, 'cache'),
    path.join(root, 'chat'),
  ];

  for (const dir of dirs) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

export function saveChatFile(
  userId: string,
  conversationId: string,
  filename: string,
  content: Buffer
): string {
  const config = getConfig();
  const chatDir = path.resolve(config.storage.root, 'chat', userId, conversationId);
  fs.mkdirSync(chatDir, { recursive: true });

  const filePath = path.join(chatDir, filename);
  const safePath = validateStoragePath(filePath);

  fs.writeFileSync(safePath, content);

  getLogger().info({ userId, conversationId, filename }, 'Chat file saved');
  return safePath;
}

export function cleanupOldFiles(daysToKeep: number = 7): number {
  const config = getConfig();
  const logger = getLogger();
  const chatRoot = path.resolve(config.storage.root, 'chat');

  if (!fs.existsSync(chatRoot)) return 0;

  const now = Date.now();
  const maxAge = daysToKeep * 24 * 3600 * 1000;
  let count = 0;

  function walk(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else {
        const stat = fs.statSync(fullPath);
        if (now - stat.mtimeMs > maxAge) {
          fs.unlinkSync(fullPath);
          count++;
        }
      }
    }
  }

  try {
    walk(chatRoot);
    if (count > 0) {
      logger.info({ count, daysToKeep }, 'Old chat files cleaned up');
    }
  } catch (err) {
    logger.error({ err }, 'Failed to cleanup old files');
  }

  return count;
}

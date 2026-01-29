import path from 'path';
import { getConfig } from '../config/index.js';

/**
 * Validate that a path is within the storage root directory.
 * Prevents path traversal attacks.
 */
export function validateStoragePath(filePath: string): string {
  const config = getConfig();
  const storageRoot = path.resolve(config.storage.root);
  const resolved = path.resolve(filePath);

  if (!resolved.startsWith(storageRoot)) {
    throw new Error(`Path ${filePath} is outside storage root`);
  }

  return resolved;
}

/**
 * Build a safe storage path from segments
 */
export function buildStoragePath(...segments: string[]): string {
  const config = getConfig();
  const filePath = path.resolve(config.storage.root, ...segments);
  return validateStoragePath(filePath);
}

import 'dotenv/config';
import { getConfig } from './config/index.js';
import { getLogger } from './config/logger.js';
import { getPrisma, disconnectPrisma } from './config/database.js';
import { disconnectRedis } from './config/redis.js';
import { buildApp } from './app.js';
import { getAgentManager } from './agent/agent-manager.js';
import { ensureStorageDirectories, cleanupOldFiles } from './storage/storage.service.js';

async function main() {
  const logger = getLogger();
  const config = getConfig();

  // Test database connection
  try {
    await getPrisma().$connect();
    logger.info('PostgreSQL connected');
  } catch (err) {
    logger.error({ err }, 'Failed to connect to PostgreSQL');
    process.exit(1);
  }

  // Ensure storage directories exist
  ensureStorageDirectories();
  logger.info('Storage directories initialized');

  // Build and start Fastify
  const app = await buildApp();

  try {
    await app.listen({ port: config.port, host: config.host });
    logger.info(`Server listening on ${config.host}:${config.port}`);
    logger.info(`Environment: ${config.nodeEnv}`);

    // Schedule periodic file cleanup (every 24 hours)
    const CLEANUP_INTERVAL = 24 * 60 * 60 * 1000;
    setInterval(() => {
      cleanupOldFiles(7);
    }, CLEANUP_INTERVAL);
  } catch (err) {
    logger.error({ err }, 'Failed to start server');
    process.exit(1);
  }

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    logger.info(`Received ${signal}, shutting down gracefully...`);

    // Terminate all agent processes
    try {
      getAgentManager().cleanup();
      logger.info('All agent processes terminated');
    } catch {
      // Agent manager may not be initialized
    }

    // Close server
    try {
      await app.close();
      logger.info('Fastify server closed');
    } catch (err) {
      logger.error({ err }, 'Error closing Fastify server');
    }

    // Disconnect databases
    await disconnectPrisma();
    await disconnectRedis();
    logger.info('Database connections closed');

    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});

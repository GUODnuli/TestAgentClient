import type { FastifyInstance } from 'fastify';
import { AppError } from '../common/errors.js';
import { getLogger } from '../config/logger.js';

export async function registerErrorHandler(app: FastifyInstance): Promise<void> {
  const logger = getLogger();

  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof AppError) {
      return reply.status(error.statusCode).send({
        success: false,
        error: error.code,
        message: error.message,
      });
    }

    // Fastify validation errors
    if (error.validation) {
      return reply.status(400).send({
        success: false,
        error: 'VALIDATION_ERROR',
        message: error.message,
      });
    }

    // JWT errors from @fastify/jwt
    if (error.statusCode === 401) {
      return reply.status(401).send({
        success: false,
        error: 'UNAUTHORIZED',
        message: error.message || 'Token无效或已过期',
      });
    }

    logger.error({ err: error }, 'Unhandled error');

    return reply.status(500).send({
      success: false,
      error: 'INTERNAL_ERROR',
      message: '服务器内部错误',
    });
  });

  app.setNotFoundHandler((_request, reply) => {
    return reply.status(404).send({
      success: false,
      error: 'NOT_FOUND',
      message: '接口不存在',
    });
  });
}

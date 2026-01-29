import type { FastifyInstance, FastifyError } from 'fastify';
import { ZodError } from 'zod';
import { AppError } from '../common/errors.js';
import { getLogger } from '../config/logger.js';

export async function registerErrorHandler(app: FastifyInstance): Promise<void> {
  const logger = getLogger();

  app.setErrorHandler((error: FastifyError | AppError | ZodError | Error, _request, reply) => {
    if (error instanceof AppError) {
      return reply.status(error.statusCode).send({
        success: false,
        error: error.code,
        message: error.message,
      });
    }

    // Zod validation errors (from schema.parse() in routes)
    if (error instanceof ZodError) {
      const messages = error.errors.map((e) => `${e.path.join('.')}: ${e.message}`);
      return reply.status(400).send({
        success: false,
        error: 'VALIDATION_ERROR',
        message: messages.join('; ') || '请求参数验证失败',
      });
    }

    // Fastify validation errors
    if ('validation' in error && (error as FastifyError).validation) {
      return reply.status(400).send({
        success: false,
        error: 'VALIDATION_ERROR',
        message: error.message,
      });
    }

    // JWT errors from @fastify/jwt
    if ('statusCode' in error && (error as FastifyError).statusCode === 401) {
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

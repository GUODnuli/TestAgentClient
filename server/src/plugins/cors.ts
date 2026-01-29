import cors from '@fastify/cors';
import type { FastifyInstance } from 'fastify';
import { getConfig } from '../config/index.js';

export async function registerCors(app: FastifyInstance): Promise<void> {
  const config = getConfig();
  await app.register(cors, {
    origin: config.cors.origins,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
  });
}

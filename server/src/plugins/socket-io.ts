import { Server as SocketIOServer } from 'socket.io';
import type { FastifyInstance } from 'fastify';
import type http from 'http';
import { getConfig } from '../config/index.js';
import { getLogger } from '../config/logger.js';
import { NAMESPACES, CLIENT_EVENTS, chatRoom } from '../socket/namespaces.js';

let io: SocketIOServer | null = null;

export function getSocketIO(): SocketIOServer {
  if (!io) {
    throw new Error('Socket.IO not initialized');
  }
  return io;
}

export async function registerSocketIO(app: FastifyInstance): Promise<void> {
  const config = getConfig();
  const logger = getLogger();

  await app.ready();

  const httpServer = app.server as http.Server;

  io = new SocketIOServer(httpServer, {
    cors: {
      origin: config.cors.origins,
      credentials: true,
    },
    transports: ['websocket', 'polling'],
  });

  // /client namespace
  const clientNs = io.of(NAMESPACES.CLIENT);

  clientNs.on('connection', (socket) => {
    logger.info({ sid: socket.id }, 'Client connected');

    socket.on(CLIENT_EVENTS.JOIN_CHAT_ROOM, (conversationId: string) => {
      const room = chatRoom(conversationId);
      socket.join(room);
      logger.debug({ sid: socket.id, room }, 'Client joined room');
    });

    socket.on(CLIENT_EVENTS.LEAVE_CHAT_ROOM, (conversationId: string) => {
      const room = chatRoom(conversationId);
      socket.leave(room);
      logger.debug({ sid: socket.id, room }, 'Client left room');
    });

    socket.on('disconnect', () => {
      logger.info({ sid: socket.id }, 'Client disconnected');
    });
  });

  // /agent namespace
  const agentNs = io.of(NAMESPACES.AGENT);

  agentNs.on('connection', (socket) => {
    logger.info({ sid: socket.id }, 'Agent connected');

    socket.on('disconnect', () => {
      logger.info({ sid: socket.id }, 'Agent disconnected');
    });
  });

  logger.info('Socket.IO initialized');
}

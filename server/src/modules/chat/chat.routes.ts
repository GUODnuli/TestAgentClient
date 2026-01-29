import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { authenticate } from '../../plugins/auth.js';
import { chatMessageSchema, interruptSchema } from './chat.schemas.js';
import * as chatService from './chat.service.js';
import { streamSSE } from './sse.handler.js';
import { getLogger } from '../../config/logger.js';
import path from 'path';
import fs from 'fs';
import { getConfig } from '../../config/index.js';

// In-memory file index (same pattern as Python backend)
const chatFilesIndex = new Map<string, string[]>();

export async function registerChatRoutes(app: FastifyInstance): Promise<void> {
  const logger = getLogger();

  // POST /api/chat/send
  app.post(
    '/api/chat/send',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const body = chatMessageSchema.parse(request.body);
      const userId = request.currentUser!.user_id;

      logger.info(
        { userId, conversationId: body.conversation_id, msgLen: body.message.length },
        'Chat send request'
      );

      const result = await chatService.sendMessage(
        body.message,
        userId,
        body.conversation_id
      );

      return { success: true, data: result };
    }
  );

  // POST /api/chat/stream
  app.post(
    '/api/chat/stream',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, reply: FastifyReply) => {
      const body = chatMessageSchema.parse(request.body);
      const userId = request.currentUser!.user_id;
      const conversationId = body.conversation_id ?? undefined;

      logger.info(
        { userId, conversationId, msgLen: body.message.length },
        'Chat stream request'
      );

      // Get uploaded files for this conversation
      const uploadedFiles = conversationId
        ? chatFilesIndex.get(conversationId) ?? []
        : [];

      const generator = chatService.sendMessageStreaming({
        message: body.message,
        userId,
        conversationId,
        uploadedFiles,
      });

      await streamSSE(reply, generator);
    }
  );

  // POST /api/chat/upload
  app.post(
    '/api/chat/upload',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const userId = request.currentUser!.user_id;
      const config = getConfig();

      const data = await request.file();
      if (!data) {
        return { success: false, message: '未找到上传文件' };
      }

      // Get conversation_id from fields
      const fields = data.fields as Record<string, { value?: string }>;
      const conversationId = fields.conversation_id?.value;

      if (!conversationId) {
        return { success: false, message: '缺少 conversation_id' };
      }

      const filename = data.filename;
      const fileBuffer = await data.toBuffer();

      // Save file to storage
      const chatDir = path.resolve(config.storage.root, 'chat', userId, conversationId);
      fs.mkdirSync(chatDir, { recursive: true });

      const filePath = path.join(chatDir, filename);

      // Path security: ensure within storage root
      const storageRoot = path.resolve(config.storage.root);
      const resolvedPath = path.resolve(filePath);
      if (!resolvedPath.startsWith(storageRoot)) {
        return { success: false, message: '路径不安全' };
      }

      fs.writeFileSync(resolvedPath, fileBuffer);

      // Update file index
      if (!chatFilesIndex.has(conversationId)) {
        chatFilesIndex.set(conversationId, []);
      }
      const files = chatFilesIndex.get(conversationId)!;
      if (!files.includes(filename)) {
        files.push(filename);
      }

      logger.info(
        { userId, conversationId, filename },
        'Chat file uploaded'
      );

      return {
        success: true,
        data: { filename },
      };
    }
  );

  // POST /api/chat/interrupt
  app.post(
    '/api/chat/interrupt',
    { preHandler: [authenticate] },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const body = interruptSchema.parse(request.body);

      const success = await chatService.interruptAgent(body.reply_id);

      if (success) {
        return { success: true, message: 'Agent 已终止' };
      }
      return { success: false, message: '未找到对应的 Agent 或终止失败' };
    }
  );
}

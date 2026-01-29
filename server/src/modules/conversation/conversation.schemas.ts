import { z } from 'zod';

export const createConversationSchema = z.object({
  title: z.string().min(1, '标题不能为空'),
});

export const updateConversationSchema = z.object({
  title: z.string().min(1, '标题不能为空'),
});

export const createMessageSchema = z.object({
  role: z.enum(['user', 'assistant']),
  content: z.string().min(1, '内容不能为空'),
});

export const paginationSchema = z.object({
  limit: z.coerce.number().int().min(1).max(1000).default(100),
  offset: z.coerce.number().int().min(0).default(0),
});

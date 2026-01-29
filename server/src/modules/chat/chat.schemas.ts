import { z } from 'zod';

export const chatMessageSchema = z.object({
  message: z.string().min(1, '消息不能为空'),
  conversation_id: z.string().nullable().optional(),
});

export const interruptSchema = z.object({
  reply_id: z.string().min(1, '缺少 reply_id'),
});

export type ChatMessageInput = z.infer<typeof chatMessageSchema>;
export type InterruptInput = z.infer<typeof interruptSchema>;

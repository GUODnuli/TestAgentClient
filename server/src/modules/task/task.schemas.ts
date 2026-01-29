import { z } from 'zod';

export const createTaskSchema = z.object({
  task_type: z.enum(['generate-testcase', 'autotest', 'analyze-report']),
  parameters: z.record(z.unknown()).default({}),
});

export const updateTaskStatusSchema = z.object({
  status: z.enum(['PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED']),
  error_message: z.string().nullable().optional(),
});

export const listTasksQuerySchema = z.object({
  status: z.string().optional(),
  task_type: z.string().optional(),
  limit: z.coerce.number().int().min(1).max(1000).default(100),
  offset: z.coerce.number().int().min(0).default(0),
  order_by: z.enum(['created_at', 'updated_at', 'status']).default('created_at'),
  order_dir: z.enum(['asc', 'desc']).default('desc'),
});

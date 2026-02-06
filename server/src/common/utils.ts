/**
 * Convert camelCase object keys to snake_case for API compatibility
 */
export function toSnakeCase(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
    result[snakeKey] = value;
  }
  return result;
}

/**
 * Convert snake_case object keys to camelCase
 */
export function toCamelCase(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    result[camelKey] = value;
  }
  return result;
}

/**
 * Format a Prisma record to snake_case API response format
 */
export function formatConversation(conv: {
  id: string;
  userId: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  _count?: { messages: number };
}) {
  return {
    conversation_id: conv.id,
    user_id: conv.userId,
    title: conv.title,
    created_at: conv.createdAt.toISOString(),
    updated_at: conv.updatedAt.toISOString(),
    message_count: conv._count?.messages ?? null,
  };
}

export function formatMessage(msg: {
  id: string;
  conversationId: string;
  role: string;
  content: string;
  metadata?: unknown;
  createdAt: Date;
}) {
  return {
    message_id: msg.id,
    conversation_id: msg.conversationId,
    role: msg.role,
    content: msg.content,
    metadata: msg.metadata ?? null,
    created_at: msg.createdAt.toISOString(),
  };
}

export function formatTask(task: {
  id: string;
  userId: string | null;
  taskType: string;
  status: string;
  parameters: unknown;
  result: unknown;
  checkpoint: unknown;
  errorMessage: string | null;
  createdAt: Date;
  updatedAt: Date;
  startedAt: Date | null;
  completedAt: Date | null;
}) {
  return {
    task_id: task.id,
    user_id: task.userId,
    task_type: task.taskType,
    status: task.status,
    parameters: task.parameters,
    result: task.result,
    checkpoint: task.checkpoint,
    error_message: task.errorMessage,
    created_at: task.createdAt.toISOString(),
    updated_at: task.updatedAt.toISOString(),
    started_at: task.startedAt?.toISOString() ?? null,
    completed_at: task.completedAt?.toISOString() ?? null,
  };
}

export function formatUser(user: {
  id: string;
  username: string;
  email: string | null;
  displayName: string | null;
  role: string;
  status: string;
  createdAt: Date;
  lastLoginAt: Date | null;
}) {
  return {
    user_id: user.id,
    username: user.username,
    email: user.email,
    display_name: user.displayName,
    role: user.role.toLowerCase(),
    status: user.status.toLowerCase(),
    created_at: user.createdAt.toISOString(),
    last_login_at: user.lastLoginAt?.toISOString() ?? null,
  };
}

/**
 * Get client IP from request headers
 */
export function getClientIp(request: { headers: Record<string, string | string[] | undefined>; ip: string }): string {
  const forwarded = request.headers['x-forwarded-for'];
  if (typeof forwarded === 'string') {
    return forwarded.split(',')[0].trim();
  }
  return request.ip;
}

/**
 * Get device info from User-Agent header
 */
export function getDeviceInfo(request: { headers: Record<string, string | string[] | undefined> }): string {
  const ua = request.headers['user-agent'];
  return typeof ua === 'string' ? ua : 'unknown';
}

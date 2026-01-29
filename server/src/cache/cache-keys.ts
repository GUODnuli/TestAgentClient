/**
 * Redis cache key patterns
 */
export const CacheKeys = {
  /** User session: session:{userId} */
  session: (userId: string) => `session:${userId}`,

  /** Conversation list cache: cache:conversations:{userId} */
  conversations: (userId: string) => `cache:conversations:${userId}`,

  /** Messages cache: cache:messages:{conversationId} */
  messages: (conversationId: string) => `cache:messages:${conversationId}`,

  /** Agent reply state: agent:reply:{replyId} */
  agentReply: (replyId: string) => `agent:reply:${replyId}`,

  /** Agent messages list: agent:messages:{replyId} */
  agentMessages: (replyId: string) => `agent:messages:${replyId}`,

  /** Rate limit: ratelimit:{ip}:{endpoint} */
  rateLimit: (ip: string, endpoint: string) => `ratelimit:${ip}:${endpoint}`,
} as const;

export const CacheTTL = {
  session: 86400,           // 24 hours
  conversations: 300,       // 5 minutes
  messages: 60,             // 1 minute
  agentReply: 3600,         // 1 hour
  agentMessages: 3600,      // 1 hour
} as const;

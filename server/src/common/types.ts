export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface JwtPayload {
  sub: string;
  username: string;
  role: string;
  jti: string;
  iat: number;
  exp: number;
}

export interface AgentMessagePayload {
  replyId: string;
  msg: {
    id?: string;
    content: string | Array<{ type: string; text?: string; thinking?: string }>;
    role?: string;
    sequence?: number;
    [key: string]: unknown;
  };
}

export interface AgentFinishedPayload {
  replyId: string;
}

export interface SSEEvent {
  type: string;
  [key: string]: unknown;
}

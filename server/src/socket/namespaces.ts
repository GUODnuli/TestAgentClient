/**
 * Socket.IO namespace definitions
 */
export const NAMESPACES = {
  /** Client (frontend) namespace */
  CLIENT: '/client',
  /** Agent (subprocess) namespace */
  AGENT: '/agent',
} as const;

export const CLIENT_EVENTS = {
  JOIN_CHAT_ROOM: 'joinChatRoom',
  LEAVE_CHAT_ROOM: 'leaveChatRoom',
  PUSH_REPLIES: 'pushReplies',
  PUSH_REPLYING_STATE: 'pushReplyingState',
  PUSH_FINISHED: 'pushFinished',
  PUSH_CANCELLED: 'pushCancelled',
} as const;

export const AGENT_EVENTS = {
  INTERRUPT: 'interrupt',
} as const;

export function chatRoom(conversationId: string): string {
  return `chat-${conversationId}`;
}

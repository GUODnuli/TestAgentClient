import { getSocketIO } from '../plugins/socket-io.js';
import { getLogger } from '../config/logger.js';

export class SocketManager {
  private get io() {
    return getSocketIO();
  }

  private get logger() {
    return getLogger();
  }

  private get clientNs() {
    return this.io.of('/client');
  }

  async broadcastMessage(conversationId: string, replyId: string, message: Record<string, unknown>): Promise<void> {
    const room = `chat-${conversationId}`;
    this.clientNs.to(room).emit('pushReplies', { replyId, message });
  }

  async broadcastReplyingState(state: Record<string, unknown>): Promise<void> {
    this.clientNs.emit('pushReplyingState', state);
  }

  async broadcastFinished(replyId: string): Promise<void> {
    this.clientNs.emit('pushFinished', { replyId });
  }

  async broadcastCancelled(replyId: string): Promise<void> {
    this.clientNs.emit('pushCancelled', { replyId });
  }

  async sendInterrupt(): Promise<void> {
    this.io.of('/agent').emit('interrupt', {});
  }
}

let _socketManager: SocketManager | null = null;

export function getSocketManager(): SocketManager {
  if (!_socketManager) {
    _socketManager = new SocketManager();
  }
  return _socketManager;
}

import { getSocketIO } from '../plugins/socket-io.js';
import { getLogger } from '../config/logger.js';
import { NAMESPACES, CLIENT_EVENTS, AGENT_EVENTS, chatRoom } from './namespaces.js';

export class SocketManager {
  private get io() {
    return getSocketIO();
  }

  private get logger() {
    return getLogger();
  }

  private get clientNs() {
    return this.io.of(NAMESPACES.CLIENT);
  }

  async broadcastMessage(conversationId: string, replyId: string, message: Record<string, unknown>): Promise<void> {
    const room = chatRoom(conversationId);
    this.clientNs.to(room).emit(CLIENT_EVENTS.PUSH_REPLIES, { replyId, message });
  }

  async broadcastReplyingState(state: Record<string, unknown>): Promise<void> {
    this.clientNs.emit(CLIENT_EVENTS.PUSH_REPLYING_STATE, state);
  }

  async broadcastFinished(replyId: string): Promise<void> {
    this.clientNs.emit(CLIENT_EVENTS.PUSH_FINISHED, { replyId });
  }

  async broadcastCancelled(replyId: string): Promise<void> {
    this.clientNs.emit(CLIENT_EVENTS.PUSH_CANCELLED, { replyId });
  }

  async sendInterrupt(): Promise<void> {
    this.io.of(NAMESPACES.AGENT).emit(AGENT_EVENTS.INTERRUPT, {});
  }
}

let _socketManager: SocketManager | null = null;

export function getSocketManager(): SocketManager {
  if (!_socketManager) {
    _socketManager = new SocketManager();
  }
  return _socketManager;
}

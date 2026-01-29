import type { FastifyReply } from 'fastify';

/**
 * Write SSE headers to a raw HTTP response
 */
export function writeSSEHeaders(reply: FastifyReply): void {
  reply.raw.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
}

/**
 * Write a single SSE event
 */
export function writeSSEEvent(reply: FastifyReply, eventType: string, data: unknown): void {
  const json = JSON.stringify(data);
  reply.raw.write(`event: ${eventType}\ndata: ${json}\n\n`);
}

/**
 * End the SSE stream
 */
export function endSSEStream(reply: FastifyReply): void {
  reply.raw.end();
}

/**
 * Stream an async generator as SSE events
 */
export async function streamSSE(
  reply: FastifyReply,
  generator: AsyncGenerator<Record<string, unknown>>
): Promise<void> {
  writeSSEHeaders(reply);

  try {
    for await (const event of generator) {
      const eventType = (event.type as string) || 'chunk';
      writeSSEEvent(reply, eventType, event);
    }
  } catch (err) {
    const errorData = { type: 'error', message: String(err) };
    writeSSEEvent(reply, 'error', errorData);
  } finally {
    endSSEStream(reply);
  }
}

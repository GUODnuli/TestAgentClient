/**
 * SSE Parser with proper chunk boundary handling.
 *
 * Standard SSE events are delimited by double newlines (\n\n).
 * When reading from a ReadableStream, chunk boundaries can split
 * an event mid-line. This parser buffers incomplete data and only
 * emits fully-received events.
 */
export class SSEParser {
  /**
   * @param {(event: { type: string, data: unknown }) => void} onEvent
   */
  constructor(onEvent) {
    /** @type {string} */
    this.buffer = ''
    /** @type {(event: { type: string, data: unknown }) => void} */
    this.onEvent = onEvent
  }

  /**
   * Feed a raw text chunk from the stream into the parser.
   * Complete events are parsed and dispatched via the onEvent callback.
   *
   * @param {string} chunk - raw text chunk from TextDecoder
   */
  feed(chunk) {
    this.buffer += chunk

    // SSE events are separated by blank lines (\n\n)
    const parts = this.buffer.split('\n\n')
    // The last element may be incomplete — keep it in the buffer
    this.buffer = parts.pop() ?? ''

    for (const part of parts) {
      if (!part.trim()) continue
      this._parseEventBlock(part)
    }
  }

  /**
   * Flush any remaining buffered data (call when the stream ends).
   */
  flush() {
    if (this.buffer.trim()) {
      this._parseEventBlock(this.buffer)
      this.buffer = ''
    }
  }

  /**
   * Parse a single SSE event block (lines between \n\n boundaries).
   *
   * Handles:
   *   event: <type>\ndata: <json>
   *   data: <json>  (type defaults to 'message')
   *
   * @param {string} block
   * @private
   */
  _parseEventBlock(block) {
    const lines = block.split('\n')
    let eventType = 'message'
    let dataLines = []

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        // Per SSE spec: remove at most one leading space after the colon
        const value = line.slice(5)
        dataLines.push(value.startsWith(' ') ? value.slice(1) : value)
      }
      // Ignore id:, retry:, comments (:), etc.
    }

    if (dataLines.length === 0) return

    const rawData = dataLines.join('\n')

    let parsed
    try {
      parsed = JSON.parse(rawData)
    } catch {
      // Not valid JSON — emit as raw string
      parsed = rawData
    }

    this.onEvent({ type: eventType, data: parsed })
  }
}

import { DefaultChatTransport, type ChatTransport, type UIMessage, type UIMessageChunk } from "ai";
import type { Detail } from "@/api";

// 只衔接官方事件前缀与游标后的流；消息还原完全交给 AI SDK。
export class ConversationTransport extends DefaultChatTransport<UIMessage> {
  private recovery: Detail["recovery"] = null;

  constructor(
    id: string,
    private snapshot: (signal?: AbortSignal) => Promise<Detail>,
    private initialize: (detail: Detail) => void,
  ) {
    super({
      api: `/api/conversations/${id}/chat`,
      prepareSendMessagesRequest: ({ id, messages }) => ({
        body: { id, trigger: "submit-message", messages: messages.slice(-1) },
      }),
      prepareReconnectToStreamRequest: () => ({
        api: `/api/conversations/${id}/chat/stream?run_id=${encodeURIComponent(this.recovery!.run_id)}&after=${this.recovery!.cursor}`,
      }),
    });
  }

  override async reconnectToStream(options: Parameters<ChatTransport<UIMessage>["reconnectToStream"]>[0]) {
    const detail = await this.snapshot(options.abortSignal);
    options.abortSignal?.throwIfAborted();
    this.recovery = detail.recovery;
    const recovery = this.recovery;
    this.initialize(detail);
    if (!recovery) return null;
    const connect = () => super.reconnectToStream(options);
    let reader: ReadableStreamDefaultReader<UIMessageChunk> | undefined;
    async function* events() {
      try {
        yield* recovery!.events;
        yield {
          type: "data-progress", transient: true,
          data: { runId: recovery!.run_id, cursor: recovery!.cursor, restored: true },
        } satisfies UIMessageChunk;
        const tail = await connect();
        reader = tail?.getReader();
        if (reader) {
          while (true) {
            const next = await reader.read();
            if (next.done) break;
            yield next.value;
          }
        }
      } finally {
        await reader?.cancel();
      }
    }
    const iterator = events();
    return new ReadableStream<UIMessageChunk>({
      async pull(controller) {
        try {
          const next = await iterator.next();
          if (next.done) controller.close();
          else controller.enqueue(next.value);
        } catch (error) {
          controller.error(error);
        }
      },
      async cancel() {
        await reader?.cancel();
        await iterator.return();
      },
    });
  }
}

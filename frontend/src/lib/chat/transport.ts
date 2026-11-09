import { DefaultChatTransport, type ChatTransport, type UIMessage } from 'ai';
import { apiUrl, type Detail } from '#lib/api.js';

// 重连时从本轮基线重放同一条流，消息合并仍由官方 AI SDK 完成。
export class ConversationTransport extends DefaultChatTransport<UIMessage> {
	private recovery: Detail['recovery'] = null;

	constructor(
		id: string,
		private snapshot: (signal?: AbortSignal) => Promise<Detail>,
		private initialize: (detail: Detail) => void
	) {
		super({
			api: apiUrl(`/conversations/${id}/chat`),
			prepareSendMessagesRequest: ({ id, messages }) => ({
				body: { id, trigger: 'submit-message', messages: messages.slice(-1) }
			}),
			prepareReconnectToStreamRequest: () => ({
				api: apiUrl(
					`/conversations/${id}/chat/stream?run_id=${encodeURIComponent(this.recovery!.run_id)}`
				)
			})
		});
	}

	override async reconnectToStream(
		options: Parameters<ChatTransport<UIMessage>['reconnectToStream']>[0]
	) {
		const detail = await this.snapshot(options.abortSignal);
		options.abortSignal?.throwIfAborted();
		this.recovery = detail.recovery;
		this.initialize(detail);
		return this.recovery ? super.reconnectToStream(options) : null;
	}
}

import type { UIMessage } from 'ai';
import { Chat } from '@ai-sdk/svelte';
import { api, ApiError, type Detail } from '#lib/api.js';
import { cacheConversation, forgetConversation, type LoadedConversation } from './cache';
import { ConversationTransport } from './transport';

// A mounted conversation owns its subscription; the server owns the running reply.
export class Conversation {
	detail: Detail;
	recovering = $state(false);
	preview: Detail['messages'];
	readonly chat: Chat;
	private target: Detail['recovery'] = null;
	private timer: ReturnType<typeof setTimeout> | undefined;

	constructor(loaded: LoadedConversation, changed: () => void) {
		this.detail = $state.raw(loaded.detail);
		this.preview = $state.raw(loaded.detail.messages);
		this.recovering = loaded.cached || Boolean(loaded.detail.recovery);
		this.chat = new Chat({
			id: this.detail.summary.id,
			messages: loaded.detail.messages,
			transport: new ConversationTransport(
				this.detail.summary.id,
				async (signal) => {
					if (!this.target)
						this.preview = $state.snapshot(this.chat.messages as unknown) as UIMessage[];
					this.recovering = true;
					return this.refresh(signal);
				},
				(saved) => {
					this.target = saved.recovery;
					this.chat.messages = saved.recovery?.messages ?? saved.messages;
					if (!saved.recovery) {
						this.recovering = false;
						this.save();
					}
				}
			),
			onData: (part) => {
				if (part.type !== 'data-progress') return;
				if (this.target) {
					const { runId, cursor } = part.data as { runId: string; cursor: string };
					if (runId !== this.target.run_id || this.target.cursor === null) return;
					if (Number(cursor) < Number(this.target.cursor)) return;
					this.target = null;
				}
				this.recovering = false;
				this.timer ??= setTimeout(() => this.save(), 250);
			},
			onError: (error) => {
				if (error.message === '回复正在恢复，请重新同步') {
					queueMicrotask(() => void this.synchronize());
					return;
				}
				this.target = null;
				this.recovering = false;
				void this.refresh()
					.then(() => this.save())
					.catch(() => {});
				changed();
			},
			onFinish: ({ isAbort, isDisconnect }) => {
				if (isAbort || isDisconnect) return;
				this.target = null;
				this.recovering = false;
				void this.refresh()
					.then(() => this.save())
					.catch(() => {});
				changed();
			}
		});
	}

	get messages() {
		return this.recovering ? this.preview : this.chat.messages;
	}

	async refresh(signal?: AbortSignal) {
		try {
			return (this.detail = await api<Detail>(`/conversations/${this.chat.id}`, { signal }));
		} catch (error) {
			if (error instanceof ApiError && error.status === 404) {
				this.preview = [];
				this.target = null;
				this.chat.messages = [];
				this.recovering = false;
				await forgetConversation(this.chat.id);
			}
			throw error;
		}
	}

	save() {
		clearTimeout(this.timer);
		this.timer = undefined;
		if (!this.recovering)
			void cacheConversation(
				this.detail,
				$state.snapshot(this.chat.messages as unknown) as UIMessage[]
			);
	}

	async synchronize() {
		await this.chat.stop();
		await this.chat.resumeStream();
	}

	mount() {
		if (this.recovering) void this.chat.resumeStream();
		else this.save();
		return () => {
			this.save();
			void this.chat.stop();
		};
	}

	reconnect() {
		if (
			document.visibilityState === 'visible' &&
			this.chat.status !== 'streaming' &&
			this.chat.status !== 'submitted'
		)
			void this.synchronize();
	}
}

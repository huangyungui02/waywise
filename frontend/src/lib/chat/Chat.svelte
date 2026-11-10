<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { invalidate } from '$app/navigation';
	import { LoaderCircle } from '@lucide/svelte';
	import { page } from '$app/state';
	import { Conversation } from '#lib/chat/conversation.svelte.js';
	import type { LoadedConversation } from '#lib/chat/cache.js';
	import { api } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import Message from './Message.svelte';
	import ChatViewport from './ChatViewport.svelte';
	import Composer from './Composer.svelte';
	import TravelForm from './TravelForm.svelte';
	import TripCard from './TripCard.svelte';
	import ProductList from './ProductList.svelte';
	import { travelPrompt } from './travel-brief';
	let { loaded }: { loaded: LoadedConversation } = $props();
	const conversation = new Conversation(
		untrack(() => loaded),
		() => {
			void invalidate('app:conversations');
		}
	);
	let values = $state<Record<string, string>>({});
	let confirming = $state(false);
	let actionError = $state('');
	let viewport: ChatViewport;
	let running = $derived(
		(conversation.recovering && conversation.chat.status !== 'error') ||
			['submitted', 'streaming'].includes(conversation.chat.status) ||
			conversation.detail.summary.outcome === 'running'
	);
	let thinking = $derived(
		conversation.chat.status === 'streaming' &&
			conversation.messages
				.at(-1)
				?.parts.some((part) => part.type === 'reasoning' && part.state === 'streaming')
	);
	let messages = $derived.by(() => {
		const result: typeof conversation.messages = [];
		for (const message of conversation.messages) {
			const previous = result.at(-1);
			if (previous?.role === 'assistant' && message.role === 'assistant')
				result[result.length - 1] = { ...previous, parts: [...previous.parts, ...message.parts] };
			else result.push(message);
		}
		return result;
	});
	onMount(() => {
		const prompt = page.state.prompt;
		if (prompt && !loaded.detail.messages.length)
			void conversation.chat.sendMessage({ text: prompt });
		return conversation.mount();
	});
	async function confirm(id: string) {
		confirming = true;
		actionError = '';
		try {
			await api(
				`/conversations/${conversation.chat.id}/proposals/${encodeURIComponent(id)}/confirm`,
				{ method: 'POST' }
			);
			await conversation.refresh();
			viewport.latest();
			await conversation.chat.sendMessage({
				text: '已确认卡片中的交通和住宿方案，请继续规划每日行程。'
			});
		} catch (cause) {
			actionError = cause instanceof Error ? cause.message : String(cause);
		} finally {
			confirming = false;
		}
	}
	async function stop() {
		try {
			await api(`/conversations/${conversation.chat.id}/chat/stop`, { method: 'POST' });
			await conversation.synchronize();
		} catch (cause) {
			actionError = String(cause);
		}
	}
</script>

<svelte:window
	ononline={() => {
		if (document.visibilityState === 'visible') void conversation.synchronize();
	}}
	onpagehide={() => conversation.save()}
/>
<svelte:document onvisibilitychange={() => conversation.reconnect()} />
<div class="relative flex min-h-0 min-w-0 flex-1 flex-col">
	<ProductList
		products={conversation.detail.products ?? []}
		onrefresh={async () => {
			await conversation.refresh();
			conversation.save();
		}}
		onremove={async (id) => {
			await api(`/conversations/${conversation.chat.id}/products/${id}`, { method: 'DELETE' });
			await conversation.refresh();
			conversation.save();
		}}
	/>
	<ChatViewport bind:this={viewport}>
		{#if !messages.length}<TravelForm bind:values />{/if}
		{#each messages as message (message.id)}<Message
				{message}
				detail={conversation.detail}
				busy={running || confirming}
				onconfirm={confirm}
			/>{/each}
		{#if conversation.detail.trip && !conversation.detail.confirmed_id}<section
				aria-label="交通与住宿方案"
				class="rounded-xl bg-card/70 p-4 shadow-xs"
			>
				<TripCard trip={conversation.detail.trip} status="confirmed" />
			</section>{/if}
		{#if thinking}<p role="status" class="flex items-center gap-2 text-xs text-muted-foreground">
				<LoaderCircle class="size-3 animate-spin" />正在思考…
			</p>{/if}
		{#if conversation.chat.error || actionError}
			<Alert.Root variant="destructive"
				><Alert.Description
					>{actionError ||
						conversation.chat.error?.message}。已保存的记录可重新打开查看，或继续发送消息。<Button
						variant="link"
						onclick={() => conversation.synchronize()}>重新同步</Button
					></Alert.Description
				></Alert.Root
			>
		{/if}
		{#if ['cancelled', 'failed'].includes(conversation.detail.summary.outcome) && !running && !conversation.chat.error}<Alert.Root
				><Alert.Description>上次回复未完成，已保留可恢复的记录，可以继续咨询。</Alert.Description
				></Alert.Root
			>{/if}
	</ChatViewport>
	<Composer
		busy={running || confirming}
		hasFormValues={!messages.length && Object.values(values).some((value) => value?.trim())}
		onstop={stop}
		onsend={async (text) => {
			const input = messages.length ? text : travelPrompt(values, text);
			viewport.latest();
			await conversation.chat.sendMessage({ text: input });
		}}
	/>
</div>

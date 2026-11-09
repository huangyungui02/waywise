<script lang="ts">
	import { ArrowUp, Square, LoaderCircle } from '@lucide/svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	let {
		busy,
		hasFormValues = false,
		onsend,
		onstop
	}: {
		busy: boolean;
		hasFormValues?: boolean;
		onsend: (text: string) => void | Promise<void>;
		onstop?: () => void;
	} = $props();
	let text = $state('');
	let canSend = $derived(Boolean(text.trim() || hasFormValues));
	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!canSend || busy) return;
		const input = text.trim();
		text = '';
		void onsend(input);
	}
</script>

<div
	class="pointer-events-none absolute inset-x-0 bottom-0 z-10 px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-8 sm:pb-6"
	{@attach (node) => {
		const parent = node.parentElement!;
		const observer = new ResizeObserver(() => {
			parent.style.setProperty('--composer-height', `${node.getBoundingClientRect().height}px`);
		});
		observer.observe(node);
		return () => {
			observer.disconnect();
			parent.style.removeProperty('--composer-height');
		};
	}}
>
	<form
		onsubmit={submit}
		class="composer liquid-glass pointer-events-auto mx-auto flex max-w-2xl items-end gap-2 rounded-[2rem] p-2 pl-5"
	>
		<Textarea
			aria-label="旅行需求"
			placeholder="写下关于这次旅行的任何想法…"
			rows={1}
			bind:value={text}
			onkeydown={(event) => {
				if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
					event.preventDefault();
					event.currentTarget.form?.requestSubmit();
				}
			}}
			class="max-h-32 min-h-6 flex-1 resize-none border-0 bg-transparent py-1 shadow-none focus-visible:border-transparent focus-visible:ring-0"
		/>
		{#if busy && onstop}
			<Button
				type="button"
				size="icon"
				class="size-9 shrink-0 rounded-full"
				variant="ghost"
				onclick={onstop}
				aria-label="停止"><Square /></Button
			>
		{:else}
			<Button
				type="submit"
				size="icon"
				class="size-9 shrink-0 rounded-full"
				disabled={!canSend || busy}
				aria-label="发送"
			>
				{#if busy}<LoaderCircle class="animate-spin" />{:else}<ArrowUp />{/if}
			</Button>
		{/if}
	</form>
</div>

<style>
	.composer {
		transition:
			box-shadow 180ms ease,
			border-color 180ms ease;
	}
	.composer:focus-within {
		border-color: color-mix(in srgb, var(--primary) 25%, white);
		box-shadow:
			0 12px 40px -12px rgb(25 56 46 / 22%),
			inset 0 1px 0 rgb(255 255 255 / 95%);
	}
</style>

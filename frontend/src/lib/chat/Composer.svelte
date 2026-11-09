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
		class="liquid-glass pointer-events-auto mx-auto flex max-w-2xl items-center gap-2 rounded-[2rem] p-2 pl-5 transition-[border-color,box-shadow] focus-within:border-primary/30"
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
			class="max-h-32 min-h-9 flex-1 resize-none border-0 bg-transparent py-2 leading-5 shadow-none focus-visible:border-transparent focus-visible:ring-0"
		/>
		{#if busy && onstop}
			<Button
				type="button"
				size="icon"
				class="size-9 shrink-0 self-end rounded-full"
				variant="ghost"
				onclick={onstop}
				aria-label="停止"><Square /></Button
			>
		{:else}
			<Button
				type="submit"
				size="icon"
				class="size-9 shrink-0 self-end rounded-full"
				disabled={!canSend || busy}
				aria-label="发送"
			>
				{#if busy}<LoaderCircle class="animate-spin" />{:else}<ArrowUp />{/if}
			</Button>
		{/if}
	</form>
</div>

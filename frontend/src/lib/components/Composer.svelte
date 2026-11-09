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

<div class="shrink-0 px-4 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-8 sm:pb-6">
	<form
		onsubmit={submit}
		class="composer pure-capsule mx-auto flex max-w-2xl items-center gap-2 rounded-full p-1.5 pl-4 focus-within:shadow-[0_12px_40px_-6px_rgba(25,35,28,0.1)]"
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
		border: 1px solid #e0e6da;
		background: #fff;
		box-shadow: 0 6px 24px -12px rgb(31 56 40 / 16%);
	}
	.composer:focus-within {
		border-color: #b5c7b1;
		box-shadow: 0 8px 28px -12px rgb(31 56 40 / 18%);
	}
</style>

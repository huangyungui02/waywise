<script lang="ts">
	import type { Snippet } from 'svelte';
	import { ArrowDown } from '@lucide/svelte';
	import { Button } from '#lib/components/ui/button/index.js';

	let { children }: { children: Snippet } = $props();
	let scroller: HTMLElement;
	let following = true;
	let lastTop = 0;
	let atBottom = $state(true);

	export function latest() {
		following = true;
		atBottom = true;
		if (scroller) {
			scroller.scrollTop = scroller.scrollHeight;
			lastTop = scroller.scrollTop;
		}
	}

	// Follow rendered geometry without subscribing to streaming message content.
	function follow(node: HTMLElement) {
		const observer = new ResizeObserver(() => {
			if (following) latest();
		});
		observer.observe(node);
		latest();
		return () => observer.disconnect();
	}
</script>

<div
	role="region"
	aria-label="聊天记录"
	{@attach (node) => {
		scroller = node;
	}}
	onwheel={(event) => {
		if (event.deltaY < 0) following = false;
	}}
	ontouchmove={() => (following = false)}
	onscroll={() => {
		const bottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 80;
		if (scroller.scrollTop < lastTop) following = false;
		else if (scroller.scrollTop > lastTop && bottom) following = true;
		lastTop = scroller.scrollTop;
		atBottom = bottom;
	}}
	class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 sm:px-8"
>
	<div {@attach follow} class="mx-auto flex max-w-2xl flex-col gap-6 py-6 sm:py-8">
		{@render children()}
	</div>
</div>
{#if !atBottom}
	<Button
		variant="outline"
		size="icon"
		aria-label="回到最新消息"
		class="absolute bottom-24 left-1/2 size-8 -translate-x-1/2 rounded-full shadow-md"
		onclick={latest}><ArrowDown /></Button
	>
{/if}

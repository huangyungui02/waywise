<script lang="ts">
	import { isToolUIPart, type UIMessage } from 'ai';
	import type { Detail, Trip } from '#lib/api.js';
	import ToolActivity from './ToolActivity.svelte';
	import Markdown from './Markdown.svelte';
	import TripCard from './TripCard.svelte';
	let {
		message,
		detail,
		busy,
		onconfirm
	}: { message: UIMessage; detail: Detail; busy: boolean; onconfirm: (id: string) => void } =
		$props();
	type Tool = Extract<UIMessage['parts'][number], { toolCallId: string }>;
	type Group =
		| { key: string; type: 'text'; text: string }
		| { key: string; type: 'proposal'; trip: Trip; id: string }
		| { key: string; type: 'tools'; tools: Tool[] };
	let groups = $derived.by(() => {
		const result: Group[] = [];
		for (const [i, part] of message.parts.entries()) {
			if (part.type === 'text') result.push({ key: `text-${i}`, type: 'text', text: part.text });
			else if (isToolUIPart(part)) {
				const name = part.type === 'dynamic-tool' ? part.toolName : part.type.slice(5);
				if (name === 'present_trip' && part.state === 'output-available') {
					const input = part.input as Trip | { trip: Trip };
					result.push({
						key: part.toolCallId,
						type: 'proposal',
						id: part.toolCallId,
						trip: 'trip' in input ? input.trip : input
					});
				} else {
					const previous = result.at(-1);
					if (previous?.type === 'tools') previous.tools.push(part);
					else result.push({ key: part.toolCallId, type: 'tools', tools: [part] });
				}
			}
		}
		return result;
	});
</script>

<article class={message.role === 'user' ? 'flex justify-end' : ''}>
	{#if message.role === 'user'}
		<div class="max-w-[92%] sm:max-w-[78%]">
			{#each message.parts as part, i (`${message.id}-${i}`)}
				{#if part.type === 'text'}
					<p
						class="rounded-xl bg-primary px-4 py-2.5 text-sm break-words whitespace-pre-wrap text-primary-foreground selection:bg-[#d9eee3] selection:text-[#19382e]"
					>
						{part.text}
					</p>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="flex min-w-0 flex-col gap-2">
			{#each groups as group (group.key)}
				{#if group.type === 'text'}<Markdown text={group.text} />
				{:else if group.type === 'proposal'}
					<section aria-label="交通与住宿方案" class="pure-capsule p-4">
						<TripCard
							trip={group.trip}
							status={detail.pending_id === group.id
								? 'pending'
								: detail.confirmed_id === group.id
									? 'confirmed'
									: 'outdated'}
							disabled={busy}
							onconfirm={() => onconfirm(group.id)}
						/>
					</section>
				{:else}
					<ToolActivity tools={group.tools} />
				{/if}
			{/each}
		</div>
	{/if}
</article>

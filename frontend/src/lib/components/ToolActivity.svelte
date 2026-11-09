<script lang="ts">
	import type { ToolUIPart, DynamicToolUIPart } from 'ai';
	import { Check, CircleAlert, LoaderCircle } from '@lucide/svelte';
	let { tools }: { tools: (ToolUIPart | DynamicToolUIPart)[] } = $props();
	let count = $derived(tools.length);
	const names: Record<string, string> = {
		current_time: '核对北京时间',
		present_trip: '整理交通和住宿方案',
		confirm_trip: '检查并保存交通和住宿',
		load_capability: '准备旅行查询',
		read_file: '查阅旅行查询说明',
		call_flyai: '查询交通与酒店',
		web_search: '搜索旅行资讯',
		run_command: '查询交通与酒店'
	};
	function scroll(node: HTMLElement) {
		if (count > 1) node.scrollTop = node.scrollHeight;
	}
</script>

<div
	{@attach scroll}
	role="region"
	aria-label="行程查询记录"
	class={[
		'my-1.5 flex flex-col gap-1 rounded-xl',
		count > 1 && 'max-h-36 overflow-y-auto overscroll-contain bg-muted/20 p-2.5'
	]}
>
	{#each tools as part (part.toolCallId)}
		{@const name = part.type === 'dynamic-tool' ? part.toolName : part.type.slice(5)}
		<div class="flex items-center gap-2 px-2 py-1 text-xs text-muted-foreground">
			{#if part.state === 'output-error'}
				<CircleAlert aria-hidden="true" class="size-3 shrink-0 text-destructive" />
			{:else if part.state === 'output-available'}
				<Check aria-hidden="true" class="size-3 shrink-0 text-primary" />
			{:else}
				<LoaderCircle
					aria-hidden="true"
					class="size-3 shrink-0 animate-spin text-primary motion-reduce:animate-none"
				/>
			{/if}
			<span>{names[name] ?? (name.startsWith('amap') ? '查询地点与路线' : name)}</span><span
				>{part.state === 'output-error'
					? '未完成'
					: part.state === 'output-available'
						? '已完成'
						: '进行中'}</span
			>
		</div>
	{/each}
</div>

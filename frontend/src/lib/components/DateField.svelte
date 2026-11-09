<script lang="ts">
	import { parseDate } from '@internationalized/date';
	import { Calendar } from '#lib/components/ui/calendar/index.js';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	let {
		label,
		value = $bindable(''),
		earliest = ''
	}: { label: string; value?: string; earliest?: string } = $props();
	let open = $state(false);
	let selected = $derived(value ? parseDate(value) : undefined);
</script>

<div class="flex min-w-0 flex-col gap-2">
	<span class="text-xs text-muted-foreground">{label}</span>
	<Popover.Root bind:open>
		<Popover.Trigger class="pure-field text-left" aria-label={label}
			>{selected ? `${selected.month}月${selected.day}日` : '选择日期'}</Popover.Trigger
		>
		<Popover.Content role="dialog" class="w-auto p-2" aria-label={label} align="start">
			<Calendar
				type="single"
				value={selected}
				locale="zh-CN"
				captionLayout="dropdown"
				minValue={earliest ? parseDate(earliest) : undefined}
				onValueChange={(date) => {
					value = date?.toString() ?? '';
					open = false;
				}}
			/>
			<Button
				variant="ghost"
				size="sm"
				class="w-full"
				onclick={() => {
					value = '';
					open = false;
				}}>清除日期</Button
			>
		</Popover.Content>
	</Popover.Root>
</div>

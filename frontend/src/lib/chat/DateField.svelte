<script lang="ts">
	import * as Field from '#lib/components/ui/field/index.js';
	import { parseDate } from '@internationalized/date';
	import { Calendar } from '#lib/components/ui/calendar/index.js';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import { Button, buttonVariants } from '#lib/components/ui/button/index.js';
	let {
		label,
		value = $bindable(''),
		earliest = ''
	}: { label: string; value?: string; earliest?: string } = $props();
	let open = $state(false);
	let selected = $derived(value ? parseDate(value) : undefined);
</script>

<Field.Field>
	<Field.Label for={label}>{label}</Field.Label>
	<Popover.Root bind:open>
		<Popover.Trigger
			id={label}
			class={buttonVariants({
				variant: 'outline',
				class: ['w-full justify-start font-normal', !selected && 'text-muted-foreground']
			})}
			aria-label={label}
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
</Field.Field>

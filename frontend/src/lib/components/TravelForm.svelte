<script lang="ts">
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import * as ToggleGroup from '#lib/components/ui/toggle-group/index.js';
	import DateField from './DateField.svelte';
	let { values = $bindable<Record<string, string>>({}) }: { values?: Record<string, string> } =
		$props();
	function departure(value: string) {
		values['出发日期'] = value;
		if (value && values['返回日期'] < value) values['返回日期'] = '';
	}
</script>

<section aria-label="旅行基本信息" class="travel-form p-5 sm:p-8">
	<h2 class="font-serif text-2xl font-medium sm:text-3xl">这次，想去哪里？</h2>
	<p class="mt-2 mb-7 text-xs text-muted-foreground">
		填下已经确定的安排，剩下的我们一起慢慢计划。
	</p>
	<Field.Group>
		<div class="grid grid-cols-2 gap-4">
			{#each [{ key: '出发城市', label: '出发地', placeholder: '从哪里出发' }, { key: '目的城市', label: '目的地', placeholder: '想去哪里' }] as item (item.key)}
				<Field.Field
					><Field.Label for={item.key}>{item.label}</Field.Label><Input
						id={item.key}
						bind:value={values[item.key]}
						placeholder={item.placeholder}
						class="travel-input"
					/></Field.Field
				>
			{/each}
		</div>
		<div class="grid grid-cols-2 gap-4">
			<DateField label="出发日期" bind:value={() => values['出发日期'] ?? '', departure} />
			<DateField
				label="返回日期"
				bind:value={() => values['返回日期'] ?? '', (v) => (values['返回日期'] = v)}
				earliest={values['出发日期']}
			/>
		</div>
		<div class="grid gap-4 border-t border-primary/5 pt-5 sm:grid-cols-2">
			<div class="travel-panel flex flex-col gap-3">
				<Field.Field
					><Field.Label for="travelers">同行人数</Field.Label><Input
						class="travel-input"
						id="travelers"
						aria-label="同行人数"
						type="number"
						min="1"
						step="1"
						placeholder="几个人"
						bind:value={
							() => values['同行人数'] ?? '',
							(v) => (values['同行人数'] = v == null ? '' : String(v))
						}
					/></Field.Field
				>
				<Field.Set
					><Field.Legend class="sr-only">同行情况</Field.Legend>
					<div class="flex gap-4">
						{#each ['老人', '小孩'] as label (label)}
							<label class="flex items-center gap-2 text-xs"
								><Checkbox
									checked={values[`${label}同行`] === '有'}
									onCheckedChange={(checked) => (values[`${label}同行`] = checked ? '有' : '')}
								/>有{label}</label
							>
						{/each}
					</div></Field.Set
				>
			</div>
			<div class="travel-panel flex flex-col gap-3">
				<Field.Field
					><Field.Label for="budget">旅行预算</Field.Label><Input
						class="travel-input"
						id="budget"
						aria-label="预算"
						type="number"
						min="0"
						placeholder="预计花费"
						bind:value={
							() => values['预算金额'] ?? '',
							(v) => {
								values['预算金额'] = v == null ? '' : String(v);
								values['预算口径'] ||= '总共';
							}
						}
					/></Field.Field
				>
				<Field.Field
					><Field.Label class="sr-only">预算口径</Field.Label><ToggleGroup.Root
						type="single"
						aria-label="预算口径"
						spacing={1}
						size="sm"
						class="budget-options"
						value={values['预算口径'] || '总共'}
						onValueChange={(v) => {
							if (v) values['预算口径'] = v;
						}}
						><ToggleGroup.Item value="人均">人均</ToggleGroup.Item><ToggleGroup.Item value="总共"
							>总共</ToggleGroup.Item
						></ToggleGroup.Root
					></Field.Field
				>
			</div>
		</div>
	</Field.Group>
</section>

<style>
	.travel-form {
		position: relative;
		border: 0;
		border-radius: 20px;
		background: #fff;
		box-shadow: 0 12px 48px -24px rgb(31 56 40 / 12%);
	}
	.travel-form :global([data-slot='field-label']),
	.travel-form :global([data-slot='popover-trigger']) {
		font-weight: 500;
	}
	.travel-form :global([data-slot='field-label']) {
		font-size: 12px;
		color: #465b4c;
	}
	.travel-form :global([data-slot='input']),
	.travel-form :global(.pure-field) {
		height: 44px;
		border: 1px solid #e6e8e2;
		border-radius: 10px;
		padding-inline: 14px;
		background: #f6f7f3;
		color: #253b2d;
		box-shadow: none;
		transition:
			border-color 150ms,
			background-color 150ms;
	}
	.travel-form :global(input::placeholder) {
		color: #859084;
	}
	.travel-form :global([data-slot='input']:hover),
	.travel-form :global(.pure-field:hover) {
		border-color: #b8c7b5;
	}
	.travel-form :global([data-slot='input']:focus-visible),
	.travel-form :global(.pure-field:focus-visible) {
		border-color: #6d8d76;
		background: #fff;
		box-shadow: none;
		outline: none;
	}
	.travel-form :global([data-slot='checkbox']) {
		border: 1px solid #bac9b5;
		background: #fff;
		box-shadow: none;
	}
	.travel-form :global([data-slot='checkbox'][data-state='checked']) {
		border-color: var(--primary);
		background: var(--primary);
	}
	.travel-form :global(.budget-options) {
		display: inline-grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		align-self: flex-start;
		width: 144px;
		gap: 2px;
		padding: 3px;
		border-radius: 10px;
		background: #f0f2eb;
	}
	.travel-form :global([data-slot='toggle-group-item']) {
		width: 100%;
		height: 30px;
		border-radius: 7px;
		color: #72806f;
		font-size: 12px;
		font-weight: 400;
	}
	.travel-form :global([data-slot='toggle-group-item'][data-state='on']) {
		background: #fff;
		color: var(--primary);
		font-weight: 500;
		box-shadow: 0 1px 3px rgb(30 55 35 / 8%);
	}
</style>

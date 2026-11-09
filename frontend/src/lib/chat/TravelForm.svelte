<script lang="ts">
	import * as Card from '#lib/components/ui/card/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import DateField from './DateField.svelte';
	let { values = $bindable<Record<string, string>>({}) }: { values?: Record<string, string> } =
		$props();
	function departure(value: string) {
		values['出发日期'] = value;
		if (value && values['返回日期'] < value) values['返回日期'] = '';
	}
</script>

<Card.Root role="region" aria-label="旅行基本信息">
	<Card.Header>
		<Card.Title role="heading" aria-level={2} class="font-serif text-2xl sm:text-3xl"
			>这次，想去哪里？</Card.Title
		>
		<Card.Description>填下已经确定的安排，剩下的我们一起慢慢计划。</Card.Description>
	</Card.Header>
	<Card.Content>
		<Field.Group>
			<div class="grid grid-cols-2 gap-4">
				{#each [{ key: '出发城市', label: '出发地', placeholder: '从哪里出发' }, { key: '目的城市', label: '目的地', placeholder: '想去哪里' }] as item (item.key)}
					<Field.Field
						><Field.Label for={item.key}>{item.label}</Field.Label><Input
							id={item.key}
							bind:value={values[item.key]}
							placeholder={item.placeholder}
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
			<div class="grid gap-4 sm:grid-cols-2">
				<div class="flex flex-col gap-3">
					<Field.Field
						><Field.Label for="travelers">同行人数</Field.Label><Input
							id="travelers"
							aria-label="同行人数"
							type="number"
							class="[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
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
								<label class="flex items-center gap-2 text-xs text-muted-foreground"
									><Checkbox
										checked={values[`${label}同行`] === '有'}
										onCheckedChange={(checked) => (values[`${label}同行`] = checked ? '有' : '')}
									/>有{label}</label
								>
							{/each}
						</div></Field.Set
					>
				</div>
				<div class="flex flex-col gap-3">
					<Field.Field
						><Field.Label for="budget">旅行预算</Field.Label><Input
							id="budget"
							aria-label="预算"
							type="number"
							class="[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
							min="0"
							placeholder={values['预算口径'] === '人均' ? '每人预算（元）' : '总预算（元）'}
							bind:value={
								() => values['预算金额'] ?? '',
								(v) => {
									values['预算金额'] = v == null ? '' : String(v);
									values['预算口径'] ||= '总共';
								}
							}
						/></Field.Field
					>
					<label class="flex items-center gap-2 text-xs text-muted-foreground">
						<Checkbox
							checked={values['预算口径'] === '人均'}
							onCheckedChange={(checked) => (values['预算口径'] = checked ? '人均' : '总共')}
						/>人均预算
					</label>
				</div>
			</div>
		</Field.Group>
	</Card.Content>
</Card.Root>

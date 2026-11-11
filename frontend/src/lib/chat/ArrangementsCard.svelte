<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import type { TravelArrangements } from '#lib/api.js';
	let {
		arrangements,
		status,
		disabled = false,
		onconfirm
	}: {
		arrangements: TravelArrangements;
		status: 'pending' | 'confirmed' | 'outdated';
		disabled?: boolean;
		onconfirm?: () => void;
	} = $props();
	let showNumber = $derived(arrangements.transports.some((leg) => Boolean(leg.number)));
</script>

<div class="flex min-w-0 flex-col gap-4">
	<div class="flex items-center justify-between">
		<h3 class="font-serif text-sm">交通与住宿</h3>
		<Badge variant="secondary"
			>{status === 'pending' ? '待确认' : status === 'confirmed' ? '已确认方案' : '已更新'}</Badge
		>
	</div>
	<p class="text-xs text-muted-foreground">
		共 {arrangements.transports.length} 段交通。如需调整，在聊天中告诉我即可重新确认。
	</p>
	<div class="min-w-0 overflow-hidden rounded-lg border">
		<Table.Root aria-label="交通安排">
			<Table.Header>
				<Table.Row>
					{#each ['序号', '出行方式', ...(showNumber ? ['车次'] : []), '出发地点', '到达地点', '出发时间', '到达时间', '预订状态'] as heading (heading)}
						<Table.Head scope="col">{heading}</Table.Head>
					{/each}
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each arrangements.transports as leg, index (`${leg.departure_time}-${leg.departure_station}`)}
					<Table.Row>
						<Table.Cell>{index + 1}</Table.Cell>
						<Table.Cell
							>{{
								train: '火车',
								flight: '飞机',
								bus: '大巴',
								drive: '自驾',
								taxi: '打车',
								ferry: '轮渡'
							}[leg.type]}</Table.Cell
						>
						{#if showNumber}<Table.Cell>{leg.number ?? ''}</Table.Cell>{/if}
						<Table.Cell class="max-w-56 min-w-36 whitespace-normal"
							>{leg.departure_station}</Table.Cell
						>
						<Table.Cell class="max-w-56 min-w-36 whitespace-normal"
							>{leg.arrival_station}</Table.Cell
						>
						<Table.Cell
							><time datetime={leg.departure_time}
								>{leg.departure_time.slice(0, 10)}<br />{leg.departure_time.slice(11, 16)}</time
							></Table.Cell
						>
						<Table.Cell
							><time datetime={leg.arrival_time}
								>{leg.arrival_time.slice(0, 10)}<br />{leg.arrival_time.slice(11, 16)}</time
							></Table.Cell
						>
						<Table.Cell>
							{#if leg.type !== 'drive'}
								{#if leg.purchased}已预订
								{:else if leg.purchase_url}<a
										class="underline underline-offset-4"
										href={leg.purchase_url}
										target="_blank"
										rel="noreferrer">点击预订</a
									>{/if}
							{/if}
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
	<p class="text-xs text-muted-foreground sm:hidden">左右滑动表格查看完整安排</p>
	{#if arrangements.stays.length}
		<div class="min-w-0 overflow-hidden rounded-lg border">
			<Table.Root aria-label="住宿安排">
				<Table.Header>
					<Table.Row>
						{#each ['酒店', '城市', '地址', '入住日期', '退房日期', '预订状态'] as heading (heading)}
							<Table.Head scope="col">{heading}</Table.Head>
						{/each}
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each arrangements.stays as stay (`${stay.hotel}-${stay.check_in}`)}
						<Table.Row>
							<Table.Cell class="max-w-48 min-w-32 whitespace-normal">{stay.hotel}</Table.Cell>
							<Table.Cell>{stay.city}</Table.Cell>
							<Table.Cell class="max-w-64 min-w-40 whitespace-normal">{stay.address}</Table.Cell>
							<Table.Cell>{stay.check_in}</Table.Cell>
							<Table.Cell>{stay.check_out}</Table.Cell>
							<Table.Cell>
								{#if stay.booked}已预订
								{:else if stay.purchase_url}<a
										class="underline underline-offset-4"
										href={stay.purchase_url}
										target="_blank"
										rel="noreferrer">点击预订</a
									>{/if}
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{:else}<p class="text-xs text-muted-foreground">本方案无酒店住宿。</p>{/if}
	{#if status === 'pending'}<Button {disabled} onclick={onconfirm}>确认方案</Button>
		<p class="text-xs text-muted-foreground">想调整交通或酒店？直接在下方告诉我。</p>{/if}
	<p class="text-xs text-muted-foreground">
		确认方案不代表已经购买，请前往预订页面自行核对并支付。
	</p>
</div>

<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import type { Trip } from '#lib/api.js';
	let {
		trip,
		status,
		disabled = false,
		onconfirm
	}: {
		trip: Trip;
		status: 'pending' | 'confirmed' | 'outdated';
		disabled?: boolean;
		onconfirm?: () => void;
	} = $props();
</script>

<div class="flex flex-col gap-4">
	<div class="flex items-center justify-between">
		<h3 class="font-serif text-sm">交通与住宿</h3>
		<Badge variant="secondary"
			>{status === 'pending' ? '待确认' : status === 'confirmed' ? '已确认方案' : '已更新'}</Badge
		>
	</div>
	<p class="text-xs text-muted-foreground">
		{trip.origin} → {trip.destination}。如需调整，在聊天中告诉我即可重新确认。
	</p>
	{#each [{ label: '去程', leg: trip.outbound }, { label: '回程', leg: trip.inbound }] as { label, leg } (label)}
		<div class="pure-capsule flex flex-col gap-3 p-4">
			<div class="flex justify-between text-xs">
				<span
					>{label} · {{ train: '高铁 / 火车', flight: '机票航班', bus: '大巴 / 景区直通车' }[
						leg.type
					]}</span
				><span>{leg.number ?? leg.name}</span>
			</div>
			<div class="flex items-center justify-between gap-3 text-sm">
				<div>
					<p>{leg.departure_point}</p>
					<p class="text-xs text-muted-foreground">{leg.departure_time.replace('T', ' ')}</p>
				</div>
				<span aria-hidden="true">→</span>
				<div class="text-right">
					<p>{leg.arrival_point}</p>
					<p class="text-xs text-muted-foreground">{leg.arrival_time.replace('T', ' ')}</p>
				</div>
			</div>
			{#if leg.purchased}<Badge variant="secondary">已购买</Badge>
			{:else if leg.purchase_url}<Button
					href={leg.purchase_url}
					target="_blank"
					rel="noreferrer"
					variant="secondary"
					size="sm">前往购买</Button
				>{/if}
		</div>
	{/each}
	{#each trip.stays as stay (`${stay.hotel}-${stay.check_in}`)}
		<div class="pure-capsule flex flex-col gap-2 p-4">
			<h4 class="font-serif text-sm">{stay.hotel}</h4>
			<p class="text-xs text-muted-foreground">{stay.address}</p>
			<p class="text-xs">{stay.check_in} 入住 · {stay.check_out} 退房</p>
			{#if stay.booked}<Badge variant="secondary">已预订</Badge>
			{:else if stay.purchase_url}<Button
					href={stay.purchase_url}
					target="_blank"
					rel="noreferrer"
					variant="secondary"
					size="sm">前往预订</Button
				>{/if}
		</div>
	{:else}<p class="text-xs text-muted-foreground">同日往返，无酒店住宿。</p>{/each}
	{#if status === 'pending'}<Button {disabled} onclick={onconfirm}>确认方案</Button>
		<p class="text-xs text-muted-foreground">想调整交通或酒店？直接在下方告诉我。</p>{/if}
	<p class="text-xs text-muted-foreground">
		确认方案不代表已经购买，请前往预订页面自行核对并支付。
	</p>
</div>

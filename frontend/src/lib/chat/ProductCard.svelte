<script lang="ts" module>
	export type { Product } from '#lib/api.js';
</script>

<script lang="ts">
	import type { Product } from '#lib/api.js';
	import { ImageOff } from '@lucide/svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	let { product }: { product: Product } = $props();
	let failedImage = $state<string | null>(null);
</script>

<Card.Root class="my-2 w-full py-4">
	<div
		class="grid grid-cols-[6rem_minmax(0,1fr)] items-start gap-x-3 gap-y-3 px-4 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-x-5"
	>
		<div
			class="relative col-start-1 row-start-1 aspect-3/4 w-full overflow-hidden rounded-lg bg-muted sm:row-span-2 sm:aspect-4/3"
		>
			{#if product.image_url && failedImage !== product.image_url}
				<img
					src={product.image_url}
					alt={product.name}
					class="absolute inset-0 size-full object-cover"
					loading="lazy"
					onerror={() => (failedImage = product.image_url ?? null)}
				/>
			{:else}
				<div
					class="absolute inset-0 flex flex-col items-center justify-center gap-1 text-xs text-muted-foreground"
				>
					<ImageOff class="size-5" aria-hidden="true" />
					<span>暂无图片</span>
				</div>
			{/if}
		</div>
		<div class="col-start-2 row-start-1 min-w-0">
			<Card.Header class="gap-2 px-0">
				<Card.Title
					title={product.name}
					class="min-w-0 text-[15px] leading-6 font-semibold break-words text-foreground max-sm:truncate sm:text-base"
					>{product.name}</Card.Title
				>
				<Card.Description class="text-sm leading-6 break-words max-sm:line-clamp-4"
					>{product.description}</Card.Description
				>
			</Card.Header>
		</div>
		<Card.Footer
			class="col-span-2 flex items-center justify-between gap-4 px-0 sm:col-span-1 sm:col-start-2"
		>
			{#if product.price}<p
					title={product.price}
					class="min-w-0 text-sm leading-6 font-medium break-words text-primary tabular-nums max-sm:truncate"
				>
					{product.price}
				</p>
			{:else}<p class="text-xs text-muted-foreground">价格以预订页面为准</p>{/if}

			<a
				href={product.purchase_url}
				target="_blank"
				rel="noopener noreferrer"
				class="inline-flex min-h-11 shrink-0 items-center justify-center rounded-sm text-sm font-medium text-primary underline underline-offset-4 hover:text-primary/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
				>点击预订</a
			>
		</Card.Footer>
	</div>
</Card.Root>

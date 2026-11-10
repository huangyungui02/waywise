<script lang="ts">
	import { MediaQuery } from 'svelte/reactivity';
	import { ShoppingBag, Trash2 } from '@lucide/svelte';
	import type { SavedProduct } from '#lib/api.js';
	import { Button, buttonVariants } from '#lib/components/ui/button/index.js';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import ProductCard from './ProductCard.svelte';

	let {
		products,
		onrefresh,
		onremove
	}: {
		products: SavedProduct[];
		onrefresh: () => Promise<void>;
		onremove: (id: string) => Promise<void>;
	} = $props();
	const desktop = new MediaQuery('(min-width: 768px)');
	let open = $state(false);
	let loading = $state(false);
	let removing = $state<string | null>(null);
	let error = $state('');

	async function refresh() {
		loading = true;
		error = '';
		try {
			await onrefresh();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			loading = false;
		}
	}
	async function remove(id: string) {
		removing = id;
		error = '';
		try {
			await onremove(id);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			removing = null;
		}
	}
</script>

<Sheet.Root
	bind:open
	onOpenChange={(value) => {
		if (value) void refresh();
	}}
>
	<Sheet.Trigger
		class={buttonVariants({
			variant: 'ghost',
			size: 'icon',
			class: 'liquid-glass absolute top-4 right-4 z-10 size-11 rounded-full'
		})}
		aria-label={`打开备选清单（${products.length}）`}
	>
		<ShoppingBag />
		{#if products.length}<span
				aria-hidden="true"
				class="absolute -top-1 -right-1 flex min-w-5 items-center justify-center rounded-full bg-primary px-1 text-xs text-primary-foreground"
				>{products.length}</span
			>{/if}
	</Sheet.Trigger>
	<Sheet.Content
		side={desktop.current ? 'right' : 'bottom'}
		class="max-h-[85dvh] rounded-t-2xl pb-[env(safe-area-inset-bottom)] md:max-h-none md:w-full md:rounded-none md:pt-[env(safe-area-inset-top)] md:data-[side=right]:max-w-xl"
	>
		<Sheet.Header class="pr-12">
			<Sheet.Title>备选清单（{products.length}）</Sheet.Title>
			<Sheet.Description
				>本次旅行推荐过的商品。价格为推荐时参考价，库存与实际费用以预订页面为准。</Sheet.Description
			>
		</Sheet.Header>
		<div class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 pb-4">
			{#if loading}<p role="status" class="text-sm text-muted-foreground">正在更新备选…</p>{/if}
			{#if error}<Alert.Root variant="destructive"
					><Alert.Description
						>{error}<Button variant="link" onclick={refresh} disabled={loading}>重试</Button
						></Alert.Description
					></Alert.Root
				>{/if}
			{#each products as product (product.id)}
				<section aria-label={product.name}>
					<ProductCard {product}>
						{#snippet header()}
							<div class="flex items-center justify-between gap-2">
								<p class="text-[11px] text-muted-foreground">
									推荐于 {new Date(product.updated_at).toLocaleString('zh-CN', {
										month: 'numeric',
										day: 'numeric',
										hour: '2-digit',
										minute: '2-digit'
									})}
								</p>
								<Button
									variant="ghost"
									size="icon-xs"
									class="text-muted-foreground"
									title="移除备选"
									aria-label={`移除${product.name}`}
									disabled={removing !== null}
									onclick={() => remove(product.id)}><Trash2 /></Button
								>
							</div>
						{/snippet}
					</ProductCard>
				</section>
			{:else}
				{#if !loading && !error}<p class="py-12 text-center text-sm text-muted-foreground">
						还没有备选商品，咨询中推荐的商品会自动保存在这里。
					</p>{/if}
			{/each}
		</div>
	</Sheet.Content>
</Sheet.Root>

<script lang="ts">
	import './layout.css';
	import { resolve } from '$app/paths';
	import { goto, invalidate } from '$app/navigation';
	import { page } from '$app/state';
	import { Compass, Menu, Plus, Trash2 } from '@lucide/svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import * as Dialog from '#lib/components/ui/alert-dialog/index.js';
	import { api, type Conversation } from '#lib/api.js';
	import { forgetConversation } from '#lib/chat/cache.js';
	import type { LayoutProps } from './$types';
	let { data, children }: LayoutProps = $props();
	let mobileOpen = $state(false);
	let deleting = $state<Conversation | null>(null);
	let removing = $state(false);
	let error = $state('');
	async function remove() {
		if (!deleting) return;
		removing = true;
		try {
			await api(`/conversations/${deleting.id}`, { method: 'DELETE' });
			await forgetConversation(deleting.id);
			deleting = null;
			await goto(resolve('/'));
			await invalidate('app:conversations');
		} catch (cause) {
			error = String(cause);
		} finally {
			removing = false;
		}
	}
</script>

<svelte:head
	><title>知途 · JOURNEY</title><meta
		name="description"
		content="一起规划交通、住宿与每日行程。"
	/></svelte:head
>
{#snippet sidebar()}
	<div class="flex h-full flex-col gap-4 p-4">
		<a href={resolve('/')} aria-label="知途首页" class="flex items-center gap-3 px-2 py-2"
			><Compass class="size-8 text-primary" /><span
				><span class="block font-serif text-lg">知途</span><span
					class="block text-[9px] tracking-widest text-muted-foreground">JOURNEY</span
				></span
			></a
		>
		<Button
			variant="outline"
			onclick={() => {
				mobileOpen = false;
				void goto(resolve('/'));
			}}
			disabled={page.url.pathname === '/'}><Plus data-icon="inline-start" />开始一段旅行</Button
		>
		<p class="mt-3 px-2 text-xs text-muted-foreground">我的旅行</p>
		<nav aria-label="我的旅行" class="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
			{#each data.conversations as conversation (conversation.id)}
				<div class="group relative">
					<a
						href={resolve('/chat/[id]', { id: conversation.id })}
						onclick={() => (mobileOpen = false)}
						aria-current={page.params.id === conversation.id ? 'page' : undefined}
						class={[
							'block rounded-lg py-2.5 pr-10 pl-3 text-xs transition-colors',
							page.params.id === conversation.id
								? 'bg-card shadow-xs'
								: 'text-muted-foreground hover:bg-card/50'
						]}
					>
						<span class="block truncate leading-5">{conversation.title}</span><span
							class="text-[10px] text-muted-foreground"
							>{new Date(conversation.updated_at).toLocaleDateString('zh-CN')}</span
						>
					</a>
					<Button
						variant="ghost"
						size="icon-sm"
						class="absolute top-1/2 right-1 -translate-y-1/2"
						aria-label={`删除 ${conversation.title}`}
						onclick={() => (deleting = conversation)}><Trash2 /></Button
					>
				</div>
			{:else}<p class="px-3 py-10 text-center font-serif text-xs text-muted-foreground">
					心之所向，皆为旅程。<br />随时开启一段漫游。
				</p>{/each}
		</nav>
	</div>
{/snippet}
<div class="flex h-dvh w-full overflow-hidden sm:p-2.5 md:p-3">
	<aside class="hidden w-60 shrink-0 md:block">{@render sidebar()}</aside>
	<div class="arc-window">
		<header class="flex h-14 shrink-0 items-center justify-between px-4 md:hidden">
			<Button
				variant="ghost"
				size="icon"
				aria-label="打开旅行列表"
				onclick={() => (mobileOpen = true)}><Menu /></Button
			>
			<a href={resolve('/')} class="font-serif">知途</a><Button
				onclick={() => goto(resolve('/'))}
				disabled={page.url.pathname === '/'}
				variant="ghost"
				size="icon"
				aria-label="新建旅行"><Plus /></Button
			>
		</header>
		{#if error}<p role="alert" class="p-3 text-sm text-destructive">
				{error}<Button variant="ghost" onclick={() => (error = '')}>关闭错误提示</Button>
			</p>{/if}
		<main class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
			{@render children()}
		</main>
	</div>
</div>
<Sheet.Root bind:open={mobileOpen}
	><Sheet.Content side="left" class="w-64 p-0"
		><Sheet.Header class="sr-only"
			><Sheet.Title>我的旅行</Sheet.Title><Sheet.Description
				>新建、切换或删除旅行会话</Sheet.Description
			></Sheet.Header
		>{@render sidebar()}</Sheet.Content
	></Sheet.Root
>
<Dialog.Root
	open={Boolean(deleting)}
	onOpenChange={(open) => {
		if (!open && !removing) deleting = null;
	}}
>
	<Dialog.Content
		><Dialog.Header
			><Dialog.Title>移除这段旅行记录？</Dialog.Title><Dialog.Description
				>将从历史记录中移除「{deleting?.title}」。已确认的行程安排也将一并清理。</Dialog.Description
			></Dialog.Header
		>
		<Dialog.Footer
			><Dialog.Cancel disabled={removing}>保留</Dialog.Cancel><Dialog.Action
				disabled={removing}
				onclick={(event) => {
					event.preventDefault();
					void remove();
				}}>{removing ? '正在删除…' : '确认删除'}</Dialog.Action
			></Dialog.Footer
		>
	</Dialog.Content>
</Dialog.Root>

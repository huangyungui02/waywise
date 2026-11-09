<script lang="ts">
	import './layout.css';
	import { resolve } from '$app/paths';
	import { goto, invalidate } from '$app/navigation';
	import { page } from '$app/state';
	import { Compass, Menu, Plus, Trash2, Ellipsis, Pencil } from '@lucide/svelte';
	import { Button, buttonVariants } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import * as Dialog from '#lib/components/ui/alert-dialog/index.js';
	import * as RenameDialog from '#lib/components/ui/dialog/index.js';
	import { api, type Conversation } from '#lib/api.js';
	import { forgetConversation } from '#lib/chat/cache.js';
	import type { LayoutProps } from './$types';
	let { data, children }: LayoutProps = $props();
	let title = $derived(
		data.conversations.find((conversation) => conversation.id === page.params.id)?.title ?? '知途'
	);
	let editing = $state<string | null>(null);
	let draftTitle = $state('');
	let saving = $state(false);
	let editError = $state('');
	async function rename(id: string) {
		saving = true;
		editError = '';
		try {
			await api(`/conversations/${id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ title: draftTitle })
			});
			await invalidate('app:conversations');
			editing = null;
		} catch (cause) {
			editError = String(cause);
		} finally {
			saving = false;
		}
	}
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
	><title>知途 · Waywise</title><meta
		name="description"
		content="一起规划交通、住宿与每日行程。"
	/></svelte:head
>
{#snippet sidebar()}
	<div class="flex h-full flex-col gap-4 p-4">
		<a href={resolve('/')} aria-label="知途首页" class="flex items-center gap-3 px-2 py-2"
			><Compass class="size-8 text-primary" /><span
				><span class="block font-serif text-lg">知途</span><span
					class="block text-[9px] tracking-widest text-muted-foreground">Waywise</span
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
					<Popover.Root>
						<Popover.Trigger
							class={buttonVariants({
								variant: 'ghost',
								size: 'icon-sm',
								class:
									'absolute top-1/2 right-1 -translate-y-1/2 opacity-40 hover:opacity-100 focus-visible:opacity-100 aria-expanded:opacity-100 md:opacity-0 md:group-focus-within:opacity-100 md:group-hover:opacity-60'
							})}
							aria-label={`更多操作 ${conversation.title}`}><Ellipsis /></Popover.Trigger
						>
						<Popover.Content align="end" class="w-36 gap-1 p-1">
							<Popover.Close
								class={buttonVariants({
									variant: 'ghost',
									size: 'sm',
									class: 'w-full justify-start'
								})}
								onclick={() => {
									draftTitle = conversation.title;
									editError = '';
									editing = conversation.id;
								}}><Pencil data-icon="inline-start" />重命名</Popover.Close
							>
							<Popover.Close
								class={buttonVariants({
									variant: 'destructive',
									size: 'sm',
									class: 'w-full justify-start'
								})}
								aria-label={`删除 ${conversation.title}`}
								onclick={() => (deleting = conversation)}
								><Trash2 data-icon="inline-start" />删除</Popover.Close
							>
						</Popover.Content>
					</Popover.Root>
				</div>
			{:else}<p class="px-3 py-10 text-center font-serif text-xs text-muted-foreground">
					心之所向，皆为旅程。<br />随时开启一段漫游。
				</p>{/each}
		</nav>
	</div>
{/snippet}
<div
	class="flex h-dvh w-full overflow-hidden pt-[env(safe-area-inset-top)] sm:p-2.5 sm:pt-[max(0.625rem,env(safe-area-inset-top))] md:p-3 md:pt-[max(0.75rem,env(safe-area-inset-top))]"
>
	<aside class="hidden w-60 shrink-0 md:block">{@render sidebar()}</aside>
	<div
		class="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl bg-card/80 shadow-sm"
	>
		<header
			class="pointer-events-none absolute inset-x-0 top-0 z-10 grid grid-cols-[2.75rem_minmax(0,1fr)_2.75rem] items-center gap-3 px-4 pt-4 md:hidden"
		>
			<Button
				variant="ghost"
				size="icon"
				class="liquid-glass pointer-events-auto size-11 rounded-full"
				aria-label="打开旅行列表"
				onclick={() => (mobileOpen = true)}><Menu /></Button
			>
			<h1
				class="liquid-glass mx-auto max-w-full truncate rounded-full px-4 py-2 text-center text-sm font-medium"
				{title}
			>
				{title}
			</h1>
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
	><Sheet.Content
		side="left"
		showCloseButton={false}
		class="w-64 p-0 pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]"
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

<RenameDialog.Root
	open={editing !== null}
	onOpenChange={(open) => {
		if (!open && !saving) editing = null;
	}}
>
	<RenameDialog.Content
		showCloseButton={false}
		onOpenAutoFocus={(event) => {
			event.preventDefault();
			document.getElementById('conversation-title')?.focus();
		}}
	>
		<RenameDialog.Header>
			<RenameDialog.Title>重命名</RenameDialog.Title>
			<RenameDialog.Description>为这段旅行设置一个标题。</RenameDialog.Description>
		</RenameDialog.Header>
		<form
			class="flex flex-col gap-4"
			onsubmit={(event) => {
				event.preventDefault();
				if (editing) void rename(editing);
			}}
		>
			<Field.Field>
				<Field.Label for="conversation-title">会话标题</Field.Label>
				<Input
					id="conversation-title"
					bind:value={draftTitle}
					maxlength={100}
					required
					disabled={saving}
				/>
			</Field.Field>
			{#if editError}<p role="alert" class="text-xs text-destructive">{editError}</p>{/if}
			<RenameDialog.Footer>
				<Button variant="ghost" disabled={saving} onclick={() => (editing = null)}>取消</Button>
				<Button type="submit" disabled={saving || !draftTitle.trim()}
					>{saving ? '保存中…' : '保存'}</Button
				>
			</RenameDialog.Footer>
		</form>
	</RenameDialog.Content>
</RenameDialog.Root>

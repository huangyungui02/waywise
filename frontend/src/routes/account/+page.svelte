<script lang="ts">
	import { api, clearLogin } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	let oldPassword = $state('');
	let newPassword = $state('');
	let confirmation = $state('');
	let submitting = $state(false);
	let error = $state('');
	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (newPassword !== confirmation) {
			error = '两次新密码不一致';
			return;
		}
		submitting = true;
		error = '';
		try {
			await api('/auth/change-password', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
			});
			await clearLogin();
			window.location.replace('/login');
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '修改失败';
		} finally {
			submitting = false;
		}
	}
</script>

<section class="flex flex-1 items-center justify-center overflow-y-auto p-6 pt-24">
	<form class="flex w-full max-w-sm flex-col gap-6" onsubmit={submit}>
		<h1 class="font-serif text-2xl">修改密码</h1>
		<p class="text-sm text-muted-foreground">修改后，所有设备需要重新登录。</p>
		<Field.Group>
			<Field.Field
				><Field.Label for="old-password">当前密码</Field.Label><Input
					id="old-password"
					type="password"
					autocomplete="current-password"
					bind:value={oldPassword}
					required
					disabled={submitting}
				/></Field.Field
			>
			<Field.Field
				><Field.Label for="new-password">新密码</Field.Label><Input
					id="new-password"
					type="password"
					autocomplete="new-password"
					bind:value={newPassword}
					minlength={8}
					maxlength={128}
					required
					disabled={submitting}
				/></Field.Field
			>
			<Field.Field
				><Field.Label for="confirmation">再次输入新密码</Field.Label><Input
					id="confirmation"
					type="password"
					autocomplete="new-password"
					bind:value={confirmation}
					minlength={8}
					maxlength={128}
					required
					disabled={submitting}
				/></Field.Field
			>
		</Field.Group>
		{#if error}<p role="alert" class="text-sm text-destructive">{error}</p>{/if}
		<Button type="submit" disabled={submitting}>{submitting ? '保存中…' : '保存并重新登录'}</Button>
	</form>
</section>

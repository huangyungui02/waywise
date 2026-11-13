<script lang="ts">
	import { login } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Field from '#lib/components/ui/field/index.js';
	let username = $state('');
	let password = $state('');
	let submitting = $state(false);
	let error = $state('');
	async function submit(event: SubmitEvent) {
		event.preventDefault();
		submitting = true;
		error = '';
		try {
			await login(username, password);
			window.location.replace('/');
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '登录失败，请重试';
		} finally {
			submitting = false;
		}
	}
</script>

<main class="flex min-h-dvh items-center justify-center p-6">
	<form class="flex w-full max-w-sm flex-col gap-6" onsubmit={submit}>
		<h1 class="font-serif text-2xl">登录知途</h1>
		<Field.Group>
			<Field.Field>
				<Field.Label for="username">用户名</Field.Label>
				<Input
					id="username"
					autocomplete="username"
					bind:value={username}
					required
					maxlength={64}
					disabled={submitting}
				/>
			</Field.Field>
			<Field.Field>
				<Field.Label for="password">密码</Field.Label>
				<Input
					id="password"
					type="password"
					autocomplete="current-password"
					bind:value={password}
					required
					maxlength={128}
					disabled={submitting}
				/>
			</Field.Field>
		</Field.Group>
		{#if error}<p role="alert" class="text-sm text-destructive">{error}</p>{/if}
		<Button type="submit" disabled={submitting}>{submitting ? '登录中…' : '登录'}</Button>
	</form>
</main>

<script lang="ts">
	import { resolve } from '$app/paths';
	import { goto, invalidate } from '$app/navigation';
	import { api, type Conversation } from '#lib/api.js';
	import TravelForm from '#lib/components/TravelForm.svelte';
	import Composer from '#lib/components/Composer.svelte';
	import { travelPrompt } from '#lib/components/travel-brief.js';
	let values = $state<Record<string, string>>({});
	let creating = $state(false);
	let error = $state('');
	async function create(text: string) {
		creating = true;
		error = '';
		try {
			const conversation = await api<Conversation>('/conversations', { method: 'POST' });
			await goto(resolve('/chat/[id]', { id: conversation.id }), {
				state: { prompt: travelPrompt(values, text) }
			});
			await invalidate('app:conversations');
		} catch (cause) {
			error = String(cause);
		} finally {
			creating = false;
		}
	}
</script>

<div class="flex min-h-0 flex-1 flex-col">
	<section class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 sm:px-8">
		<div class="mx-auto max-w-2xl py-6 sm:py-12">
			<TravelForm bind:values />{#if error}<p role="alert">{error}</p>{/if}
		</div>
	</section>
	<Composer
		busy={creating}
		hasFormValues={Object.values(values).some((value) => value?.trim())}
		onsend={create}
	/>
</div>

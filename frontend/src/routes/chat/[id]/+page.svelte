<script lang="ts">
	import Chat from '#lib/chat/Chat.svelte';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();
</script>

{#key data.loaded.detail.summary.id}<Chat loaded={data.loaded} />{/key}

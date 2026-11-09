<script lang="ts">
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';
	let { text }: { text: string } = $props();
	let html = $derived(marked.parse(text, { async: false }));
	function render(node: HTMLElement) {
		node.replaceChildren(DOMPurify.sanitize(html, { RETURN_DOM_FRAGMENT: true }));
	}
</script>

<div
	{@attach render}
	class="prose prose-sm max-w-none leading-7 break-words prose-headings:font-serif prose-a:text-primary prose-pre:overflow-x-auto prose-table:text-xs"
></div>

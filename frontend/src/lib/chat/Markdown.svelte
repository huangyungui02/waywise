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
	class="prose prose-sm max-w-none leading-7 break-words prose-headings:mt-6 prose-headings:mb-3 prose-headings:font-serif prose-headings:leading-relaxed prose-headings:font-medium prose-headings:text-foreground prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-h4:text-sm prose-h5:text-sm prose-h6:text-sm prose-a:text-primary prose-pre:overflow-x-auto prose-table:text-xs"
></div>

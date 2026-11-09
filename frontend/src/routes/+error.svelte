<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { Button } from '#lib/components/ui/button/index.js';
</script>

<div class="m-auto flex max-w-sm flex-col items-center gap-4 p-6 text-center">
	<h1 class="font-serif text-xl">暂时无法打开</h1>
	<p role="alert" class="text-sm text-muted-foreground">{page.error?.message}</p>
	<Button href={resolve('/')} variant="outline">返回首页</Button>
</div>

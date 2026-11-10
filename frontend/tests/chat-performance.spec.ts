import { expect, test } from '@playwright/test';

test('长会话恢复保留完整预览，上滑阅读不被重放拉回底部', async ({ page }) => {
	const paragraph = '交通、住宿和景点安排需要结合实际班次进行核实。'.repeat(8);
	const markdown = `### 每日行程\n\n${paragraph}\n\n| 时间 | 安排 |\n| --- | --- |\n${'| 上午 | 游览城市街区 |\n'.repeat(8)}`;
	const history = Array.from({ length: 24 }, (_, i) => [
		{ id: `u-${i}`, role: 'user', parts: [{ type: 'text', text: `第 ${i + 1} 轮旅行咨询` }] },
		{
			id: `a-${i}`,
			role: 'assistant',
			parts: [
				{ type: 'text', text: markdown },
				{
					type: 'dynamic-tool',
					toolName: 'call_flyai',
					toolCallId: `t-${i}`,
					state: 'output-available',
					input: {},
					output: {}
				}
			]
		}
	]).flat();
	const base = [
		...history,
		{ id: 'latest-user', role: 'user', parts: [{ type: 'text', text: '继续核实安排' }] }
	];
	const delta = '继续核实，安排妥当。';
	const text = delta.repeat(1000);
	const summary = {
		id: 'long-chat',
		title: '长会话性能测试',
		outcome: 'running',
		updated_at: new Date().toISOString()
	};
	const detail = {
		summary,
		messages: [...base, { id: 'current-run', role: 'assistant', parts: [{ type: 'text', text }] }],
		recovery: { run_id: 'current-run', cursor: '1002-0', messages: base },
		arrangements: null,
		pending_arrangements: null,
		pending_id: null,
		confirmed_id: null
	};
	const chunks = [
		{ type: 'start', messageId: 'current-run' },
		{ type: 'text-start', id: 'text' },
		...Array.from({ length: 1000 }, () => ({ type: 'text-delta', id: 'text', delta })),
		{ type: 'text-end', id: 'text' },
		{ type: 'finish' }
	];
	const frames = chunks.map(
		(chunk, i) =>
			`data: ${JSON.stringify(chunk)}\n\ndata: ${JSON.stringify({ type: 'data-progress', data: { runId: 'current-run', cursor: `${i + 1}-0` }, transient: true })}\n\n`
	);
	await page.addInitScript(
		({ head, tail }) => {
			const fetch = window.fetch.bind(window);
			window.fetch = async (input, init) => {
				if (!String(input).includes('/chat/stream')) return fetch(input, init);
				const encoder = new TextEncoder();
				return new Response(
					new ReadableStream({
						start(controller) {
							controller.enqueue(encoder.encode(head));
							window.addEventListener(
								'test:finish-replay',
								() => {
									controller.enqueue(encoder.encode(tail));
									controller.close();
								},
								{ once: true }
							);
						}
					}),
					{
						headers: { 'content-type': 'text/event-stream', 'x-vercel-ai-ui-message-stream': 'v1' }
					}
				);
			};
		},
		{ head: frames.slice(0, 3).join(''), tail: frames.slice(3).join('') + 'data: [DONE]\n\n' }
	);
	await page.route('**/api/**', (route) =>
		route.fulfill({
			json: new URL(route.request().url()).pathname === '/api/conversations' ? [summary] : detail
		})
	);
	await page.goto('/');
	await page.evaluate(async (detail) => {
		const db = await new Promise<IDBDatabase>((resolve) => {
			const request = indexedDB.open('travel-agent', 1);
			request.onupgradeneeded = () =>
				request.result.createObjectStore('conversations', { keyPath: 'id' });
			request.onsuccess = () => resolve(request.result);
		});
		await new Promise<void>((resolve) => {
			const tx = db.transaction('conversations', 'readwrite');
			tx.objectStore('conversations').put({
				id: detail.summary.id,
				schemaVersion: 2,
				detail: { ...detail, recovery: null }
			});
			tx.oncomplete = () => {
				db.close();
				resolve();
			};
		});
	}, detail);
	await page.locator('a[href="/chat/long-chat"]').click();
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	await expect(page.getByText('正在同步最新进度…', { exact: true })).toHaveCount(0);
	// 第一条事件已抵达；完整预览仍应保留，不退回空白的回复起点。
	await page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 150)));
	await expect(page.getByText(text, { exact: true })).toHaveCount(1);
	const table = await page.locator('table').first().elementHandle();
	const scroller = page.locator('main .overflow-y-auto').first();
	await scroller.hover();
	await page.mouse.wheel(0, -50000);
	await expect.poll(() => scroller.evaluate((element) => element.scrollTop)).toBeLessThan(80);
	// 观察实际重放期间的主线程长任务，不依赖生产代码的计数或测试开关。
	summary.outcome = 'completed';
	const synchronized = page.waitForResponse(
		(response) => new URL(response.url()).pathname === '/api/conversations/long-chat'
	);
	await page.evaluate(() => {
		const tasks: number[] = [];
		const observer = new PerformanceObserver((list) =>
			tasks.push(...list.getEntries().map((entry) => entry.duration))
		);
		observer.observe({ entryTypes: ['longtask'] });
		Object.assign(window, { replayTasks: tasks });
		window.dispatchEvent(new Event('test:finish-replay'));
	});
	await synchronized;
	await expect(page.getByText('正在同步最新进度…', { exact: true })).toHaveCount(0);
	await expect(page.getByText(text, { exact: true })).toHaveCount(1);
	await expect.poll(() => scroller.evaluate((element) => element.scrollTop)).toBeLessThan(80);
	expect(await table!.evaluate((element) => element.isConnected)).toBe(true);
	const longest = await page.evaluate(() =>
		Math.max(0, ...(window as unknown as { replayTasks: number[] }).replayTasks)
	);
	expect(longest).toBeLessThan(1500);
	await page.getByRole('button', { name: '回到最新消息' }).click();
	await expect
		.poll(() =>
			scroller.evaluate(
				(element) => element.scrollHeight - element.clientHeight - element.scrollTop
			)
		)
		.toBeLessThan(2);
});

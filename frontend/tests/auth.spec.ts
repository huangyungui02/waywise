import { test, expect } from './fixtures';

test('登录失败、成功登录和退出后撤销会话', async ({ page, tokens, context }) => {
	await context.setExtraHTTPHeaders({});
	await page.goto('/login');
	await page.getByLabel('用户名', { exact: true }).fill('offline');
	await page.getByLabel('密码', { exact: true }).fill('wrong-password');
	await page.getByRole('button', { name: '登录', exact: true }).click();
	await expect(page.getByRole('alert')).toBeVisible();
	await page.getByLabel('密码', { exact: true }).fill('offline-test-password');
	await page.getByRole('button', { name: '登录', exact: true }).click();
	await expect(page).toHaveURL('/');
	await expect(page.getByRole('button', { name: '退出登录', exact: true })).toBeVisible();
	const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('waywise.auth')!));
	expect(stored.userId).toBe(tokens.userId);
	await page.getByRole('button', { name: '退出登录', exact: true }).click();
	await expect(page).toHaveURL('/login');
	expect(await page.evaluate(() => localStorage.getItem('waywise.auth'))).toBeNull();
	const response = await page.request.post('/api/auth/refresh', {
		data: { refresh_token: stored.refreshToken }
	});
	expect(response.status()).toBe(401);
});

test('启动合并并发刷新，access 失效后自动重试，撤销后跳转登录', async ({
	page,
	tokens,
	context
}) => {
	await context.setExtraHTTPHeaders({});
	let refreshes = 0;
	page.on('request', (request) => {
		if (request.url().endsWith('/api/auth/refresh')) refreshes++;
	});
	await page.goto('/');
	await expect(page.getByRole('button', { name: '退出登录', exact: true })).toBeVisible();
	expect(refreshes).toBe(1);
	const before = await page.evaluate(
		() => JSON.parse(localStorage.getItem('waywise.auth')!).refreshToken
	);
	expect(before).not.toBe(tokens.refresh_token);
	const result = await page.evaluate(async () => {
		const { api } = await import('/src/lib/api.ts');
		await Promise.all([api('/auth/me'), api('/auth/me')]);
		return true;
	});
	expect(result).toBe(true);
	expect(refreshes).toBe(1);
	let rejected = false;
	await page.route('**/api/auth/me', async (route) => {
		if (!rejected) {
			rejected = true;
			await route.fulfill({ status: 401, json: { detail: 'expired' } });
		} else await route.continue();
	});
	await page.evaluate(async () => {
		const { api } = await import('/src/lib/api.ts');
		await api('/auth/me');
	});
	expect(refreshes).toBe(2);
	await page.request.post('/api/auth/logout', {
		headers: { Authorization: `Bearer ${tokens.access_token}` }
	});
	await page.reload();
	await expect(page).toHaveURL('/login');
});

test('修改密码时旧密码错误保留登录状态', async ({ page, context }) => {
	await context.setExtraHTTPHeaders({});
	await page.goto('/account');
	await page.getByLabel('当前密码', { exact: true }).fill('wrong-password');
	await page.getByLabel('新密码', { exact: true }).fill('replacement-password');
	await page.getByLabel('再次输入新密码', { exact: true }).fill('replacement-password');
	await page.getByRole('button', { name: '保存并重新登录' }).click();
	await expect(page.getByRole('alert')).toHaveText('当前密码不正确');
	await expect(page).toHaveURL('/account');
	await page.reload();
	await expect(page.getByRole('heading', { name: '修改密码' })).toBeVisible();
});

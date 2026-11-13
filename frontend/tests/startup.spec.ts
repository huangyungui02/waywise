import { expect, test } from './fixtures';

test('首次启动无法连接后端时显示可读错误', async ({ page }) => {
	await page.route('**/api/conversations', (route) => route.abort());
	await page.goto('/');
	await expect(
		page.getByText('无法连接服务器，请检查网络及后端地址、HTTPS 证书和跨域配置后重新打开。')
	).toBeVisible();
});

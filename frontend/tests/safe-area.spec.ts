import { expect, test } from '@playwright/test';

for (const top of [0, 62]) {
	test(`手机顶部安全区 ${top}px：表单和旅行列表避开标题与状态栏`, async ({ page }) => {
		await page.setViewportSize({ width: 420, height: 912 });
		const session = await page.context().newCDPSession(page);
		await session.send('Emulation.setSafeAreaInsetsOverride', {
			insets: { top, bottom: 34, left: 0, right: 0 }
		});
		await page.goto('/');
		const menu = page.getByRole('button', { name: '打开旅行列表' });
		const menuBox = (await menu.boundingBox())!;
		expect(menuBox.y).toBeGreaterThanOrEqual(top + 16);
		const formTitle = (await page.getByText('这次，想去哪里？', { exact: true }).boundingBox())!;
		expect(formTitle.y).toBeGreaterThan(menuBox.y + menuBox.height);
		await page.screenshot({
			path: `/private/tmp/travel-safe-area-${top}-home.png`,
			animations: 'disabled'
		});

		await menu.click();
		const sheet = page.getByRole('dialog', { name: '我的旅行', exact: true });
		await expect(sheet).toBeVisible();
		await expect
			.poll(async () => (await sheet.getByRole('link', { name: '知途首页' }).boundingBox())!.y)
			.toBeGreaterThanOrEqual(top + 16);
		await page.screenshot({
			path: `/private/tmp/travel-safe-area-${top}-sidebar.png`,
			animations: 'disabled'
		});
	});
}

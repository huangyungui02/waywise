import { expect, test } from '@playwright/test';

test('新建、发送、工具展示、刷新恢复、切换与删除', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: '开始规划' }).click();
  await expect(page).toHaveURL(/\/chat\//);
  const firstUrl = page.url();
  const prompt = `去杭州 ${Date.now()}`;
  await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
  await expect(page.getByText('核对北京时间')).toBeVisible();
  await page.reload();
  await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
  await page.getByRole('button', { name: '开始一段旅行' }).click();
  await expect(page.getByRole('heading', { name: '说说这次旅行吧。' })).toBeVisible();
  await page.getByRole('link', { name: new RegExp(prompt) }).click();
  await expect(page).toHaveURL(firstUrl);
  await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
  await page.screenshot({ path: '/private/tmp/travel-agent-desktop.png', fullPage: true });
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: `删除 ${prompt}` }).click();
  await expect(page).toHaveURL('http://127.0.0.1:5179/');
  expect(errors).toEqual([]);
});

test('手机界面可输入、发送和读取历史，页面没有横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: '开始规划' }).click();
  await page.getByRole('textbox', { name: '旅行需求' }).fill('我想去重庆');
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.getByText('收到你的旅行想法：我想去重庆。')).toBeVisible();
  await page.reload();
  await expect(page.getByText('收到你的旅行想法：我想去重庆。')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '/private/tmp/travel-agent-mobile.png', fullPage: true });
});

test('停止生成后仍能读取已保存记录并继续聊天', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '开始规划' }).click();
  await page.getByRole('textbox', { name: '旅行需求' }).fill('停止测试');
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.getByText('正在安排这次旅行…')).toBeVisible();
  await page.getByRole('button', { name: '停止' }).click();
  await page.reload();
  await expect(page.getByText('停止测试', { exact: true }).last()).toBeVisible();
  await page.getByRole('textbox', { name: '旅行需求' }).fill('继续聊杭州');
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.getByText('收到你的旅行想法：继续聊杭州。')).toBeVisible();
});

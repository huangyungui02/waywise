import type { Detail } from '../src/lib/api';
import { expect, test, type Page } from '@playwright/test';

function dateName(date: string) {
	const [year, month, day] = date.split('-').map(Number);
	return new RegExp(`^${year}年${month}月${day}日`);
}

async function selectDate(page: Page, label: string, date: string) {
	await page.getByRole('button', { name: label, exact: true }).click();
	const calendar = page.getByRole('dialog', { name: label, exact: true });
	await calendar.getByRole('combobox', { name: '年份' }).selectOption(date.slice(0, 4));
	await calendar
		.getByRole('combobox', { name: '月份' })
		.selectOption(String(Number(date.slice(5, 7))));
	await calendar.getByRole('button', { name: dateName(date) }).click();
	await expect(calendar).not.toBeVisible();
}

for (const mobile of [false, true]) {
	test(`${mobile ? '手机' : '桌面'}日历可清除并约束往返日期，选项可取消`, async ({ page }) => {
		await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 });
		await page.goto('/');
		await selectDate(page, '出发日期', '2026-12-10');
		await page.getByRole('button', { name: '返回日期', exact: true }).click();
		await expect(page.getByRole('button', { name: dateName('2026-12-09') })).toBeDisabled();
		await page.screenshot({
			path: `/private/tmp/travel-form-calendar-${mobile ? 'mobile' : 'desktop'}.png`,
			fullPage: true,
			animations: 'disabled'
		});
		expect(
			await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
		).toBe(true);
		await page.getByRole('button', { name: dateName('2026-12-12') }).click();
		await selectDate(page, '出发日期', '2026-12-15');
		await expect(page.getByRole('button', { name: '返回日期', exact: true })).toHaveText(
			'选择日期'
		);
		await page.getByRole('button', { name: '出发日期', exact: true }).click();
		await page.getByRole('button', { name: '清除日期', exact: true }).click();
		await expect(page.getByRole('button', { name: '出发日期', exact: true })).toHaveText(
			'选择日期'
		);
		await page.getByRole('checkbox', { name: '有老人', exact: true }).check();
		await page.getByRole('checkbox', { name: '有老人', exact: true }).uncheck();
		await expect(page.getByRole('checkbox', { name: '有老人', exact: true })).not.toBeChecked();
		await page.getByRole('radio', { name: '人均', exact: true }).check();
		await page.getByRole('radio', { name: '总共', exact: true }).check();
		await expect(page.getByRole('radio', { name: '人均', exact: true })).not.toBeChecked();
	});
}

for (const mobile of [false, true]) {
	test(`${mobile ? '手机' : '桌面'}新旅行发送前不创建会话，空白会话不能重复新建`, async ({
		page
	}) => {
		await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 });
		let creates = 0;
		page.on('request', (request) => {
			if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/conversations')
				creates++;
		});
		await page.goto('/');
		const existing = await (await page.request.get('/api/conversations')).json();
		const newTravel = page.getByRole('button', {
			name: mobile ? '新建旅行' : '开始一段旅行',
			exact: true
		});
		await expect(newTravel).toBeDisabled();
		await page.getByLabel('目的地', { exact: true }).fill('四姑娘山');
		await expect(newTravel).toBeDisabled();
		expect(creates).toBe(0);
		expect(await (await page.request.get('/api/conversations')).json()).toHaveLength(
			existing.length
		);
		await page.getByRole('button', { name: '发送', exact: true }).click();
		await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
		expect(creates).toBe(1);
		await newTravel.click();
		await expect(page).toHaveURL('http://127.0.0.1:5179/');
		await expect(newTravel).toBeDisabled();
		await page.reload();
		await expect(newTravel).toBeDisabled();
		expect(creates).toBe(1);
		expect(await (await page.request.get('/api/conversations')).json()).toHaveLength(
			existing.length + 1
		);
	});
}

test('模型思考时显示动画并隐藏思考内容，正式输出时立即移除', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('思考测试');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const activity = page.getByRole('status').filter({ hasText: '正在思考…' });
	await expect(activity).toBeVisible();
	// reasoning 事件已到达并进入 streaming 状态，仍然保留提示。
	await expect(page.locator('article')).toHaveCount(2);
	await expect(activity).toBeVisible();
	await expect(activity.locator('svg')).toHaveClass(/animate-spin/);
	await expect(page.getByText('这是不应展示的思考内容')).toHaveCount(0);
	await expect(page.getByText('旅行建议已整理好。')).toBeVisible();
	await expect(activity).toHaveCount(0);
	await expect(page.getByRole('button', { name: '停止', exact: true })).toBeVisible();
	await expect(page.getByText('接下来一起确定出发日期。', { exact: false })).toBeVisible();
	await expect(activity).toHaveCount(0);
});

test('新建、发送、工具展示、刷新恢复、切换与删除', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	await page.goto('/');
	await page.screenshot({
		path: '/private/tmp/travel-agent-welcome.png',
		fullPage: true
	});
	await expect(page.getByRole('button', { name: '开始一段旅行' })).toBeDisabled();
	const prompt = `去杭州 ${Date.now()}`;
	await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page).toHaveURL(/\/chat\//);
	const firstUrl = page.url();
	await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
	const userMessage = page.locator('article').getByText(prompt, { exact: true });
	const selection = await userMessage.evaluate((element) => {
		const range = document.createRange();
		range.selectNodeContents(element);
		const selected = window.getSelection()!;
		selected.removeAllRanges();
		selected.addRange(range);
		const style = getComputedStyle(element, '::selection');
		return { text: selected.toString(), color: style.color, background: style.backgroundColor };
	});
	expect(selection).toEqual({
		text: prompt,
		color: 'rgb(25, 56, 46)',
		background: 'rgb(217, 238, 227)'
	});
	await page.evaluate(() => window.getSelection()?.removeAllRanges());
	await expect(page.getByText('核对北京时间')).toBeVisible();
	await expect(page.getByRole('button', { name: /核对北京时间/ })).toHaveCount(0);
	await expect(page.getByText('2026-11-06 10:00', { exact: false })).toHaveCount(0);
	await page.reload();
	await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
	await page.getByRole('button', { name: '开始一段旅行' }).click();
	await expect(page.getByRole('textbox', { name: '旅行需求' })).toBeVisible();
	await page.getByRole('link', { name: new RegExp(prompt) }).click();
	await expect(page).toHaveURL(firstUrl);
	await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
	await page.screenshot({
		path: '/private/tmp/travel-agent-desktop.png',
		fullPage: true
	});
	await page.getByRole('button', { name: `删除 ${prompt}` }).click();
	await expect(page.getByRole('alertdialog')).toBeVisible();
	await page.getByRole('button', { name: '确认删除', exact: true }).click();
	await expect(page).toHaveURL('http://127.0.0.1:5179/');
	const deletedId = new URL(firstUrl).pathname.split('/').at(-1)!;
	await expect.poll(() => cachedConversation(page, deletedId)).toBeUndefined();
	expect(errors).toEqual([]);
});

test('手机界面可输入、发送和读取历史，页面没有横向溢出', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('开始旅行');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
	await page.getByRole('textbox', { name: '旅行需求' }).fill('我想去重庆');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText('收到你的旅行想法：我想去重庆。')).toBeVisible();
	await page.reload();
	await expect(page.getByText('收到你的旅行想法：我想去重庆。')).toBeVisible();
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
		true
	);
	await page.screenshot({
		path: '/private/tmp/travel-agent-mobile.png',
		fullPage: true
	});
});

test('停止生成后仍能读取已保存记录并继续聊天', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('开始旅行');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
	await page.getByRole('textbox', { name: '旅行需求' }).fill('停止测试');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText('正在安排这次旅行…')).toBeVisible();
	await page.getByRole('button', { name: '停止' }).click();
	await expect(page.getByText('正在思考…', { exact: true })).toHaveCount(0);
	await page.reload();
	await expect(page.getByText('停止测试', { exact: true }).last()).toBeVisible();
	await page.getByRole('textbox', { name: '旅行需求' }).fill('继续聊杭州');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText('收到你的旅行想法：继续聊杭州。')).toBeVisible();
});

test('表单合并发送，刷新恢复摘要，聊天调整需求和手机布局', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/');
	await page.getByLabel('出发地', { exact: true }).fill('上海');
	await page.getByLabel('目的地', { exact: true }).fill('杭州');
	await selectDate(page, '出发日期', '2026-12-01');
	await selectDate(page, '返回日期', '2026-12-03');
	await page.getByLabel('同行人数', { exact: true }).fill('2');
	await page.getByLabel('预算', { exact: true }).fill('2000');
	await page.getByRole('radio', { name: '人均', exact: true }).check();
	await page.getByRole('checkbox', { name: '有老人', exact: true }).check();
	await page.getByRole('checkbox', { name: '有小孩', exact: true }).check();
	await page.getByRole('textbox', { name: '旅行需求' }).fill('想住湖边');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
	await expect(page.locator('article').first().getByText('上海', { exact: true })).toBeVisible();
	await expect(page.locator('article').first().getByText('杭州', { exact: true })).toBeVisible();
	await expect(page.locator('article').first()).toContainText('2026-12-01 至 2026-12-03');
	await expect(page.locator('article').first()).toContainText('¥2000 (人均)');
	await expect(page.locator('article').first()).toContainText('有老人同行');
	await expect(page.locator('article').first()).toContainText('有小孩同行');
	await expect(page.getByLabel('出发地', { exact: true })).toHaveCount(0);
	await page.reload();
	await expect(page.getByRole('button', { name: '修改需求' })).toHaveCount(0);
	await expect(page.locator('article').first().getByText('杭州', { exact: true })).toBeVisible();
	await page.getByRole('textbox', { name: '旅行需求' }).fill('目的地改成苏州');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText('收到你的旅行想法：目的地改成苏州。')).toBeVisible();
	await expect(page.getByRole('button', { name: '旅行安排', exact: true })).toHaveCount(0);
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
		true
	);
	await page.screenshot({ path: '/private/tmp/travel-agent-mobile.png', fullPage: true });
});

for (const mobile of [false, true]) {
	test(`${mobile ? '手机' : '桌面'}方案卡片支持修改、确认和刷新恢复`, async ({ page }) => {
		if (mobile) await page.setViewportSize({ width: 390, height: 844 });
		await page.goto('/');
		const send = async (text: string) => {
			await page.getByRole('textbox', { name: '旅行需求' }).fill(text);
			await page.getByRole('button', { name: '发送', exact: true }).click();
		};
		await send('展示方案');
		const cards = page.getByRole('region', { name: '交通与住宿方案' });
		await expect(cards).toHaveCount(1);
		await expect(cards.first().getByRole('button', { name: '确认方案' })).toBeEnabled();
		await expect(cards.first().getByText('G123', { exact: true })).toBeVisible();
		await expect(cards.first().getByRole('link', { name: '前往购买' })).toHaveAttribute(
			'href',
			'https://example.com/train'
		);
		await expect(page.getByRole('complementary', { name: '旅行基础安排' })).toHaveCount(0);
		await expect(page.getByRole('button', { name: '旅行安排', exact: true })).toHaveCount(0);
		await page.reload();
		await expect(cards.first().getByText('待确认', { exact: true })).toBeVisible();
		await send('换酒店');
		await expect(cards).toHaveCount(2);
		await expect(cards.first().getByText('已更新', { exact: true })).toBeVisible();
		await expect(cards.first().getByRole('button', { name: '确认方案' })).toHaveCount(0);
		await expect(cards.last().getByText('新的测试酒店', { exact: true })).toBeVisible();
		await expect(cards.last().getByRole('button', { name: '确认方案' })).toBeEnabled();
		await cards.last().getByRole('button', { name: '确认方案' }).click();
		await expect(
			page.getByText('交通住宿已确认，现在开始每日行程规划。', { exact: true })
		).toBeVisible();
		await expect(cards.last().getByText('已确认方案', { exact: true })).toBeVisible();
		await page.reload();
		await expect(cards.last().getByText('已确认方案', { exact: true })).toBeVisible();
		expect(
			await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
		).toBe(true);
		await page.screenshot({
			path: `/private/tmp/travel-agent-proposal-${mobile ? 'mobile' : 'desktop'}.png`,
			fullPage: true
		});
	});
}

test('历史方案卡片兼容包装格式的工具参数', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('展示方案');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const card = page.getByRole('region', { name: '交通与住宿方案' });
	await expect(card.getByRole('button', { name: '确认方案' })).toBeEnabled();
	await page.route('**/api/conversations/*', async (route) => {
		const response = await route.fetch();
		const detail = await response.json();
		detail.recovery = null;
		for (const message of detail.messages) {
			for (const part of message.parts) {
				if (part.type === 'tool-present_trip' || part.toolName === 'present_trip') {
					part.input = { trip: part.input };
				}
			}
		}
		await route.fulfill({ response, json: detail });
	});
	await page.reload();
	await expect(card.getByText('上海 → 杭州。', { exact: false })).toBeVisible();
	await expect(card.getByText('G123', { exact: true })).toBeVisible();
	await expect(card.getByRole('button', { name: '确认方案' })).toBeEnabled();
});

test('用户发送文字也能确认待确认方案', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('展示方案');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const card = page.getByRole('region', { name: '交通与住宿方案' });
	await expect(card.getByRole('button', { name: '确认方案' })).toBeEnabled();
	await page.getByRole('textbox', { name: '旅行需求' }).fill('确认方案');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(
		page.getByText('交通住宿已确认，现在开始每日行程规划。', { exact: true })
	).toBeVisible();
	await expect(card.getByText('已确认方案', { exact: true })).toBeVisible();
	await expect(card.getByRole('button', { name: '确认方案' })).toHaveCount(0);
});

test('连续工具记录自动滚动到底部且不提供结果详情', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('工具滚动测试');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
	await page.route('**/api/conversations/*', async (route) => {
		const response = await route.fetch();
		const detail = await response.json();
		detail.recovery = null;
		detail.messages = [
			{
				id: 'tools-scroll',
				role: 'assistant',
				parts: Array.from({ length: 20 }, (_, index) => ({
					type: 'tool-current_time',
					toolCallId: `clock-${index}`,
					state: 'output-available',
					input: {},
					output: '不应显示的工具原始结果'
				}))
			}
		];
		await route.fulfill({ response, json: detail });
	});
	await page.reload();
	const records = page.getByRole('region', { name: '行程查询记录' });
	await expect(records.getByText('核对北京时间')).toHaveCount(20);
	await expect(page.getByText('行程查询记录', { exact: true })).toHaveCount(0);
	await expect(records.getByText(/^\d+ 项$/)).toHaveCount(0);
	await expect
		.poll(() =>
			records.evaluate(
				(element) =>
					element.scrollHeight > element.clientHeight &&
					Math.abs(element.scrollHeight - element.clientHeight - element.scrollTop) < 2
			)
		)
		.toBe(true);
	await expect(records.getByRole('button')).toHaveCount(0);
	await expect(page.getByText('不应显示的工具原始结果')).toHaveCount(0);
});

for (const mobile of [false, true]) {
	test(`${mobile ? '手机' : '桌面'}聊天布局简化且回到底部按钮居中`, async ({ page }) => {
		await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 });
		await page.goto('/');
		await page.getByRole('textbox', { name: '旅行需求' }).fill('布局测试');
		await page.getByRole('button', { name: '发送', exact: true }).click();
		await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
		await page.route('**/api/conversations/*', async (route) => {
			const response = await route.fetch();
			const detail = await response.json();
			detail.recovery = null;
			detail.messages = [
				{
					id: 'long-message',
					role: 'assistant',
					parts: [
						{
							type: 'text',
							text: Array.from({ length: 50 }, (_, i) => `行程建议第 ${i + 1} 条。`).join('\n\n')
						}
					]
				}
			];
			await route.fulfill({ response, json: detail });
		});
		await page.reload();
		const article = page.locator('article').first();
		await expect(article).toContainText('行程建议第 50 条');
		expect(
			await article.evaluate(
				(el) =>
					el.children.length === 1 &&
					Math.abs(
						el.getBoundingClientRect().left - el.firstElementChild!.getBoundingClientRect().left
					) < 1
			)
		).toBe(true);
		const scroller = article.locator('../..');
		await scroller.evaluate((el) => {
			el.scrollTop = 0;
		});
		const button = page.getByRole('button', { name: '回到最新消息' });
		await expect(button).toBeVisible();
		const buttonBox = (await button.boundingBox())!;
		const chatBox = (await scroller.boundingBox())!;
		expect(
			Math.abs(buttonBox.x + buttonBox.width / 2 - chatBox.x - chatBox.width / 2)
		).toBeLessThan(1);
		await button.click();
		await expect(button).toBeHidden();
		for (const text of [
			'知途 · 旅行手札',
			'山水有信 · 知途相伴',
			'基础安排 · 行囊',
			'确认方案不代表已经购买。请前往预订页面自行核对并支付。'
		]) {
			await expect(page.getByText(text, { exact: true })).toHaveCount(0);
		}
	});
}

for (const mobile of [false, true]) {
	test(`${mobile ? '手机' : '桌面'}新旅行使用底部输入框发送精简表单`, async ({ page }) => {
		await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 });
		await page.goto('/');
		for (const newConversation of [false, true]) {
			if (newConversation)
				await page
					.getByRole('button', { name: mobile ? '新建旅行' : '开始一段旅行', exact: true })
					.click();
			const card = page.getByRole('region', { name: '旅行基本信息' });
			await expect(card.getByRole('textbox')).toHaveCount(2);
			await expect(card.getByRole('spinbutton')).toHaveCount(2);
			await expect(card.getByRole('checkbox')).toHaveCount(2);
			await expect(card.getByRole('radio', { name: '总共' })).toBeChecked();
			await expect(page.getByText('旅行想法与期待', { exact: true })).toHaveCount(0);
			await expect(page.getByRole('button', { name: '开始规划', exact: true })).toHaveCount(0);
			const composer = page.getByRole('textbox', { name: '旅行需求' });
			await expect(composer).toBeInViewport();
			await expect(page.getByRole('button', { name: '发送', exact: true })).toBeDisabled();
			await page.getByLabel('目的地', { exact: true }).fill('四姑娘山');
			await expect(page.getByRole('button', { name: '发送', exact: true })).toBeEnabled();
			if (newConversation) {
				await composer.fill('想坐大巴');
				await composer.press('Enter');
			} else {
				await page.screenshot({
					path: `/private/tmp/travel-agent-new-${mobile ? 'mobile' : 'desktop'}.png`,
					fullPage: true
				});
				await page.getByRole('button', { name: '发送', exact: true }).click();
			}
			await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
			await expect(page.locator('article').first()).toContainText('四姑娘山');
			await expect(page.getByText('旅行计划', { exact: true })).toHaveCount(0);
			await expect(page.locator('a[aria-current="page"]')).toContainText('四姑娘山旅行');
			if (newConversation) await expect(page.locator('article').first()).toContainText('想坐大巴');
			await expect(card).toHaveCount(0);
			await expect(composer).toBeInViewport();
			expect(
				await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
			).toBe(true);
		}
	});
}

async function startBackgroundReply(page: Page, withHistory = false) {
	await page.goto('/');
	if (withHistory) {
		await page.getByRole('textbox', { name: '旅行需求' }).fill('开始旅行');
		await page.getByRole('button', { name: '发送', exact: true }).click();
		await expect(page.getByText('收到你的旅行想法：开始旅行。', { exact: false })).toBeVisible();
		await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
	}
	await page.getByRole('textbox', { name: '旅行需求' }).fill('后台测试');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText('正在后台整理旅行…', { exact: false })).toBeVisible();
	return page.url();
}

test('切换会话和刷新会恢复正在执行的回复，输出不重复', async ({ page }) => {
	const url = await startBackgroundReply(page, true);
	await page.getByRole('button', { name: '开始一段旅行', exact: true }).click();
	await expect(page).toHaveURL('http://127.0.0.1:5179/');
	await page.goto(url);
	await expect(page.getByText('正在后台整理旅行…', { exact: false })).toBeVisible();
	await expect(page.getByRole('button', { name: '停止', exact: true })).toBeVisible();
	await page.reload();
	await expect(page.getByText('后台旅行建议已完成。', { exact: false })).toBeVisible();
	await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
	await expect(page.locator('article')).toHaveCount(4);
	await expect(page.getByText('核对北京时间', { exact: true })).toHaveCount(1);
	await expect(page.locator('article').last()).toHaveText('正在后台整理旅行…后台旅行建议已完成。');
});

test('关闭页面后后台继续执行，新页面能读取最终结果', async ({ page, context }) => {
	const url = await startBackgroundReply(page);
	const cid = url.split('/').at(-1);
	await page.close();
	const reopened = await context.newPage();
	await expect
		.poll(async () => {
			const response = await reopened.request.get(`/api/conversations/${cid}`);
			return (await response.json()).summary.outcome;
		})
		.toBe('completed');
	await reopened.goto(url);
	await expect(reopened.getByText('后台旅行建议已完成。', { exact: false })).toBeVisible();
	await expect(reopened.locator('article')).toHaveCount(2);
});

test('详情读取后任务恰好完成，重连仍能加载最终结果', async ({ page }) => {
	const url = await startBackgroundReply(page);
	const cid = url.split('/').at(-1);
	await page.route(`**/api/conversations/${cid}/chat/stream?*`, async (route) => {
		await expect
			.poll(async () => {
				const response = await page.request.get(`/api/conversations/${cid}`);
				return (await response.json()).summary.outcome;
			})
			.toBe('completed');
		await route.continue();
	});
	await page.reload();
	await expect(page.getByText('后台旅行建议已完成。', { exact: false })).toBeVisible();
	await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
});

for (const stopped of [false, true]) {
	test(`原生搜索后思考时切换会话和刷新，完整回放并${stopped ? '停止' : '完成'}`, async ({
		page
	}) => {
		const other = await (await page.request.post('/api/conversations')).json();
		const otherLoads: string[] = [];
		page.on('request', (request) => {
			if (
				request.method() === 'GET' &&
				new URL(request.url()).pathname === `/api/conversations/${other.id}`
			)
				otherLoads.push(request.url());
		});
		const prompt = `搜索恢复测试 ${Date.now()}`;
		await page.goto('/');
		await page.getByRole('textbox', { name: '旅行需求' }).fill('开始旅行');
		await page.getByRole('button', { name: '发送', exact: true }).click();
		await expect(page.getByText('收到你的旅行想法：开始旅行。', { exact: false })).toBeVisible();
		await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
		await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
		await page.getByRole('button', { name: '发送', exact: true }).click();
		const reply = '好的，继续。最后核实回程班车的班次，确认后即可锁定方案。';
		const search = page.getByText('搜索旅行资讯', { exact: true });
		const thinking = page.getByRole('status').filter({ hasText: '正在思考…' });
		await expect(page.getByText(reply, { exact: true })).toBeVisible();
		await expect(search).toHaveCount(1);
		await expect(thinking).toBeVisible();
		const url = page.url();
		const cid = new URL(page.url()).pathname.split('/').at(-1);
		const state = await (await page.request.get(`/api/conversations/${cid}`)).json();
		expect(state.summary.outcome).toBe('running');
		expect(JSON.stringify(state.messages)).not.toContain(reply);

		// 使用客户端导航，与截图中的 session 切换保持一致。
		await page.locator(`a[href="/chat/${other.id}"]`).click();
		await expect(page).toHaveURL(new RegExp(`/chat/${other.id}$`));
		await page.locator(`a[href="${new URL(url).pathname}"]`).click();
		await expect(page).toHaveURL(url);
		await expect(thinking).toBeVisible();
		await expect(page.getByText(reply, { exact: true })).toBeVisible();
		await expect(search).toHaveCount(1);
		await page.reload();
		await expect(thinking).toBeVisible();
		await expect(page.getByText(reply, { exact: true })).toBeVisible();
		await expect(search).toHaveCount(1);
		await expect(page.locator('article')).toHaveCount(4);
		await expect(page.getByText('核对北京时间', { exact: true })).toHaveCount(1);

		if (stopped) {
			await page.getByRole('button', { name: '停止', exact: true }).click();
		} else {
			const finished = await page.request.post(
				`/api/__test/finish-search?prompt=${encodeURIComponent(prompt)}`
			);
			expect(finished.ok()).toBe(true);
			await expect(page.getByRole('region', { name: '交通与住宿方案' })).toBeVisible();
		}
		await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
		await page.reload();
		await expect(page.getByText(reply, { exact: true })).toBeVisible();
		await expect(search).toHaveCount(1);
		expect(otherLoads).toHaveLength(1);
	});
}

async function cachedConversation(page: Page, id: string) {
	return page.evaluate(async (id) => {
		const db = await new Promise<IDBDatabase>((resolve, reject) => {
			const request = indexedDB.open('travel-agent', 1);
			request.onsuccess = () => resolve(request.result);
			request.onerror = () => reject(request.error);
		});
		try {
			return await new Promise<{ detail: Detail } | undefined>((resolve, reject) => {
				const request = db.transaction('conversations').objectStore('conversations').get(id);
				request.onsuccess = () => resolve(request.result);
				request.onerror = () => reject(request.error);
			});
		} finally {
			db.close();
		}
	}, id);
}

test('IndexedDB 先显示完整预览，慢速同步后接续后台结果', async ({ page }) => {
	const prompt = `搜索恢复测试 缓存 ${Date.now()}`;
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const text = '好的，继续。最后核实回程班车的班次，确认后即可锁定方案。';
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	const url = page.url();
	const id = new URL(url).pathname.split('/').at(-1)!;
	await expect.poll(async () => JSON.stringify(await cachedConversation(page, id))).toContain(text);
	let release!: () => void;
	const gate = new Promise<void>((resolve) => {
		release = resolve;
	});
	await page.route(`**/api/conversations/${id}`, async (route) => {
		await gate;
		await route.continue();
	});
	await page.reload();
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	await expect(page.getByText('正在同步最新进度…', { exact: true })).toBeVisible();
	await page.request.post(`/api/__test/finish-search?prompt=${encodeURIComponent(prompt)}`);
	release();
	await expect(page.getByRole('region', { name: '交通与住宿方案' })).toBeVisible();
	await expect(page.getByText('正在同步最新进度…', { exact: true })).toHaveCount(0);
	await expect(page.getByText(text, { exact: true })).toHaveCount(1);
	await expect(page.getByText('搜索旅行资讯', { exact: true })).toHaveCount(1);
});

for (const mode of ['清空 IndexedDB', 'IndexedDB 不可用', 'IndexedDB 写入失败']) {
	test(`${mode}仍能恢复原生搜索和当前文字`, async ({ page }) => {
		if (mode === 'IndexedDB 不可用')
			await page.addInitScript(() => {
				Object.defineProperty(window, 'indexedDB', {
					get() {
						throw new Error('缓存不可用');
					}
				});
			});
		if (mode === 'IndexedDB 写入失败')
			await page.addInitScript(() => {
				IDBObjectStore.prototype.put = () => {
					throw new DOMException('缓存空间不足', 'QuotaExceededError');
				};
			});
		const prompt = `搜索恢复测试 无缓存 ${Date.now()}`;
		await page.goto('/');
		await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
		await page.getByRole('button', { name: '发送', exact: true }).click();
		const text = '好的，继续。最后核实回程班车的班次，确认后即可锁定方案。';
		await expect(page.getByText(text, { exact: true })).toBeVisible();
		if (mode === '清空 IndexedDB') {
			// reload 的新文档在路由加载前清空缓存，覆盖无预览的完整服务端恢复路径。
			await page.addInitScript(() => {
				const request = indexedDB.open('travel-agent', 1);
				request.onsuccess = () => {
					const db = request.result;
					const transaction = db.transaction('conversations', 'readwrite');
					transaction.objectStore('conversations').clear();
					transaction.oncomplete = () => db.close();
				};
			});
		}
		await page.reload();
		await expect(page.getByText(text, { exact: true })).toBeVisible();
		await expect(page.getByText('搜索旅行资讯', { exact: true })).toHaveCount(1);
		await expect(page.getByRole('status').filter({ hasText: '正在思考…' })).toBeVisible();
		await page.getByRole('button', { name: '停止', exact: true }).click();
		await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
	});
}

test('接口离线仍可读取缓存，重新同步后恢复正常', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('离线阅读测试');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const text = '收到你的旅行想法：离线阅读测试。';
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
	const id = new URL(page.url()).pathname.split('/').at(-1)!;
	await expect.poll(async () => JSON.stringify(await cachedConversation(page, id))).toContain(text);
	await page.route('**/api/**', (route) => route.abort());
	await page.reload();
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: '重新同步', exact: true })).toBeVisible();
	await page.unroute('**/api/**');
	await page.getByRole('button', { name: '重新同步', exact: true }).click();
	await expect(page.getByRole('button', { name: '重新同步', exact: true })).toHaveCount(0);
	await expect(page.getByText(text, { exact: true })).toHaveCount(1);
});

test('旧运行缓存只作为预览，同步后以新运行完整进度为准且不重跑模型', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('旧运行缓存');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByText('收到你的旅行想法：旧运行缓存。', { exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
	const url = page.url();
	const id = new URL(url).pathname.split('/').at(-1)!;
	await expect
		.poll(async () => (await cachedConversation(page, id))?.detail.summary.outcome)
		.toBe('completed');
	const old = await cachedConversation(page, id);
	const prompt = `搜索恢复测试 新运行 ${Date.now()}`;
	await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const text = '好的，继续。最后核实回程班车的班次，确认后即可锁定方案。';
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	// 新文档消除上一页面尚未提交的缓存写入，再注入真实的旧运行缓存。
	await page.goto('/');
	await page.evaluate(async (old) => {
		const db = await new Promise<IDBDatabase>((resolve) => {
			const request = indexedDB.open('travel-agent', 1);
			request.onsuccess = () => resolve(request.result);
		});
		await new Promise<void>((resolve) => {
			const transaction = db.transaction('conversations', 'readwrite');
			transaction.objectStore('conversations').put(old);
			transaction.oncomplete = () => {
				db.close();
				resolve();
			};
		});
	}, old);
	let submissions = 0;
	page.on('request', (request) => {
		if (request.method() === 'POST' && request.url().endsWith(`/conversations/${id}/chat`))
			submissions++;
	});
	expect((await cachedConversation(page, id))!.detail.messages).toEqual(old!.detail.messages);
	await page.goto(url);
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	await expect(page.getByText('搜索旅行资讯', { exact: true })).toHaveCount(1);
	await expect(page.getByRole('status').filter({ hasText: '正在思考…' })).toBeVisible();
	expect(submissions).toBe(0);
	await page.getByRole('button', { name: '停止', exact: true }).click();
	await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
});

test('网络恢复后重新订阅后台运行，工具与文字不重复', async ({ page, context }) => {
	const prompt = `搜索恢复测试 网络 ${Date.now()}`;
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const text = '好的，继续。最后核实回程班车的班次，确认后即可锁定方案。';
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	let subscriptions = 0;
	let submissions = 0;
	page.on('request', (request) => {
		if (request.url().includes('/chat/stream?')) subscriptions++;
		if (request.method() === 'POST' && request.url().endsWith('/chat')) submissions++;
	});
	await context.setOffline(true);
	await context.setOffline(false);
	await expect.poll(() => subscriptions).toBeGreaterThan(0);
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	await page.request.post(`/api/__test/finish-search?prompt=${encodeURIComponent(prompt)}`);
	await expect(page.getByRole('region', { name: '交通与住宿方案' })).toBeVisible();
	await expect(page.getByText('搜索旅行资讯', { exact: true })).toHaveCount(1);
	await expect(page.getByText(text, { exact: true })).toHaveCount(1);
	expect(submissions).toBe(0);
});

test('失败运行刷新后保留已生成内容，恢复不会卡在同步状态', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('失败恢复测试');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByRole('alert')).toContainText('离线模型失败');
	await expect(page.getByText('失败前已经生成的建议。', { exact: true })).toBeVisible();
	await page.reload();
	await expect(page.getByText('失败前已经生成的建议。', { exact: true })).toBeVisible();
	await expect(page.getByRole('alert')).toContainText('离线模型失败');
	await expect(page.getByText('正在同步最新进度…', { exact: true })).toHaveCount(0);
});

test('服务端已删除会话返回 404 时清除本地预览和缓存', async ({ page }) => {
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill('删除缓存测试');
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const text = '收到你的旅行想法：删除缓存测试。';
	await expect(page.getByText(text, { exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
	const url = page.url();
	const id = new URL(url).pathname.split('/').at(-1)!;
	await expect
		.poll(async () => (await cachedConversation(page, id))?.detail.summary.outcome)
		.toBe('completed');
	await page.goto('/');
	expect((await page.request.delete(`/api/conversations/${id}`)).status()).toBe(204);
	await page.goto(url);
	await expect(page.getByRole('alert')).toContainText('会话不存在');
	await expect(page.getByText(text, { exact: true })).toHaveCount(0);
	await expect.poll(() => cachedConversation(page, id)).toBeUndefined();
	await page.reload();
	await expect(page.getByText('暂时无法打开', { exact: true })).toBeVisible();
});

test('健康连接重新可见时不重连，回复完成后只读取一次详情', async ({ page }) => {
	// 禁用缓存，避免缓存命中掩盖路由重验证产生的重复详情请求。
	await page.addInitScript(() => {
		Object.defineProperty(window, 'indexedDB', {
			get() {
				throw new Error('缓存不可用');
			}
		});
	});
	const prompt = `搜索恢复测试 可见 ${Date.now()}`;
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
	await page.getByRole('button', { name: '发送', exact: true }).click();
	await expect(page.getByRole('status').filter({ hasText: '正在思考…' })).toBeVisible();
	const id = new URL(page.url()).pathname.split('/').at(-1)!;
	let subscriptions = 0;
	let details = 0;
	page.on('request', (request) => {
		if (request.url().includes('/chat/stream?')) subscriptions++;
		if (new URL(request.url()).pathname === `/api/conversations/${id}`) details++;
	});
	await page.evaluate(async () => {
		document.dispatchEvent(new Event('visibilitychange'));
		await new Promise((resolve) => setTimeout(resolve, 100));
	});
	expect(subscriptions).toBe(0);
	expect(details).toBe(0);

	const list = page.waitForResponse(
		(response) => new URL(response.url()).pathname === '/api/conversations'
	);
	const detail = page.waitForResponse(
		(response) => new URL(response.url()).pathname === `/api/conversations/${id}`
	);
	await page.request.post(`/api/__test/finish-search?prompt=${encodeURIComponent(prompt)}`);
	await Promise.all([list, detail]);
	await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
	await expect(page.getByRole('region', { name: '交通与住宿方案' })).toBeVisible();
	expect(details).toBe(1);
	expect(subscriptions).toBe(0);
});

test('新会话在后台断流后重新可见时自动恢复', async ({ page }) => {
	// 仅在测试侧中断响应体，确定性覆盖浏览器后台丢失流连接的场景。
	await page.addInitScript(() => {
		const fetch = window.fetch.bind(window);
		window.fetch = async (input, init) => {
			const response = await fetch(input, init);
			if (init?.method !== 'POST' || !String(input).endsWith('/chat')) return response;
			const disconnected = new TransformStream({
				start(controller) {
					window.addEventListener(
						'test:disconnect-chat',
						() => {
							controller.error(new TypeError('network disconnected'));
						},
						{ once: true }
					);
				}
			});
			return new Response(response.body!.pipeThrough(disconnected), response);
		};
	});
	const prompt = `搜索恢复测试 后台 ${Date.now()}`;
	await page.goto('/');
	await page.getByRole('textbox', { name: '旅行需求' }).fill(prompt);
	await page.getByRole('button', { name: '发送', exact: true }).click();
	const text = '好的，继续。最后核实回程班车的班次，确认后即可锁定方案。';
	await expect(page.getByRole('status').filter({ hasText: '正在思考…' })).toBeVisible();
	let submissions = 0;
	page.on('request', (request) => {
		if (request.method() === 'POST' && request.url().endsWith('/chat')) submissions++;
	});
	await page.evaluate(() => {
		Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
		window.dispatchEvent(new Event('test:disconnect-chat'));
	});
	await expect(page.getByRole('alert')).toContainText('network disconnected');
	const resumed = page.waitForRequest((request) => request.url().includes('/chat/stream?'));
	await page.evaluate(() => {
		Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
		document.dispatchEvent(new Event('visibilitychange'));
	});
	await resumed;
	await expect(page.getByRole('alert')).toHaveCount(0);
	await expect(page.getByText(text, { exact: true })).toHaveCount(1);
	await expect(page.getByText('搜索旅行资讯', { exact: true })).toHaveCount(1);
	await page.request.post(`/api/__test/finish-search?prompt=${encodeURIComponent(prompt)}`);
	await expect(page.getByRole('region', { name: '交通与住宿方案' })).toBeVisible();
	expect(submissions).toBe(0);
});

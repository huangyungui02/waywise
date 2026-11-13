import { test as base, expect } from '@playwright/test';

type Tokens = { access_token: string; refresh_token: string; userId: string };
export const test = base.extend<{ tokens: Tokens }>({
	tokens: async ({ baseURL }, use) => {
		if (!baseURL) throw new Error('缺少测试前端地址');
		const response = await fetch('http://127.0.0.1:17933/api/auth/login', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username: 'offline', password: 'offline-test-password' })
		});
		const tokens = await response.json();
		const me = await fetch('http://127.0.0.1:17933/api/auth/me', {
			headers: { Authorization: `Bearer ${tokens.access_token}` }
		});
		await use({ ...tokens, userId: (await me.json()).id });
	},
	extraHTTPHeaders: async ({ tokens }, use) => {
		await use({ Authorization: `Bearer ${tokens.access_token}` });
	},
	storageState: async ({ tokens }, use) => {
		await use({
			cookies: [],
			origins: [
				{
					origin: 'http://127.0.0.1:5179',
					localStorage: [
						{
							name: 'waywise.auth',
							value: JSON.stringify({ refreshToken: tokens.refresh_token, userId: tokens.userId })
						}
					]
				}
			]
		});
	}
});
export { expect };
export type { Page } from '@playwright/test';

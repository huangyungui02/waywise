import { listConversations } from '#lib/chat/cache.js';
import { ApiError, currentUserId } from '#lib/api.js';
import { error, redirect } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';

export const ssr = false;
export const prerender = false;
export const load: LayoutLoad = async ({ depends, fetch, url }) => {
	depends('app:conversations');
	if (url.pathname === '/login') return { conversations: [] };
	if (!(await currentUserId())) redirect(307, '/login');
	try {
		return { conversations: await listConversations(fetch) };
	} catch (cause) {
		error(
			cause instanceof ApiError ? cause.status : 503,
			cause instanceof ApiError
				? cause.message
				: '无法连接服务器，请检查网络及后端地址、HTTPS 证书和跨域配置后重新打开。'
		);
	}
};

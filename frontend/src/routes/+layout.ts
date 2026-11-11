import { listConversations } from '#lib/chat/cache.js';
import { ApiError } from '#lib/api.js';
import { error } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';

export const ssr = false;
export const prerender = false;
export const load: LayoutLoad = async ({ depends, fetch }) => {
	depends('app:conversations');
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

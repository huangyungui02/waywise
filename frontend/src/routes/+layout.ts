import { listConversations } from '#lib/chat/cache.js';
import type { LayoutLoad } from './$types';

export const ssr = false;
export const prerender = false;
export const load: LayoutLoad = async ({ depends, fetch }) => {
	depends('app:conversations');
	return { conversations: await listConversations(fetch) };
};

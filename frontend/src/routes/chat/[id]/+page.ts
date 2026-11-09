import { error } from '@sveltejs/kit';
import { loadConversation } from '#lib/chat/cache.js';
import { ApiError } from '#lib/api.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	try {
		return { loaded: await loadConversation(params.id, fetch) };
	} catch (cause) {
		if (cause instanceof ApiError) error(cause.status, cause.message);
		throw cause;
	}
};

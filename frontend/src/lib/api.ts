import type { UIMessage } from 'ai';
import { Capacitor } from '@capacitor/core';
import { SecureStorage } from '@aparajita/capacitor-secure-storage';

export function apiUrl(path: string): string {
	return `${(import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')}/api${path}`;
}

export function apiHeaders(headers?: HeadersInit): Record<string, string> {
	const result = new Headers(headers);
	result.set('Authorization', `Bearer ${accessToken ?? ''}`);
	return Object.fromEntries(result);
}

export interface Conversation {
	id: string;
	title: string;
	outcome: string;
	updated_at: string;
}
interface Transport {
	type: 'train' | 'flight' | 'bus' | 'drive' | 'taxi' | 'ferry';
	number: string | null;
	departure_station: string;
	arrival_station: string;
	departure_time: string;
	arrival_time: string;
	purchase_url: string | null;
	purchased: boolean;
}
interface Stay {
	city: string;
	hotel: string;
	address: string;
	check_in: string;
	check_out: string;
	purchase_url: string | null;
	booked: boolean;
}
export interface TravelArrangements {
	transports: Transport[];
	stays: Stay[];
}
export interface Recovery {
	run_id: string;
	cursor: string | null;
	messages: UIMessage[];
}
export interface Detail {
	products?: SavedProduct[];
	recovery: Recovery | null;
	summary: Conversation;
	messages: UIMessage[];
	arrangements: TravelArrangements | null;
	pending_arrangements: TravelArrangements | null;
	pending_id: string | null;
	confirmed_id: string | null;
}

export interface Product {
	name: string;
	description: string;
	purchase_url: string;
	image_url?: string | null;
	price?: string | null;
}

export interface SavedProduct extends Product {
	id: string;
	updated_at: string;
}

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

export async function api<T>(
	path: string,
	init?: RequestInit,
	request: typeof fetch = fetch
): Promise<T> {
	const response = await authenticatedFetch(apiUrl(path), init, request);
	if (!response.ok) {
		const body = await response.json().catch(() => ({}));
		throw new ApiError(
			response.status,
			typeof body.detail === 'string' ? body.detail : `请求失败 (${response.status})`
		);
	}
	return response.status === 204 ? (undefined as T) : response.json();
}

interface Tokens {
	access_token: string;
	refresh_token: string;
}
interface LoginState {
	refreshToken: string;
	userId: string;
}
const storageKey = 'waywise.auth';
let accessToken: string | null = null;
let identity: LoginState | null = null;
let refreshing: Promise<void> | null = null;

async function readLogin(): Promise<LoginState | null> {
	if (identity) return identity;
	identity = Capacitor.isNativePlatform()
		? ((await SecureStorage.get(storageKey)) as unknown as LoginState | null)
		: JSON.parse(localStorage.getItem(storageKey) ?? 'null');
	return identity;
}

async function saveLogin(tokens: Tokens, userId: string) {
	const state = { refreshToken: tokens.refresh_token, userId };
	if (Capacitor.isNativePlatform()) await SecureStorage.set(storageKey, state);
	else localStorage.setItem(storageKey, JSON.stringify(state));
	identity = state;
	accessToken = tokens.access_token;
}

export async function clearLogin() {
	accessToken = null;
	identity = null;
	if (Capacitor.isNativePlatform()) await SecureStorage.remove(storageKey);
	else localStorage.removeItem(storageKey);
}

export async function currentUserId(): Promise<string | null> {
	return (await readLogin())?.userId ?? null;
}

async function authRequest<T>(path: string, body: unknown): Promise<T> {
	const response = await fetch(apiUrl(`/auth/${path}`), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	if (!response.ok) {
		const data = await response.json().catch(() => ({}));
		throw new ApiError(
			response.status,
			typeof data.detail === 'string' ? data.detail : '登录请求失败'
		);
	}
	return response.json();
}

export async function login(username: string, password: string) {
	const tokens = await authRequest<Tokens>('login', { username, password });
	const response = await fetch(apiUrl('/auth/me'), {
		headers: { Authorization: `Bearer ${tokens.access_token}` }
	});
	if (!response.ok) throw new ApiError(response.status, '无法读取账号信息');
	const user: { id: string } = await response.json();
	await saveLogin(tokens, user.id);
}

async function refreshLogin() {
	if (!refreshing) {
		refreshing = (async () => {
			const state = await readLogin();
			if (!state) throw new ApiError(401, '请先登录');
			try {
				const tokens = await authRequest<Tokens>('refresh', { refresh_token: state.refreshToken });
				await saveLogin(tokens, state.userId);
			} catch (error) {
				if (error instanceof ApiError && error.status === 401) await clearLogin();
				throw error;
			}
		})().finally(() => {
			refreshing = null;
		});
	}
	return refreshing;
}

export async function authenticatedFetch(
	input: RequestInfo | URL,
	init?: RequestInit,
	request: typeof fetch = fetch
): Promise<Response> {
	try {
		if (!accessToken) await refreshLogin();
		const usedToken = accessToken;
		let response = await request(input, { ...init, headers: apiHeaders(init?.headers) });
		if (response.status === 401) {
			// 其他并发请求可能已经刷新成功，避免重复轮换。
			if (accessToken === usedToken) await refreshLogin();
			response = await request(input, { ...init, headers: apiHeaders(init?.headers) });
			if (response.status === 401) {
				await clearLogin();
				throw new ApiError(401, '请重新登录');
			}
		}
		return response;
	} catch (error) {
		if (error instanceof ApiError && error.status === 401 && location.pathname !== '/login') {
			location.replace('/login');
		}
		throw error;
	}
}

export async function logout() {
	await api('/auth/logout', { method: 'POST' });
	await clearLogin();
}

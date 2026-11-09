import type { UIMessage } from 'ai';

export interface Conversation { id: string; title: string; outcome: string; updated_at: string }
interface Transport {
  type: 'train' | 'flight' | 'bus'; name: string; number: string | null; departure_point: string; arrival_point: string;
  departure_time: string; arrival_time: string; purchase_url: string | null; purchased: boolean;
}
interface Stay { hotel: string; address: string; check_in: string; check_out: string; purchase_url: string | null; booked: boolean }
export interface Trip { origin: string; destination: string; outbound: Transport; inbound: Transport; stays: Stay[] }
export interface Recovery { run_id: string; cursor: string | null; messages: UIMessage[] }
export interface Detail { recovery: Recovery | null; summary: Conversation; messages: UIMessage[]; trip: Trip | null; pending_trip: Trip | null; pending_id: string | null; confirmed_id: string | null }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof body.detail === 'string' ? body.detail : `请求失败 (${response.status})`);
  }
  return response.status === 204 ? undefined as T : response.json();
}

import type { UIMessage } from 'ai';

export interface Conversation { id: string; title: string; outcome: string; updated_at: string }
interface Transport {
  type: 'train' | 'flight' | 'bus'; name: string; number: string | null; departure_point: string; arrival_point: string;
  departure_time: string; arrival_time: string; purchase_url: string | null; purchased: boolean;
}
interface Stay { hotel: string; address: string; check_in: string; check_out: string; purchase_url: string | null; booked: boolean }
export interface Trip { origin: string; destination: string; outbound: Transport; inbound: Transport; stays: Stay[] }
export interface Detail { summary: Conversation; messages: UIMessage[]; trip: Trip | null }

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `请求失败 (${response.status})`);
  }
  return response.status === 204 ? undefined as T : response.json();
}

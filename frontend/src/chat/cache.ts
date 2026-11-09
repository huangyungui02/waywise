import type { UIMessage } from "ai";
import { api, type Conversation, type Detail } from "@/api";

interface CachedConversation {
  id: string;
  schemaVersion: 2;
  runId: string;
  cursor: string;
  detail: Detail;
}
export interface LoadedConversation { detail: Detail; cached: boolean }

// 会话 ID 不复用；删除后禁止在途写入或组件卸载再次创建缓存。
const forgotten = new Set<string>();

// 缓存可以被禁用或随时清空；所有读写失败都退回服务端恢复。
async function access<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => Pick<IDBRequest<T>, "result">): Promise<T | undefined> {
  let db: IDBDatabase | undefined;
  try {
    db = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open("travel-agent", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("conversations", { keyPath: "id" });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error("缓存暂不可用"));
    });
    return await new Promise<T>((resolve, reject) => {
      const transaction = db!.transaction("conversations", mode);
      const request = action(transaction.objectStore("conversations"));
      transaction.oncomplete = () => resolve(request.result);
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } catch {
    return undefined;
  } finally {
    db?.close();
  }
}

export async function loadConversation(id: string, signal?: AbortSignal): Promise<LoadedConversation> {
  const cached = await access<CachedConversation | undefined>("readonly", (store) => store.get(id));
  signal?.throwIfAborted();
  if (cached?.schemaVersion === 2) return { detail: cached.detail, cached: true };
  return { detail: await api<Detail>(`/conversations/${id}`, { signal }), cached: false };
}

export function cacheConversation(detail: Detail, runId: string, cursor: string, messages: UIMessage[]) {
  return access<IDBValidKey | undefined>("readwrite", (store) => forgotten.has(detail.summary.id)
    ? store.delete(detail.summary.id)
    : store.put({
      id: detail.summary.id, schemaVersion: 2, runId, cursor,
      detail: { ...detail, messages, recovery: null },
    } satisfies CachedConversation));
}

export function forgetConversation(id: string) {
  forgotten.add(id);
  return access("readwrite", (store) => store.delete(id));
}

export async function listConversations(): Promise<Conversation[]> {
  try {
    return await api<Conversation[]>("/conversations");
  } catch (error) {
    const cached = await access<CachedConversation[]>("readonly", (store) => store.getAll());
    if (!cached?.length) throw error;
    return cached.filter((item) => item.schemaVersion === 2)
      .map((item) => item.detail.summary)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }
}

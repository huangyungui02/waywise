import { useEffect, useRef, useState } from "react";
import { useRevalidator } from "react-router";
import { Chat as SDKChat, useChat } from "@ai-sdk/react";
import { api, ApiError, type Detail } from "@/api";
import { cacheConversation, forgetConversation, type LoadedConversation } from "./cache";
import { ConversationTransport } from "./transport";

export function useConversation(loaded: LoadedConversation) {
  const [detail, setDetail] = useState(loaded.detail);
  const [recovering, setRecovering] = useState(loaded.cached || Boolean(loaded.detail.recovery));
  const preview = useRef(loaded.detail.messages);
  const replayTarget = useRef<Detail["recovery"]>(null);
  const detailRef = useRef(detail);
  const pendingMessages = useRef<Detail["messages"] | null>(null);
  const cacheTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const revalidator = useRevalidator();
  const [chat] = useState(
    () => new SDKChat({
      id: detail.summary.id,
      messages: detail.messages,
      transport: new ConversationTransport(
        detail.summary.id,
        (signal) => {
          if (!replayTarget.current) preview.current = chat.messages;
          setRecovering(true);
          return refreshDetail(signal);
        },
        (saved) => {
          replayTarget.current = saved.recovery;
          chat.messages = saved.recovery?.messages ?? saved.messages;
          if (!saved.recovery) {
            setRecovering(false);
            pendingMessages.current = chat.messages;
            flushCache();
          }
        },
      ),
      onData: (part) => {
        if (part.type === "data-progress") {
          const target = replayTarget.current;
          if (target) {
            const { runId, cursor } = part.data as { runId: string; cursor: string };
            if (runId !== target.run_id || target.cursor === null) return;
            const [time, sequence] = cursor.split("-").map(BigInt);
            const [targetTime, targetSequence] = target.cursor.split("-").map(BigInt);
            if (time < targetTime || (time === targetTime && sequence < targetSequence)) return;
            replayTarget.current = null;
          }
          setRecovering(false);
          pendingMessages.current = chat.messages;
          if (cacheTimer.current === null)
            cacheTimer.current = setTimeout(flushCache, 250);
        }
      },
      onFinish: ({ isAbort, isDisconnect }) => {
        if (!isAbort && !isDisconnect) {
          replayTarget.current = null;
          setRecovering(false);
          pendingMessages.current = chat.messages;
          void refreshDetail().then(flushCache).catch(() => {});
          revalidator.revalidate();
        }
      },
    }),
  );
  const { sendMessage, stop, resumeStream, status, error } = useChat({
    chat,
    experimental_throttle: 100,
    // 空白会话不重连；首条消息发出后也启用 SDK 的可见性恢复。
    resume: loaded.cached || Boolean(loaded.detail.recovery) || chat.messages.length > 0,
  });

  async function refreshDetail(signal?: AbortSignal) {
    try {
      const saved = await api<Detail>(`/conversations/${detailRef.current.summary.id}`, { signal });
      detailRef.current = saved;
      setDetail(saved);
      return saved;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        preview.current = [];
        replayTarget.current = null;
        pendingMessages.current = null;
        await forgetConversation(detailRef.current.summary.id);
        chat.messages = [];
        setRecovering(false);
      }
      throw error;
    }
  }

  function flushCache() {
    if (cacheTimer.current !== null) clearTimeout(cacheTimer.current);
    cacheTimer.current = null;
    const messages = pendingMessages.current;
    if (messages) void cacheConversation(detailRef.current, structuredClone(messages));
  }

  async function synchronize() {
    await stop();
    await resumeStream();
  }

  useEffect(() => {
    if (!loaded.cached && !loaded.detail.recovery && loaded.detail.messages.length) {
      pendingMessages.current = chat.messages;
      flushCache();
    }
    const online = () => {
      if (document.visibilityState === "visible") void synchronize();
    };
    const save = () => flushCache();
    window.addEventListener("pagehide", save);
    window.addEventListener("online", online);
    return () => {
      window.removeEventListener("pagehide", save);
      window.removeEventListener("online", online);
      flushCache();
      void stop();
    };
  }, [chat, stop, resumeStream]);

  return { detail, messages: recovering ? preview.current : chat.messages, sendMessage, status, error, recovering, synchronize };
}

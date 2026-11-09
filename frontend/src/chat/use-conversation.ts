import { useEffect, useRef, useState } from "react";
import { useRevalidator } from "react-router";
import { Chat as SDKChat, useChat } from "@ai-sdk/react";
import { api, ApiError, type Detail } from "@/api";
import { cacheConversation, forgetConversation, type LoadedConversation } from "./cache";
import { ConversationTransport } from "./transport";

export function useConversation(loaded: LoadedConversation) {
  const initialDetail = loaded.detail;
  const [boot] = useState(loaded);
  const [detail, setDetail] = useState(initialDetail);
  const [recovering, setRecovering] = useState(loaded.cached || Boolean(initialDetail.recovery));
  const preview = useRef(initialDetail.messages);
  const firstSnapshot = useRef<Detail | null>(loaded.cached ? null : initialDetail);
  const detailRef = useRef(detail);
  detailRef.current = detail;
  const checkpoint = useRef<{ runId: string; cursor: string; messages: Detail["messages"] } | null>(null);
  const cacheTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const revalidator = useRevalidator();
  const [chat] = useState(
    () =>
      new SDKChat({
        id: detail.summary.id,
        messages: detail.messages,
        transport: new ConversationTransport(
          detail.summary.id,
          async (signal) => {
            try {
              const saved = firstSnapshot.current ?? await api<Detail>(`/conversations/${detail.summary.id}`, { signal });
              firstSnapshot.current = null;
              return saved;
            } catch (error) {
              if (error instanceof ApiError && error.status === 404) {
                preview.current = [];
                checkpoint.current = null;
                await forgetConversation(detail.summary.id);
                chat.messages = [];
                setRecovering(false);
              }
              throw error;
            }
          },
          (saved) => {
            setDetail(saved);
            chat.messages = saved.recovery?.messages ?? saved.messages;
            if (!saved.recovery) {
              setRecovering(false);
              checkpoint.current = { runId: "", cursor: "0-0", messages: structuredClone(saved.messages) };
              detailRef.current = saved;
              flushCache();
            }
          },
        ),
        onError: () => setRecovering(false),
        onData: (part) => {
          if (part.type === "data-progress") {
            const progress = part.data as { runId: string; cursor: string; restored?: boolean };
            if (progress.restored) setRecovering(false);
            checkpoint.current = { ...progress, messages: structuredClone(chat.messages) };
            if (cacheTimer.current === null)
              cacheTimer.current = setTimeout(flushCache, 250);
          }
        },
        onFinish: ({ isAbort, isDisconnect }) => {
          if (!isAbort && !isDisconnect) {
            void api<Detail>(`/conversations/${detail.summary.id}`).then((saved) => {
              detailRef.current = saved;
              setDetail(saved);
              flushCache();
            }).catch(() => {});
            revalidator.revalidate();
          }
        },
      }),
  );
  const { messages: liveMessages, sendMessage, stop, resumeStream, status, error } = useChat({
    chat,
    resume: boot.cached || Boolean(boot.detail.recovery),
  });

  function flushCache() {
    if (cacheTimer.current !== null) clearTimeout(cacheTimer.current);
    cacheTimer.current = null;
    const saved = checkpoint.current;
    if (saved) void cacheConversation(detailRef.current, saved.runId, saved.cursor, saved.messages);
  }

  useEffect(() => { if (!loaded.cached) setDetail(initialDetail); }, [initialDetail, loaded.cached]);
  useEffect(() => {
    if (!boot.cached && !boot.detail.recovery && boot.detail.messages.length) {
      checkpoint.current = { runId: "", cursor: "0-0", messages: structuredClone(boot.detail.messages) };
      flushCache();
    }
  }, [boot]);

  const messages = recovering ? preview.current : liveMessages;

  async function synchronize() {
    preview.current = chat.messages;
    setRecovering(true);
    firstSnapshot.current = null;
    await stop();
    await resumeStream();
  }

  useEffect(() => {
    const resume = () => {
      if (document.visibilityState === "visible") void synchronize();
    };
    const save = () => flushCache();
    window.addEventListener("pagehide", save);
    window.addEventListener("online", resume);
    document.addEventListener("visibilitychange", resume);
    return () => {
      window.removeEventListener("pagehide", save);
      window.removeEventListener("online", resume);
      document.removeEventListener("visibilitychange", resume);
    };
  }, [chat, stop, resumeStream]);

  useEffect(
    () => () => {
      flushCache();
      void stop();
    },
    [stop],
  );
  return { detail, messages, sendMessage, status, error, recovering, synchronize };
}

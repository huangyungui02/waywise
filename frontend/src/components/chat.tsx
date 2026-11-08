import { useEffect, useMemo, useRef, useState } from "react";
import { useLoaderData, useLocation, useRevalidator } from "react-router";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import {
  ArrowDown,
  CircleAlert,
  LoaderCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { Detail } from "@/api";
import { Message } from "./message";
import { TripCard } from "./trip-card";
import { api } from "@/api";
import { TravelForm, travelPrompt } from "./travel-form";
import { Composer } from "./composer";

export function ChatRoute() {
  const detail = useLoaderData() as Detail;
  return <Chat key={detail.summary.id} detail={detail} />;
}

function Chat({ detail }: { detail: Detail }) {
  const revalidator = useRevalidator();
  const location = useLocation();
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const initialSent = useRef(false);
  const scroller = useRef<HTMLDivElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [transport] = useState(
    () =>
      new DefaultChatTransport({
        api: `/api/conversations/${detail.summary.id}/chat`,
        prepareSendMessagesRequest: ({ id, messages }) => ({
          body: { id, trigger: "submit-message", messages: messages.slice(-1) },
        }),
      }),
  );
  const { messages, sendMessage, stop, status, error } = useChat({
    id: detail.summary.id,
    messages: detail.messages,
    transport,
    onFinish: () => {
      revalidator.revalidate();
    },
  });

  // 聚合连续的助手消息，确保刷新后工具调用记录依然整齐聚合在一个滚动容器内
  const displayMessages = useMemo(() => {
    const result: typeof messages = [];
    for (const m of messages) {
      const prev = result[result.length - 1];
      if (prev && prev.role === "assistant" && m.role === "assistant") {
        result[result.length - 1] = {
          ...prev,
          parts: [...prev.parts, ...m.parts],
        };
      } else {
        result.push(m);
      }
    }
    return result;
  }, [messages]);

  useEffect(() => {
    const prompt = (location.state as { prompt?: string } | null)?.prompt;
    if (!initialSent.current && !detail.messages.length && prompt) {
      initialSent.current = true;
      void sendMessage({ text: prompt });
    }
  }, [location.state, detail.messages.length, sendMessage]);

  const running = status === "submitted" || status === "streaming";

  useEffect(
    () => () => {
      void stop();
    },
    [stop],
  );

  useEffect(() => {
    if (atBottom && scroller.current)
      scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [displayMessages, atBottom]);

  return (
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      <div
        ref={scroller}
        onScroll={(event) => {
          const el = event.currentTarget;
          setAtBottom(
            el.scrollHeight - el.scrollTop - el.clientHeight < 80,
          );
        }}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 sm:px-8"
      >
        <div className="mx-auto max-w-2xl space-y-6 py-6 sm:py-8">
          {!displayMessages.length && (
            <TravelForm values={values} onChange={setValues} />
          )}

          {displayMessages.map((message) => (
            <Message message={message} key={message.id} detail={detail} busy={running || confirming} onConfirm={async (id) => {
              setConfirming(true);
              setConfirmError(null);
              try {
                await api(`/conversations/${detail.summary.id}/proposals/${encodeURIComponent(id)}/confirm`, { method: "POST" });
                revalidator.revalidate();
                setAtBottom(true);
                await sendMessage({ text: "已确认卡片中的交通和住宿方案，请继续规划每日行程。" });
              } catch (error) {
                setConfirmError(error instanceof Error ? error.message : "确认失败，请重试");
                revalidator.revalidate();
              } finally {
                setConfirming(false);
              }
            }} />
          ))}

          {detail.trip && !detail.confirmed_id && (
            <section aria-label="交通与住宿方案" className="pure-capsule p-4 sm:p-5">
              <TripCard trip={detail.trip} status="confirmed" />
            </section>
          )}

          {status === "submitted" && (
            <div
              role="status"
              className="flex items-center gap-2 rounded-full bg-white/70 px-4 py-1.5 text-xs text-muted-foreground backdrop-blur-md w-fit shadow-xs"
            >
              <LoaderCircle className="size-3 animate-spin text-primary" />
              <span className="font-serif">正在整理你的旅行需求…</span>
            </div>
          )}

          {(error || confirmError) && (
            <Alert variant="destructive" className="rounded-xl bg-destructive/5 backdrop-blur-md">
              <CircleAlert />
              <AlertDescription className="break-words text-xs leading-relaxed">
                {confirmError || error?.message}
                。已保存的记录可重新打开查看，或继续发送消息。
              </AlertDescription>
            </Alert>
          )}

          {detail.summary.outcome === "cancelled" &&
            !running &&
            !error && (
              <Alert className="rounded-xl bg-white/60 backdrop-blur-md">
                <CircleAlert />
                <AlertDescription className="text-xs leading-relaxed">
                  上次回复未完成，已保留可恢复的记录，可以继续咨询。
                </AlertDescription>
              </Alert>
            )}
        </div>
      </div>

      {/* 回到最新消息 */}
      {!atBottom && (
        <Button
          variant="outline"
          size="icon"
          aria-label="回到最新消息"
          className="absolute bottom-24 left-1/2 -translate-x-1/2 size-8 rounded-full bg-white/90 shadow-md backdrop-blur-md hover:bg-white"
          onClick={() => {
            setAtBottom(true);
            if (scroller.current) {
              scroller.current.scrollTop = scroller.current.scrollHeight;
            }
          }}
        >
          <ArrowDown className="size-4" />
        </Button>
      )}

      <Composer
        busy={running || confirming}
        hasFormValues={!displayMessages.length && Object.values(values).some((value) => value.trim())}
        onStop={() => void stop()}
        onSend={async (text) => {
          const input = displayMessages.length ? text : travelPrompt(values, text);
          setAtBottom(true);
          await sendMessage({ text: input });
        }}
      />
    </div>
  );
}

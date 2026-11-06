import { useEffect, useRef, useState } from "react";
import { useLoaderData, useLocation, useRevalidator } from "react-router";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  CircleAlert,
  Compass,
  LoaderCircle,
  Route,
  Square,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
} from "@/components/ui/sheet";
import type { Detail } from "@/api";
import { Message } from "./message";
import { TripPanel } from "./trip-panel";

export function ChatRoute() {
  const detail = useLoaderData() as Detail;
  return <Chat key={detail.summary.id} detail={detail} />;
}

function Chat({ detail }: { detail: Detail }) {
  const revalidator = useRevalidator();
  const location = useLocation();
  const [text, setText] = useState(
    !detail.messages.length
      ? (location.state as { prompt?: string } | null)?.prompt || ""
      : "",
  );
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
  }, [messages, atBottom]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() || running) return;
    const input = text.trim();
    setText("");
    setAtBottom(true);
    await sendMessage({ text: input });
  }

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border/80 bg-background/80 px-5 backdrop-blur-xs sm:px-8">
        <h1 className="truncate text-sm font-medium text-foreground">
          {detail.summary.title}
        </h1>
        <Sheet>
          <SheetTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 shrink-0 gap-1.5 rounded-full text-xs xl:hidden"
            >
              <Route className="size-3.5 text-primary" />
              旅行安排
            </Button>
          </SheetTrigger>
          <SheetContent className="overflow-y-auto">
            <SheetHeader>
              <SheetTitle>这次旅行</SheetTitle>
              <SheetDescription>往返交通与住宿安排</SheetDescription>
            </SheetHeader>
            <div className="px-5 pb-8">
              <TripPanel trip={detail.trip} />
            </div>
          </SheetContent>
        </Sheet>
      </header>
      <div className="flex min-h-0 min-w-0 flex-1">
        <div className="relative flex min-w-0 flex-1 flex-col">
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
              {!messages.length && (
                <div className="rounded-2xl border border-border/70 bg-card/60 p-6 sm:p-8">
                  <span className="mb-4 flex size-10 items-center justify-center rounded-xl bg-secondary text-primary">
                    <Compass className="size-5" strokeWidth={1.6} />
                  </span>
                  <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
                    说说这次旅行吧。
                  </h2>
                  <p className="mt-2.5 text-sm leading-6 text-muted-foreground">
                    从哪里出发，想去哪个城市，准备什么时候去？
                    <br />
                    已经订好的车票和酒店，也可以直接告诉我。
                  </p>
                  <Button
                    variant="outline"
                    className="mt-5 h-auto max-w-full whitespace-normal rounded-full bg-card px-4 py-2 text-left text-xs shadow-2xs"
                    onClick={() =>
                      setText("我想规划一次周末旅行，车票和酒店还没订。")
                    }
                  >
                    还没有具体计划，帮我一起想想
                    <ArrowRight className="size-3.5 shrink-0 text-muted-foreground" />
                  </Button>
                </div>
              )}
              {messages.map((message) => (
                <Message message={message} key={message.id} />
              ))}
              {status === "submitted" && (
                <div
                  role="status"
                  className="flex items-center gap-2 text-xs text-muted-foreground"
                >
                  <LoaderCircle className="size-3.5 animate-spin text-primary" />
                  正在整理你的旅行需求…
                </div>
              )}
              {error && (
                <Alert variant="destructive">
                  <CircleAlert />
                  <AlertDescription className="break-words text-xs leading-6">
                    {error.message}
                    。已保存的记录可重新打开查看，或继续发送消息。
                  </AlertDescription>
                </Alert>
              )}
              {detail.summary.outcome === "cancelled" && !running && !error && (
                <Alert>
                  <CircleAlert />
                  <AlertDescription className="text-xs leading-6">
                    上次回复未完成，已保留可恢复的记录，可以继续咨询。
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </div>
          {!atBottom && (
            <Button
              variant="outline"
              size="icon"
              aria-label="回到最新消息"
              className="absolute bottom-36 left-1/2 size-8 -translate-x-1/2 rounded-full bg-card shadow-sm"
              onClick={() => setAtBottom(true)}
            >
              <ArrowDown className="size-4" />
            </Button>
          )}
          <div className="shrink-0 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 sm:px-8 sm:pb-4">
            <form
              onSubmit={submit}
              className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-2 shadow-xs transition-all focus-within:border-primary/40 focus-within:ring-3 focus-within:ring-primary/8"
            >
              <Textarea
                aria-label="旅行需求"
                placeholder="输入目的地、出行日期，或已有的车票与酒店安排…"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    e.currentTarget.form?.requestSubmit();
                  }
                }}
                className="max-h-36 min-h-14 resize-none border-0 bg-transparent px-2.5 py-2 text-sm shadow-none focus-visible:ring-0"
              />
              <div className="flex items-center justify-between gap-2 px-2 pb-0.5 pt-1">
                <span className="text-[11px] text-muted-foreground">
                  <span className="hidden sm:inline">
                    Enter 发送 · Shift + Enter 换行
                  </span>
                  <span className="sm:hidden">报价与库存以预订页面为准</span>
                </span>
                {running ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => void stop()}
                    className="h-8 gap-1.5 rounded-xl px-3 text-xs"
                  >
                    停止
                    <Square className="size-2.5 fill-current" />
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!text.trim()}
                    className="h-8 gap-1.5 rounded-xl px-3.5 text-xs"
                  >
                    发送
                    <ArrowUp className="size-3.5" />
                  </Button>
                )}
              </div>
            </form>
            <p className="mt-2 hidden text-center text-[11px] text-muted-foreground sm:block">
              报价与库存以预订页面为准 · 购票与订房需由你自行完成
            </p>
          </div>
        </div>
        <aside
          aria-label="旅行基础安排"
          className="hidden w-76 shrink-0 overflow-y-auto border-l border-border/80 bg-sidebar/40 px-5 py-6 xl:block"
        >
          <TripPanel trip={detail.trip} />
        </aside>
      </div>
    </>
  );
}

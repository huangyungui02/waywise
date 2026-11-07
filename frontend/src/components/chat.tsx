import { useEffect, useMemo, useRef, useState } from "react";
import { useLoaderData, useLocation, useRevalidator } from "react-router";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import {
  ArrowDown,
  ArrowUp,
  CircleAlert,
  Compass,
  Edit3,
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
import { TravelForm, readBrief } from "./travel-form";

export function ChatRoute() {
  const detail = useLoaderData() as Detail;
  return <Chat key={detail.summary.id} detail={detail} />;
}

function formatTitle(title: string): string {
  if (title.startsWith("这次旅行的想法：")) {
    return "知途 · 旅行手札";
  }
  return title;
}

function Chat({ detail }: { detail: Detail }) {
  const revalidator = useRevalidator();
  const location = useLocation();
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);
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

  const briefText = [...displayMessages]
    .reverse()
    .filter((m) => m.role === "user")
    .flatMap((m) => m.parts)
    .find((p) => p.type === "text" && readBrief(p.text));
  const brief =
    briefText?.type === "text" ? readBrief(briefText.text) : undefined;

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

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() || running) return;
    const input = text.trim();
    setText("");
    setAtBottom(true);
    await sendMessage({ text: input });
  }

  const cleanTitle = formatTitle(detail.summary.title);

  return (
    <>
      {/* 极简无界毛玻璃导航 */}
      <header className="flex h-14 shrink-0 items-center justify-between gap-3 bg-white/50 px-6 backdrop-blur-xl sm:px-8">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Compass className="size-3.5" />
          </span>
          <h1 className="truncate font-serif text-sm font-medium tracking-wide text-foreground">
            {cleanTitle}
          </h1>
        </div>

        {/* 移动端安排抽屉入口 */}
        <Sheet>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 shrink-0 gap-1.5 rounded-full bg-black/[0.03] text-xs hover:bg-black/[0.06] xl:hidden"
            >
              <Route className="size-3.5 text-primary" />
              <span>旅行安排</span>
            </Button>
          </SheetTrigger>
          <SheetContent className="overflow-y-auto bg-[#f8f6f0]">
            <SheetHeader className="pb-2">
              <SheetTitle className="font-serif text-base tracking-wide">
                这次旅行
              </SheetTitle>
              <SheetDescription className="text-xs">
                往返交通与住宿安排清单
              </SheetDescription>
            </SheetHeader>
            <div className="px-5 pb-8 pt-3">
              <TripPanel trip={detail.trip} />
            </div>
          </SheetContent>
        </Sheet>
      </header>

      {/* 纯净意境摘要条 (Brief Bar) */}
      {brief && (
        <div className="flex items-center justify-between gap-3 bg-white/35 px-6 py-2.5 text-xs backdrop-blur-md sm:px-8">
          <div className="flex min-w-0 items-center gap-2">
            <span className="size-1.5 shrink-0 rounded-full bg-primary/80" />
            <span className="truncate text-muted-foreground">
              <strong className="font-medium text-foreground">
                {[brief["出发城市"], brief["目的城市"]].filter(Boolean).join(" → ") ||
                  "旅行心愿"}
              </strong>
              {" · "}
              {brief["出发日期"] || "日期待定"}
              {brief["返回日期"] ? ` — ${brief["返回日期"]}` : ""}
              {brief["成人"] ? ` · ${brief["成人"]}位成人` : ""}
              {brief["老人"] ? ` · ${brief["老人"]}位老人` : ""}
              {brief["儿童"] ? ` · ${brief["儿童"]}位儿童` : ""}
              {brief["预算金额"]
                ? ` · ¥${brief["预算金额"]}（${brief["预算口径"] || "口径待定"}）`
                : ""}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            disabled={running}
            onClick={() => setEditing((v) => !v)}
            className="h-7 shrink-0 gap-1 rounded-full px-2.5 text-xs text-primary hover:bg-primary/10"
          >
            <Edit3 className="size-3" />
            修改需求
          </Button>
        </div>
      )}

      {/* 核心双栏视口 */}
      <div className="flex min-h-0 min-w-0 flex-1">
        {/* 对话区 */}
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
              {(!displayMessages.length || editing) && (
                <TravelForm
                  initial={brief}
                  busy={running}
                  onCancel={editing ? () => setEditing(false) : undefined}
                  onSubmit={(input) => {
                    setEditing(false);
                    void sendMessage({ text: input });
                  }}
                />
              )}

              {displayMessages.map((message) => (
                <Message message={message} key={message.id} />
              ))}

              {status === "submitted" && (
                <div
                  role="status"
                  className="flex items-center gap-2 rounded-full bg-white/70 px-4 py-1.5 text-xs text-muted-foreground backdrop-blur-md w-fit shadow-xs"
                >
                  <LoaderCircle className="size-3 animate-spin text-primary" />
                  <span className="font-serif">正在整理你的旅行需求…</span>
                </div>
              )}

              {error && (
                <Alert variant="destructive" className="rounded-xl bg-destructive/5 backdrop-blur-md">
                  <CircleAlert />
                  <AlertDescription className="break-words text-xs leading-relaxed">
                    {error.message}
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

          {/* 回到最新按钮：隐于右下角 */}
          {!atBottom && (
            <Button
              variant="outline"
              size="icon"
              aria-label="回到最新消息"
              className="absolute bottom-24 right-6 size-8 rounded-full bg-white/90 shadow-md backdrop-blur-md hover:bg-white sm:right-10"
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

          {/* 极致纯净：单行悬浮液态玻璃输入胶囊（无下划线分割，无键盘说教，纯粹单图标） */}
          {!!displayMessages.length && !editing && (
            <div className="shrink-0 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 sm:px-8 sm:pb-6">
              <form
                onSubmit={submit}
                className="pure-capsule mx-auto flex max-w-2xl items-center gap-2 rounded-full p-1.5 pl-4 sm:pl-5 transition-all duration-200 focus-within:shadow-[0_12px_40px_-6px_rgba(25,35,28,0.1)] focus-within:bg-white/95"
              >
                <Textarea
                  aria-label="旅行需求"
                  placeholder="写下关于这次旅行的任何想法…"
                  rows={1}
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
                  className="max-h-32 min-h-6 flex-1 resize-none border-0 bg-transparent py-1 text-sm leading-relaxed shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/45"
                />

                <div className="flex shrink-0 items-center">
                  {running ? (
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      onClick={() => void stop()}
                      className="size-9 rounded-full bg-black/[0.04] text-foreground hover:bg-black/[0.08]"
                    >
                      <span className="sr-only">停止</span>
                      <Square className="size-3 fill-current" />
                    </Button>
                  ) : (
                    <Button
                      type="submit"
                      size="icon"
                      disabled={!text.trim()}
                      className="size-9 rounded-full bg-primary text-white shadow-xs hover:bg-primary/95 transition-all duration-200 active:scale-95 disabled:opacity-30 disabled:pointer-events-none"
                    >
                      <span className="sr-only">发送</span>
                      <ArrowUp className="size-4 stroke-[2.2]" />
                    </Button>
                  )}
                </div>
              </form>
            </div>
          )}
        </div>

        {/* 宽屏右侧基础安排 */}
        <aside
          aria-label="旅行基础安排"
          className="hidden w-76 shrink-0 overflow-y-auto bg-white/20 px-5 py-6 backdrop-blur-md xl:block"
        >
          <TripPanel trip={detail.trip} />
        </aside>
      </div>
    </>
  );
}

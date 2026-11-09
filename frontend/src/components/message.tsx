import { memo, useLayoutEffect, useRef, type ReactNode } from "react";
import { isToolUIPart } from "ai";
import type { UIMessage } from "ai";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowRight,
  Check,
  CircleAlert,
  LoaderCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Detail, Trip } from "@/api";
import { TripCard } from "./trip-card";
import { readBrief } from "./travel-form";

const toolNames: Record<string, string> = {
  current_time: "核对北京时间",
  present_trip: "整理交通和住宿方案",
  confirm_trip: "检查并保存交通和住宿",
  load_capability: "准备旅行查询",
  read_file: "查阅旅行查询说明",
  call_flyai: "查询交通与酒店",
  web_search: "搜索旅行资讯",
};

function ToolActivityGroup({ children, count }: { children: ReactNode; count: number }) {
  const scroller = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const element = scroller.current;
    if (count > 1 && element) element.scrollTop = element.scrollHeight;
  }, [count]);

  return (
    <div
      ref={scroller}
      role="region"
      aria-label="行程查询记录"
      className={cn(
        "my-1.5 rounded-xl",
        count > 1
          ? "bg-black/[0.02] p-2.5 max-h-36 overflow-y-auto overscroll-contain space-y-1"
          : "space-y-1",
      )}
    >
      <div className="space-y-1">
        {children}
      </div>
    </div>
  );
}

export const Message = memo(function Message({ message, detail, busy, onConfirm }: { message: UIMessage; detail: Detail; busy: boolean; onConfirm: (id: string) => void }) {
  const user = message.role === "user";

  if (user) {
    return (
      <article className="flex justify-end">
        <div className="max-w-[92%] sm:max-w-[78%]">
          {message.parts.map((part, i) => {
            if (part.type !== "text") return null;
            const brief = readBrief(part.text);

            if (brief) {
              const route = [brief["出发城市"], brief["目的城市"]]
                .filter(Boolean)
                .join(" → ");
              const dates = [brief["出发日期"], brief["返回日期"]]
                .filter(Boolean)
                .join(" 至 ");
              const tags = [
                brief["同行人数"] ? `${brief["同行人数"]} 人同行` : "",
                brief["预算"] ? `预算 ${brief["预算"]}` : "",
                brief["成人"] ? `${brief["成人"]} 位成人` : "",
                brief["老人"] ? `${brief["老人"]} 位长辈` : "",
                brief["儿童"] ? `${brief["儿童"]} 位儿童` : "",
                brief["老人同行"] === "有" ? "有老人同行" : "",
                brief["小孩同行"] === "有" ? "有小孩同行" : "",
                brief["交通偏好"],
                brief["住宿偏好"],
                brief["预算金额"]
                  ? `¥${brief["预算金额"]} (${brief["预算口径"] || "总额"})`
                  : "",
                brief["兴趣偏好"],
              ].filter(Boolean);

              return (
                <div
                  key={i}
                  className="pure-capsule relative overflow-hidden p-5 text-foreground sm:p-6"
                >
                  {route && (
                    <div className="flex items-center gap-2.5">
                      <span className="font-serif text-xl font-medium tracking-tight text-foreground sm:text-2xl">
                        {brief["出发城市"] || "出发地"}
                      </span>
                      <ArrowRight className="size-4 shrink-0 text-muted-foreground/40" />
                      <span className="font-serif text-xl font-medium tracking-tight text-foreground sm:text-2xl">
                        {brief["目的城市"] || "目的地"}
                      </span>
                    </div>
                  )}

                  {dates && (
                    <p className="mt-1 text-xs text-muted-foreground font-mono">
                      {dates}
                    </p>
                  )}

                  {tags.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {tags.map((t) => (
                        <span
                          key={t}
                          className="rounded-full bg-black/[0.03] px-2.5 py-0.5 text-[11px] text-foreground/75"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}

                  {brief["补充想法"] && (
                    <p className="mt-2.5 font-serif text-xs italic text-muted-foreground">
                      “{brief["补充想法"]}”
                    </p>
                  )}

                  <span className="sr-only">{part.text}</span>
                </div>
              );
            }

            return (
              <div
                key={i}
                className="rounded-xl rounded-tr-xs bg-[#19382e]/90 text-white selection:bg-[#d9eee3] selection:text-[#19382e] px-4 py-2.5 text-sm leading-relaxed shadow-2xs break-words"
              >
                {part.text}
              </div>
            );
          })}
        </div>
      </article>
    );
  }

  // 将消息 parts 组织成文本与工具组，避免工具刷屏撑破页面
  type PartGroup =
    | { type: "proposal"; trip: Trip; id: string }
    | { type: "text"; text: string; key: number }
    | { type: "tools"; tools: Array<{ part: Parameters<typeof isToolUIPart>[0]; key: number }> };

  const groups: PartGroup[] = [];
  message.parts.forEach((part, i) => {
    if (part.type === "text") {
      groups.push({ type: "text", text: part.text, key: i });
    } else if (isToolUIPart(part)) {
      const name = part.type === "dynamic-tool" ? part.toolName : part.type.slice(5);
      if (name === "present_trip" && part.state === "output-available") {
        // 仅在输出工具成功后展示已校验的参数；框架返回值是结束标记。
        const input = part.input as Trip | { trip: Trip };
        // 单模型参数默认展开；兼容历史消息中按参数名包装的输入。
        const trip = "trip" in input ? input.trip : input;
        groups.push({ type: "proposal", trip, id: part.toolCallId });
        return;
      }
      const last = groups[groups.length - 1];
      if (last && last.type === "tools") {
        last.tools.push({ part, key: i });
      } else {
        groups.push({ type: "tools", tools: [{ part, key: i }] });
      }
    }
  });

  return (
    <article>
      <div className="min-w-0 flex-1 space-y-2">
        {groups.map((group, groupIdx) => {
          if (group.type === "proposal") {
            const status = detail.pending_id === group.id ? "pending" : detail.confirmed_id === group.id ? "confirmed" : "outdated";
            return <section key={group.id} aria-label="交通与住宿方案" className="pure-capsule p-4 sm:p-5"><TripCard trip={group.trip} status={status} disabled={busy} onConfirm={() => onConfirm(group.id)} /></section>;
          }
          if (group.type === "text") {
            return (
              <MessageMarkdown key={groupIdx} text={group.text} />
            );
          }

          if (group.type === "tools") {
            return (
              <ToolActivityGroup key={groupIdx} count={group.tools.length}>
                {group.tools.map(({ part, key }) => {
                  if (!isToolUIPart(part)) return null;
                  const name =
                    part.type === "dynamic-tool"
                      ? part.toolName
                      : part.type.slice(5);
                  const finished = part.state === "output-available";
                  const failed = part.state === "output-error";
                  return (
                    <div key={key}>
                      <div className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-left text-[11px] text-muted-foreground/75">
                        {failed ? (
                          <CircleAlert className="size-3 shrink-0 text-destructive" />
                        ) : finished ? (
                          <Check className="size-3 shrink-0 text-primary stroke-[2.5]" />
                        ) : (
                          <LoaderCircle className="size-3 shrink-0 animate-spin text-primary" />
                        )}
                        <span className="font-normal font-sans">
                          {toolNames[name] ||
                            (name.startsWith("amap")
                              ? "查询地点与路线"
                              : name === "run_command"
                                ? "查询交通与酒店"
                                : name)}
                        </span>
                        <span className="text-[10px] text-muted-foreground/50">
                          {failed ? "未完成" : finished ? "已完成" : "进行中"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </ToolActivityGroup>
            );
          }

          return null;
        })}
      </div>
    </article>
  );
});

const markdownComponents: Components = {
  a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
  table: (props) => (
    <div className="my-3 max-w-full overflow-x-auto rounded-xl bg-white/70 px-3 py-1 shadow-2xs">
      <table {...props} />
    </div>
  ),
};

const MessageMarkdown = memo(function MessageMarkdown({ text }: { text: string }) {
  return (
    <div
      className={cn(
        "prose prose-sm prose-stone max-w-none break-words text-sm leading-7 text-foreground",
        "prose-headings:font-serif prose-headings:font-medium prose-headings:tracking-tight prose-headings:text-foreground",
        "prose-h2:text-lg prose-h2:mt-4 prose-h2:mb-1.5",
        "prose-h3:text-sm prose-h3:mt-3 prose-h3:mb-1",
        "prose-p:my-2 first:prose-p:mt-0 last:prose-p:mb-0",
        "prose-a:font-medium prose-a:text-primary prose-a:underline-offset-4 hover:prose-a:underline",
        "prose-blockquote:border-l-primary/40 prose-blockquote:py-1 prose-blockquote:px-3.5 prose-blockquote:font-serif prose-blockquote:italic",
        "prose-li:my-0.5",
        "prose-pre:max-w-full prose-pre:overflow-x-auto prose-pre:rounded-xl prose-pre:bg-white/80",
        "prose-img:max-h-80 prose-img:rounded-xl prose-img:object-cover",
        "prose-table:text-xs",
      )}
    >
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {text}
      </Markdown>
    </div>
  );
});

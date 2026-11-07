import { isToolUIPart } from "ai";
import type { UIMessage } from "ai";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowRight,
  Check,
  ChevronDown,
  CircleAlert,
  Compass,
  LoaderCircle,
  Sparkles,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { readBrief } from "./travel-form";

const toolNames: Record<string, string> = {
  current_time: "核对北京时间",
  confirm_trip: "检查并保存交通和住宿",
  load_capability: "准备旅行查询",
  read_file: "查阅旅行查询说明",
  call_flyai: "查询交通与酒店",
  web_search: "搜索旅行资讯",
};

export function Message({ message }: { message: UIMessage }) {
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
                brief["成人"] ? `${brief["成人"]} 位成人` : "",
                brief["老人"] ? `${brief["老人"]} 位长辈` : "",
                brief["儿童"] ? `${brief["儿童"]} 位儿童` : "",
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
                  <div className="flex items-center justify-between text-xs text-muted-foreground/70">
                    <span className="flex items-center gap-1.5 font-serif font-medium text-primary">
                      <Sparkles className="size-3.5 text-primary" />
                      旅行心愿
                    </span>
                    <span className="font-mono text-[9px] tracking-widest uppercase">
                      TRIP INTENT
                    </span>
                  </div>

                  {route && (
                    <div className="mt-3 flex items-center gap-2.5">
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
                className="rounded-xl rounded-tr-xs bg-[#19382e]/90 text-white backdrop-blur-md px-4 py-2.5 text-sm leading-relaxed shadow-2xs break-words"
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
    | { type: "text"; text: string; key: number }
    | { type: "tools"; tools: Array<{ part: Parameters<typeof isToolUIPart>[0]; key: number }> };

  const groups: PartGroup[] = [];
  message.parts.forEach((part, i) => {
    if (part.type === "text") {
      groups.push({ type: "text", text: part.text, key: i });
    } else if (isToolUIPart(part)) {
      const last = groups[groups.length - 1];
      if (last && last.type === "tools") {
        last.tools.push({ part, key: i });
      } else {
        groups.push({ type: "tools", tools: [{ part, key: i }] });
      }
    }
  });

  return (
    <article className="flex gap-3.5 sm:gap-4">
      {/* 助手印章 */}
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary shadow-2xs">
        <Compass className="size-3.5" strokeWidth={1.8} />
      </div>

      <div className="min-w-0 flex-1 space-y-2">
        {groups.map((group, groupIdx) => {
          if (group.type === "text") {
            return (
              <div
                key={groupIdx}
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
                  components={{
                    a: (props) => (
                      <a {...props} target="_blank" rel="noreferrer" />
                    ),
                    table: (props) => (
                      <div className="my-3 max-w-full overflow-x-auto rounded-xl bg-white/70 px-3 py-1 shadow-2xs backdrop-blur-md">
                        <table {...props} />
                      </div>
                    ),
                  }}
                >
                  {group.text}
                </Markdown>
              </div>
            );
          }

          if (group.type === "tools") {
            const hasMultiple = group.tools.length > 1;

            return (
              <div
                key={groupIdx}
                className={cn(
                  "my-1.5 rounded-xl transition-all",
                  hasMultiple
                    ? "bg-black/[0.02] p-2.5 max-h-36 overflow-y-auto overscroll-contain space-y-1"
                    : "space-y-1",
                )}
              >
                {hasMultiple && (
                  <div className="mb-1 flex items-center justify-between px-1 text-[10px] text-muted-foreground/60 font-mono uppercase">
                    <span>行程查询记录</span>
                    <span>{group.tools.length} 项</span>
                  </div>
                )}

                {group.tools.map(({ part, key }) => {
                  if (!isToolUIPart(part)) return null;
                  const name =
                    part.type === "dynamic-tool"
                      ? part.toolName
                      : part.type.slice(5);
                  const finished = part.state === "output-available";
                  const failed = part.state === "output-error";
                  const payload =
                    "output" in part
                      ? part.output
                      : "errorText" in part
                        ? part.errorText
                        : part.input;

                  return (
                    <Collapsible key={key} className="my-0.5">
                      <CollapsibleTrigger className="group inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-left text-[11px] text-muted-foreground/75 hover:bg-black/[0.04] hover:text-foreground transition-colors">
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
                        <ChevronDown className="size-2.5 text-muted-foreground/40 transition-transform duration-200 group-data-[state=open]:rotate-180" />
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <div className="mt-1 max-w-xl rounded-xl bg-white/80 p-3 shadow-2xs backdrop-blur-md">
                          <pre className="max-h-40 overflow-auto text-[11px] leading-relaxed text-muted-foreground font-mono">
                            {JSON.stringify(payload, null, 2)}
                          </pre>
                        </div>
                      </CollapsibleContent>
                    </Collapsible>
                  );
                })}
              </div>
            );
          }

          return null;
        })}
      </div>
    </article>
  );
}

import { isToolUIPart } from "ai";
import type { UIMessage } from "ai";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Check,
  ChevronDown,
  CircleAlert,
  Compass,
  LoaderCircle,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

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
        <div className="max-w-[85%] space-y-2 sm:max-w-[75%]">
          {message.parts.map((part, i) =>
            part.type === "text" ? (
              <div
                key={i}
                className="rounded-2xl rounded-br-sm bg-secondary px-4 py-2.5 text-sm leading-6 text-foreground break-words"
              >
                {part.text}
              </div>
            ) : null,
          )}
        </div>
      </article>
    );
  }

  return (
    <article className="flex gap-3">
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Compass className="size-3.5" />
      </div>
      <div className="min-w-0 flex-1 space-y-2.5">
        {message.parts.map((part, i) => {
          if (part.type === "text")
            return (
              <div
                key={i}
                className={cn(
                  "prose prose-sm prose-stone max-w-none break-words text-sm leading-7 text-foreground prose-headings:font-semibold prose-headings:tracking-tight prose-p:my-2 first:prose-p:mt-0 last:prose-p:mb-0 prose-a:text-primary prose-a:decoration-primary/30 prose-a:underline-offset-4 prose-pre:max-w-full prose-pre:overflow-x-auto prose-img:max-h-80 prose-img:rounded-xl prose-img:object-cover prose-table:text-xs",
                )}
              >
                <Markdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: (props) => (
                      <a {...props} target="_blank" rel="noreferrer" />
                    ),
                    table: (props) => (
                      <div className="my-3 max-w-full overflow-x-auto rounded-xl border bg-card px-3">
                        <table {...props} />
                      </div>
                    ),
                  }}
                >
                  {part.text}
                </Markdown>
              </div>
            );
          if (isToolUIPart(part)) {
            const name =
              part.type === "dynamic-tool" ? part.toolName : part.type.slice(5);
            const finished = part.state === "output-available";
            const failed = part.state === "output-error";
            return (
              <Collapsible key={i} className="space-y-1.5">
                <CollapsibleTrigger className="group inline-flex max-w-full items-center gap-2 rounded-full border border-border/80 bg-card px-3 py-1.5 text-left text-xs shadow-2xs transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  {failed ? (
                    <CircleAlert className="size-3.5 shrink-0 text-destructive" />
                  ) : finished ? (
                    <Check className="size-3.5 shrink-0 text-primary" />
                  ) : (
                    <LoaderCircle className="size-3.5 shrink-0 animate-spin text-primary" />
                  )}
                  <span className="truncate font-medium text-foreground/90">
                    {toolNames[name] ||
                      (name.startsWith("amap") ? "查询地点与路线" : name)}
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {failed ? "未完成" : finished ? "已返回" : "进行中"}
                  </span>
                  <ChevronDown className="size-3 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <pre className="max-h-60 overflow-auto rounded-xl border border-border/80 bg-card/90 p-3 text-[11px] leading-5 text-muted-foreground shadow-2xs">
                    {JSON.stringify(
                      "output" in part
                        ? part.output
                        : "errorText" in part
                          ? part.errorText
                          : part.input,
                      null,
                      2,
                    )}
                  </pre>
                </CollapsibleContent>
              </Collapsible>
            );
          }
          return null;
        })}
      </div>
    </article>
  );
}

import { useOutletContext } from "react-router";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Compass,
  LoaderCircle,
  TrainFront,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { TravelActions } from "./layout";

const suggestions = [
  {
    icon: TrainFront,
    title: "周末，去附近走走",
    description: "一趟高铁，换个城市过周末",
    prompt: "想找个周末坐高铁去附近城市玩两三天，帮我一起选个目的地。",
  },
  {
    icon: Compass,
    title: "给自己放个小长假",
    description: "选好机票与酒店，轻松出发",
    prompt: "想安排一次四五天的国内旅行，机票和酒店都还没订，帮我一起规划。",
  },
  {
    icon: CalendarDays,
    title: "已有预订，接着安排",
    description: "从已经确定的计划继续聊",
    prompt: "我已经有部分车票或酒店预订，想在这些安排的基础上继续规划旅行。",
  },
];

export function Welcome() {
  const { create, creating } = useOutletContext<TravelActions>();
  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="m-auto w-full max-w-3xl px-6 py-10 sm:px-10">
        <div className="flex flex-col items-start">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
            <Compass className="size-3.5 text-primary" />
            国内城市旅行规划
          </span>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight text-foreground sm:text-4xl">
            下一站，想去哪里走走？
          </h1>
          <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
            聊聊你的出发地、时间和旅行想法，一起选定往返交通与住宿，再从容安排每一天的行程。
          </p>
          <Button
            size="lg"
            onClick={() => void create()}
            disabled={creating}
            className="mt-6 h-10 gap-2 rounded-full px-6 text-xs font-medium shadow-xs"
          >
            {creating ? <LoaderCircle className="size-4 animate-spin" /> : null}
            开始规划
            <ArrowRight className="size-3.5" />
          </Button>
        </div>

        <div className="mt-10 grid gap-3 sm:grid-cols-3">
          {suggestions.map(({ icon: Icon, title, description, prompt }) => (
            <button
              key={title}
              onClick={() => void create(prompt)}
              disabled={creating}
              className="group flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-4 text-left shadow-2xs transition-all hover:border-primary/35 hover:shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              <div>
                <div className="mb-3.5 flex items-center justify-between">
                  <span className="flex size-8 items-center justify-center rounded-lg bg-secondary text-primary">
                    <Icon className="size-4" />
                  </span>
                  <ArrowUpRight className="size-3.5 text-muted-foreground/60 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
                </div>
                <span className="block text-sm font-medium text-foreground">
                  {title}
                </span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  {description}
                </span>
              </div>
            </button>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border/60 pt-5 text-xs text-muted-foreground">
          <span>1. 聊聊旅行想法</span>
          <ArrowRight className="size-3 opacity-40" />
          <span>2. 选定并确认交通与住宿</span>
          <ArrowRight className="size-3 opacity-40" />
          <span>3. 生成每日行程安排</span>
        </div>
      </div>
    </section>
  );
}

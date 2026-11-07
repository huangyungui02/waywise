import { useState } from "react";
import { ArrowRight, ArrowUpRight, Compass, LoaderCircle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const fields = [
  ["出发城市", "text", "出发地"],
  ["目的城市", "text", "目的地"],
  ["出发日期", "date", ""],
  ["返回日期", "date", ""],
  ["成人", "number", "1"],
  ["老人", "number", "0"],
  ["儿童", "number", "0"],
  ["儿童年龄", "text", "儿童年龄"],
  ["预算金额", "number", "预算金额"],
] as const;

const interests = [
  "当地美食",
  "自然山水",
  "历史人文",
  "城市漫步",
  "慢节奏",
  "特色民宿",
  "亲子体验",
  "摄影出片",
];

const marker = "这次旅行的想法：";

export function readBrief(text: string): Record<string, string> | undefined {
  if (!text.startsWith(marker)) return;
  return Object.fromEntries(
    text
      .slice(marker.length)
      .trim()
      .split("\n")
      .map((line) => {
        const index = line.indexOf("：");
        return index < 0
          ? ["", ""]
          : [line.slice(0, index), line.slice(index + 1)];
      })
      .filter(([key]) => key),
  );
}

export function TravelForm({
  initial = {},
  busy = false,
  onSubmit,
  onCancel,
}: {
  initial?: Record<string, string>;
  busy?: boolean;
  onSubmit: (text: string) => void;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>(initial);
  const [note, setNote] = useState(initial["补充想法"] || "");

  const update = (key: string, value: string) =>
    setValues((v) => ({ ...v, [key]: value }));

  const selected = (values["兴趣偏好"] || "").split("、").filter(Boolean);
  const hasInput = note.trim() || Object.values(values).some((v) => v.trim());

  return (
    <form
      className="pure-capsule relative space-y-5 p-6 sm:p-8"
      onSubmit={(e) => {
        e.preventDefault();
        if (!hasInput || busy) return;
        if (!Object.values(values).some((v) => v.trim())) {
          onSubmit(note.trim());
          return;
        }
        const data = { ...values, 补充想法: note.replace(/\n/g, " ") };
        onSubmit(
          marker +
            "\n" +
            Object.entries(data)
              .filter(([, v]) => v.trim())
              .map(([k, v]) => `${k}：${v}`)
              .join("\n"),
        );
      }}
    >
      {/* 核心自然语言随笔 */}
      <div>
        <label
          htmlFor="travel-main-note"
          className="mb-2 flex items-center gap-1.5 font-serif text-sm font-medium tracking-wide text-foreground"
        >
          <Sparkles className="size-3.5 text-primary" />
          <span>旅行想法与期待</span>
        </label>
        <Textarea
          id="travel-main-note"
          aria-label="旅行需求"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="例如：想在四月去杭州住西湖边、带父母坐高铁慢游三天……或只写一句话从容开始。"
          className="min-h-20 w-full resize-none rounded-xl bg-black/[0.025] p-3.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground/40 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary/10 transition-all border-0 shadow-none"
        />
      </div>

      {/* 起讫与行程细节：轻透无框流动 */}
      <div className="space-y-3.5 pt-1">
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              出发城市
            </span>
            <input
              type="text"
              placeholder="出发城市"
              value={values["出发城市"] || ""}
              onChange={(e) => update("出发城市", e.target.value)}
              className="pure-field"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              目的城市
            </span>
            <input
              type="text"
              placeholder="想去哪里？"
              value={values["目的城市"] || ""}
              onChange={(e) => update("目的城市", e.target.value)}
              className="pure-field"
            />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <label className="col-span-2 flex flex-col gap-1 sm:col-span-2">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              出发日期
            </span>
            <input
              type="date"
              value={values["出发日期"] || ""}
              onChange={(e) => update("出发日期", e.target.value)}
              className="pure-field font-mono text-xs"
            />
          </label>
          <label className="col-span-2 flex flex-col gap-1 sm:col-span-2">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              返回日期
            </span>
            <input
              type="date"
              min={values["出发日期"] || undefined}
              value={values["返回日期"] || ""}
              onChange={(e) => update("返回日期", e.target.value)}
              className="pure-field font-mono text-xs"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              成人
            </span>
            <input
              type="number"
              min={0}
              max={99}
              placeholder="人数"
              value={values["成人"] || ""}
              onChange={(e) => update("成人", e.target.value)}
              className="pure-field"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              老人
            </span>
            <input
              type="number"
              min={0}
              max={99}
              placeholder="长辈"
              value={values["老人"] || ""}
              onChange={(e) => update("老人", e.target.value)}
              className="pure-field"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              儿童
            </span>
            <input
              type="number"
              min={0}
              max={99}
              placeholder="儿童"
              value={values["儿童"] || ""}
              onChange={(e) => update("儿童", e.target.value)}
              className="pure-field"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              儿童年龄
            </span>
            <input
              type="text"
              placeholder="如：5岁"
              value={values["儿童年龄"] || ""}
              onChange={(e) => update("儿童年龄", e.target.value)}
              className="pure-field"
            />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              预算金额
            </span>
            <input
              type="number"
              min={1}
              placeholder="¥ 预算金额"
              value={values["预算金额"] || ""}
              onChange={(e) => update("预算金额", e.target.value)}
              className="pure-field"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              预算口径
            </span>
            <select
              className="pure-select"
              value={values["预算口径"] || ""}
              onChange={(e) => update("预算口径", e.target.value)}
            >
              <option value="">暂未确定</option>
              <option value="全程总预算">全程总预算</option>
              <option value="每人全程预算">每人全程预算</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              交通偏好
            </span>
            <select
              className="pure-select"
              value={values["交通偏好"] || ""}
              onChange={(e) => update("交通偏好", e.target.value)}
            >
              <option value="">暂未确定</option>
              <option value="都可以">都可以</option>
              <option value="高铁 / 火车">高铁 / 火车</option>
              <option value="飞机">飞机</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
              住宿偏好
            </span>
            <select
              className="pure-select"
              value={values["住宿偏好"] || ""}
              onChange={(e) => update("住宿偏好", e.target.value)}
            >
              <option value="">暂未确定</option>
              <option value="舒适方便">舒适方便</option>
              <option value="经济实惠">经济实惠</option>
              <option value="品质酒店">品质酒店</option>
              <option value="特色住宿">特色住宿</option>
            </select>
          </label>
        </div>

        {/* 兴趣标签 */}
        <fieldset className="pt-1">
          <legend className="mb-2 text-[11px] font-medium text-muted-foreground/80 font-mono">
            兴趣偏好
          </legend>
          <div className="flex flex-wrap gap-2">
            {interests.map((item) => {
              const active = selected.includes(item);
              return (
                <button
                  key={item}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    update(
                      "兴趣偏好",
                      (active
                        ? selected.filter((s) => s !== item)
                        : [...selected, item]
                      ).join("、"),
                    )
                  }
                  className={`pure-pill ${
                    active ? "pure-pill-active" : ""
                  }`}
                >
                  {item}
                </button>
              );
            })}
          </div>
        </fieldset>

        {/* 已有预订 */}
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-medium text-muted-foreground/80 font-mono">
            已有预订
          </span>
          <input
            className="pure-field"
            placeholder="已订车票、航班或酒店（选填）"
            value={values["已有预订"] || ""}
            onChange={(e) => update("已有预订", e.target.value)}
          />
        </label>
      </div>

      {/* 底部极简操作 */}
      <div className="flex items-center justify-end gap-2 pt-2">
        {onCancel && (
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            className="rounded-full px-4 text-xs text-muted-foreground hover:text-foreground"
          >
            取消
          </Button>
        )}
        <Button
          disabled={!hasInput || busy}
          className="gap-2 rounded-full bg-primary px-6 text-xs text-white shadow-xs hover:bg-primary/95 active:scale-95 transition-all"
          type="submit"
        >
          {busy ? <LoaderCircle className="size-3.5 animate-spin" /> : null}
          {onCancel ? "发送修改" : "开始规划"}
          <ArrowUpRight className="size-3.5" />
        </Button>
      </div>
    </form>
  );
}

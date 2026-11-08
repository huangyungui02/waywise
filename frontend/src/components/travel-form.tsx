import { useState } from "react";
import { format, parseISO } from "date-fns";
import { zhCN } from "react-day-picker/locale";
import { ArrowRight, CalendarDays, Users, Wallet } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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

export function travelPrompt(values: Record<string, string>, text: string): string {
  const entries = Object.entries(values).filter(([, value]) => value.trim());
  if (!entries.length) return text.trim();
  if (text.trim()) entries.push(["补充想法", text.trim().replace(/\n/g, " ")]);
  return marker + "\n" + entries.map(([key, value]) => `${key}：${value.trim()}`).join("\n");
}

function DateField({ label, value, earliest, onChange }: {
  label: string;
  value?: string;
  earliest?: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = value ? parseISO(value) : undefined;
  return (
    <div className="min-w-0 space-y-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button type="button" aria-label={label} className={cn("pure-field flex w-full items-center justify-between gap-2 text-left text-sm focus-visible:ring-2 focus-visible:ring-primary/30", !value && "text-muted-foreground/70")}>
            <span>{selected ? format(selected, "M月d日") : "选择日期"}</span>
            <CalendarDays className="size-4 shrink-0 text-primary/50" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-auto rounded-2xl p-2" aria-label={label}>
          <Calendar
            mode="single"
            locale={zhCN}
            captionLayout="dropdown"
            startMonth={new Date(2020, 0)}
            endMonth={new Date(new Date().getFullYear() + 5, 11)}
            defaultMonth={selected || (earliest ? parseISO(earliest) : undefined)}
            selected={selected}
            disabled={earliest ? { before: parseISO(earliest) } : undefined}
            labels={{
              labelMonthDropdown: () => "月份",
              labelYearDropdown: () => "年份",
              labelDayButton: (date) => format(date, "yyyy-MM-dd"),
              labelNext: () => "下个月",
              labelPrevious: () => "上个月",
            }}
            className="[--cell-size:--spacing(9)]"
            onSelect={(date) => {
              onChange(date ? format(date, "yyyy-MM-dd") : "");
              setOpen(false);
            }}
          />
          <Button variant="ghost" size="sm" className="w-full text-xs text-muted-foreground" onClick={() => { onChange(""); setOpen(false); }}>清除日期</Button>
        </PopoverContent>
      </Popover>
    </div>
  );
}

export function TravelForm({ values, onChange }: {
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
}) {
  const update = (key: string, value: string) => onChange({ ...values, [key]: value });
  return (
    <section aria-label="旅行基本信息" className="pure-capsule overflow-hidden p-5 sm:p-8">
      <div className="mb-7">
        <h2 className="font-serif text-2xl font-medium tracking-tight sm:text-3xl">这次，想去哪里？</h2>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">填下已经确定的安排，剩下的我们一起慢慢计划。</p>
      </div>

      <div className="space-y-6">
        <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-3 sm:gap-4">
          {([['出发城市', '出发地', '从哪里出发'], ['目的城市', '目的地', '想去哪里']] as const).map(([key, label, placeholder], index) => (
            <div key={key} className="contents">
              {index === 1 && <ArrowRight aria-hidden="true" className="mb-3 size-4 text-primary/30" />}
              <label className="flex min-w-0 flex-col gap-2">
                <span className="text-xs text-muted-foreground">{label}</span>
                <input value={values[key] || ""} onChange={(event) => update(key, event.target.value)} placeholder={placeholder} className="pure-field min-w-0 w-full text-sm" />
              </label>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <DateField label="出发日期" value={values['出发日期']} onChange={(value) => onChange({ ...values, 出发日期: value, 返回日期: value && values['返回日期'] && values['返回日期'] < value ? "" : values['返回日期'] || "" })} />
          <DateField label="返回日期" value={values['返回日期']} earliest={values['出发日期']} onChange={(value) => update('返回日期', value)} />
        </div>

        <div className="grid gap-4 border-t border-black/[0.05] pt-5 sm:grid-cols-2">
          <div className="rounded-2xl bg-primary/[0.025] p-4">
            <label className="flex flex-col gap-3">
              <span className="flex items-center gap-2 text-xs font-medium text-primary"><Users className="size-3.5" /> 同行人数</span>
              <span className="flex items-center gap-2">
                <input aria-label="同行人数" type="number" min="1" step="1" placeholder="几个人" value={values['同行人数'] || ""} onChange={(event) => update('同行人数', event.target.value)} className="pure-field min-w-0 w-full text-sm" />
                <span className="shrink-0 text-xs text-muted-foreground">人</span>
              </span>
            </label>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
              {(['老人', '小孩'] as const).map((label) => (
                <label key={label} className="flex cursor-pointer items-center gap-2 py-1 text-xs text-muted-foreground">
                  <Checkbox checked={values[`${label}同行`] === '有'} onCheckedChange={(checked) => update(`${label}同行`, checked === true ? '有' : '')} className="border-primary/25" />
                  有{label}
                </label>
              ))}
            </div>
          </div>

          <div className="rounded-2xl bg-primary/[0.025] p-4">
            <label className="flex flex-col gap-3">
              <span className="flex items-center gap-2 text-xs font-medium text-primary"><Wallet className="size-3.5" /> 旅行预算</span>
              <span className="flex items-center gap-2">
                <input aria-label="预算" type="number" min="0" placeholder="预计花费" value={values['预算金额'] || ""} onChange={(event) => onChange({ ...values, 预算金额: event.target.value, 预算口径: event.target.value ? values['预算口径'] || '总共' : '' })} className="pure-field min-w-0 w-full text-sm" />
                <span className="shrink-0 text-xs text-muted-foreground">元</span>
              </span>
            </label>
            <div role="radiogroup" aria-label="预算口径" className="mt-3 inline-flex rounded-full bg-black/[0.035] p-0.5">
              {(['人均', '总共'] as const).map((scope) => (
                <label key={scope} className="relative cursor-pointer">
                  <input type="radio" name="budget-scope" value={scope} checked={(values['预算口径'] || '总共') === scope} onChange={() => update('预算口径', scope)} className="peer absolute inset-0 z-10 size-full cursor-pointer opacity-0" />
                  <span className="block rounded-full px-4 py-1.5 text-xs text-muted-foreground transition-colors peer-checked:bg-white peer-checked:text-primary peer-checked:shadow-xs peer-focus-visible:ring-2 peer-focus-visible:ring-primary/30">{scope}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

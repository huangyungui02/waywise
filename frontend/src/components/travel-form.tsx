const fields = [
  { key: "出发城市", label: "出发地", type: "text", placeholder: "从哪里出发" },
  { key: "目的城市", label: "目的地", type: "text", placeholder: "想去哪里" },
  { key: "出发日期", label: "出发日期", type: "date" },
  { key: "返回日期", label: "返回日期", type: "date" },
  { key: "同行人数", label: "同行人数", type: "number", placeholder: "几个人出行" },
  { key: "预算", label: "预算", type: "text", placeholder: "如：每人 2000 元" },
] as const;

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

export function TravelForm({ values, onChange }: {
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
}) {
  return (
    <section aria-label="旅行基本信息" className="pure-capsule space-y-5 p-5 sm:p-7">
      <div>
        <h2 className="font-serif text-lg font-medium text-foreground">这次去哪里？</h2>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          先填已确定的信息，其他可以边聊边定。
        </p>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-4">
        {fields.map((field) => (
          <label key={field.key} className="flex min-w-0 flex-col gap-1.5">
            <span className="text-xs text-muted-foreground">{field.label}</span>
            <input
              type={field.type}
              placeholder={"placeholder" in field ? field.placeholder : undefined}
              min={field.type === "number" ? 1 : field.key === "返回日期" ? values["出发日期"] || undefined : undefined}
              value={values[field.key] || ""}
              onChange={(event) => onChange({ ...values, [field.key]: event.target.value })}
              className="pure-field min-w-0 w-full"
            />
          </label>
        ))}
      </div>
    </section>
  );
}

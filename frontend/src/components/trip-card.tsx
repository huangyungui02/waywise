import {
  ArrowRight,
  ArrowUpRight,
  Calendar,
  Bus,
  Check,
  Hotel,
  MapPin,
  Plane,
  Route,
  TrainFront,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Trip } from "@/api";

export function TripCard({ trip, status, disabled, onConfirm }: { trip: Trip; status: "pending" | "confirmed" | "outdated"; disabled?: boolean; onConfirm?: () => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-serif text-sm font-medium"><Route className="size-3.5 text-primary" />交通与住宿</h3>
        <Badge variant="secondary">{status === "pending" ? "待确认" : status === "confirmed" ? "已确认方案" : "已更新"}</Badge>
      </div>
      <p className="font-serif text-xs leading-relaxed text-muted-foreground/70">
        {trip.origin} → {trip.destination}。如需调整，在聊天中告诉我即可重新确认。
      </p>

      {/* 交通卡片 */}
      {(
        [
          ["去程", trip.outbound],
          ["回程", trip.inbound],
        ] as const
      ).map(([label, leg]) => {
        const { icon: Icon, title } = {
          train: { icon: TrainFront, title: "高铁 / 火车" },
          flight: { icon: Plane, title: "机票航班" },
          bus: { icon: Bus, title: "大巴 / 景区直通车" },
        }[leg.type];
        return (
          <div
            key={label}
            className="pure-capsule relative overflow-hidden p-4 transition-all duration-200"
          >
            {/* 票根头部 */}
            <div className="flex items-center justify-between pb-2 text-xs">
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground/80">
                <Icon className="size-3.5 text-primary" />
                <span className="font-serif font-medium text-foreground">
                  {label}
                </span>
                <span>·</span>
                <span>{title}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold tracking-wider text-primary">
                  {leg.number ?? leg.name}
                </span>
                {leg.purchased && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                    <Check className="size-2.5 stroke-[2.5]" />
                    已购买
                  </span>
                )}
              </div>
            </div>

            {/* 站台与航迹 */}
            <div className="mt-2 space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-serif text-sm font-semibold text-foreground">
                    {leg.departure_point}
                  </div>
                  <div className="text-[11px] text-muted-foreground/70 font-mono">
                    {leg.departure_time.replace("T", " ")}
                  </div>
                </div>

                <div className="flex shrink-0 flex-col items-center px-1">
                  <span className="text-[9px] tracking-wider text-muted-foreground/45 uppercase font-mono">
                    {leg.type.toUpperCase()}
                  </span>
                  <div className="flex items-center gap-1 text-primary/45">
                    <span className="size-1 rounded-full bg-primary/45" />
                    <span className="h-px w-4 bg-primary/30" />
                    <ArrowRight className="size-2.5" />
                  </div>
                </div>

                <div className="min-w-0 flex-1 text-right">
                  <div className="truncate font-serif text-sm font-semibold text-foreground">
                    {leg.arrival_point}
                  </div>
                  <div className="text-[11px] text-muted-foreground/70 font-mono">
                    {leg.arrival_time.replace("T", " ")}
                  </div>
                </div>
              </div>

              {!leg.purchased && leg.purchase_url && (
                <Button
                  asChild
                  variant="ghost"
                  size="sm"
                  className="mt-1 h-7.5 w-full rounded-full bg-black/[0.025] text-xs font-medium text-foreground hover:bg-black/[0.05]"
                >
                  <a
                    href={leg.purchase_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center gap-1.5"
                  >
                    <span>前往购买</span>
                    <ArrowUpRight className="size-3 text-muted-foreground" />
                  </a>
                </Button>
              )}
            </div>
          </div>
        );
      })}

      {/* 住宿卡片 */}
      {trip.stays.map((stay, i) => (
        <div
          key={i}
          className="pure-capsule relative overflow-hidden p-4 transition-all duration-200"
        >
          <div className="flex items-center justify-between pb-2 text-xs">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground/80">
              <Hotel className="size-3.5 text-primary" />
              <span className="font-serif font-medium text-foreground">
                下榻住处
              </span>
            </div>
            {stay.booked && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                <Check className="size-2.5 stroke-[2.5]" />
                已预订
              </span>
            )}
          </div>

          <div className="mt-2 space-y-2">
            <div>
              <h4 className="font-serif text-sm font-semibold leading-snug text-foreground">
                {stay.hotel}
              </h4>
              <p className="mt-0.5 flex items-start gap-1 text-xs leading-relaxed text-muted-foreground/70">
                <MapPin className="mt-0.5 size-3 shrink-0 text-muted-foreground/50" />
                <span className="break-words">{stay.address}</span>
              </p>
            </div>

            <div className="flex items-center gap-1.5 rounded-xl bg-black/[0.02] px-2.5 py-1 text-xs text-foreground/85">
              <Calendar className="size-3 text-primary" />
              <span className="font-serif text-xs">
                {stay.check_in} 入住 · {stay.check_out} 退房
              </span>
            </div>

            {!stay.booked && stay.purchase_url && (
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="mt-1 h-7.5 w-full rounded-full bg-black/[0.025] text-xs font-medium text-foreground hover:bg-black/[0.05]"
              >
                <a
                  href={stay.purchase_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-1.5"
                >
                  <span>前往预订</span>
                  <ArrowUpRight className="size-3 text-muted-foreground" />
                </a>
              </Button>
            )}
          </div>
        </div>
      ))}

      {!trip.stays.length && (
        <p className="text-center font-serif text-xs text-muted-foreground/70">
          同日往返，无酒店住宿。
        </p>
      )}
      {status === "pending" && (
        <div className="space-y-2">
          <Button className="w-full rounded-full" disabled={disabled} onClick={onConfirm}>确认方案</Button>
          <p className="text-xs text-muted-foreground">想调整交通或酒店？直接在下方告诉我。</p>
        </div>
      )}
      <p className="text-xs text-muted-foreground">确认方案不代表已经购买，请前往预订页面自行核对并支付。</p>
    </div>
  );
}

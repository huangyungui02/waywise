import {
  ArrowRight,
  ArrowUpRight,
  Calendar,
  Check,
  Compass,
  Hotel,
  MapPin,
  Plane,
  Route,
  TrainFront,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Trip } from "@/api";

export function TripPanel({ trip }: { trip: Trip | null }) {
  return (
    <div className="space-y-4">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-serif text-sm font-medium tracking-wide text-foreground">
          <Route className="size-3.5 text-primary" />
          <span>基础安排</span>
        </h3>
        <Badge
          variant={trip ? "secondary" : "outline"}
          className={`rounded-full px-2.5 py-0.5 text-[10px] font-normal tracking-wide ${
            trip
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground/60"
          }`}
        >
          {trip ? "已确认方案" : "待确认"}
        </Badge>
      </div>

      {/* 空状态 */}
      {!trip ? (
        <div className="pure-capsule relative overflow-hidden py-10 px-6 text-center">
          <div className="mx-auto mb-3 flex size-8 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Compass className="size-4" strokeWidth={1.75} />
          </div>
          <p className="font-serif text-sm font-medium text-foreground">
            好行程，从容安排
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground/60">
            选好往返交通和住宿后，
            <br />
            确认的安排会保存在这里。
          </p>
        </div>
      ) : (
        <>
          <p className="font-serif text-xs leading-relaxed text-muted-foreground/70">
            最近确认的安排。如需调整，在聊天中告诉我即可重新确认。
          </p>

          {/* 交通卡片 */}
          {(
            [
              ["去程", trip.outbound],
              ["回程", trip.inbound],
            ] as const
          ).map(([label, leg]) => {
            const Icon = leg.type === "train" ? TrainFront : Plane;
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
                    <span>{leg.type === "train" ? "高铁 / 火车" : "机票航班"}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold tracking-wider text-primary">
                      {leg.number}
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
                        {leg.departure_station}
                      </div>
                      <div className="text-[11px] text-muted-foreground/70 font-mono">
                        {leg.departure_time.replace("T", " ")}
                      </div>
                    </div>

                    <div className="flex shrink-0 flex-col items-center px-1">
                      <span className="text-[9px] tracking-wider text-muted-foreground/45 uppercase font-mono">
                        {leg.type === "train" ? "TRAIN" : "FLIGHT"}
                      </span>
                      <div className="flex items-center gap-1 text-primary/45">
                        <span className="size-1 rounded-full bg-primary/45" />
                        <span className="h-px w-4 bg-primary/30" />
                        <ArrowRight className="size-2.5" />
                      </div>
                    </div>

                    <div className="min-w-0 flex-1 text-right">
                      <div className="truncate font-serif text-sm font-semibold text-foreground">
                        {leg.arrival_station}
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
        </>
      )}
    </div>
  );
}

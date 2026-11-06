import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Hotel,
  MapPin,
  Plane,
  Route,
  ShieldCheck,
  TrainFront,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Trip } from "@/api";

export function TripPanel({ trip }: { trip: Trip | null }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-xs font-semibold text-foreground">
          <Route className="size-3.5 text-primary" />
          基础安排
        </h3>
        <Badge
          variant={trip ? "secondary" : "outline"}
          className="text-[10px] font-normal"
        >
          {trip ? "已确认方案" : "待确认"}
        </Badge>
      </div>
      {!trip ? (
        <>
          <div className="rounded-2xl border border-dashed border-border bg-card/60 px-4 py-7 text-center">
            <MapPin
              className="mx-auto mb-3 size-6 text-primary/50"
              strokeWidth={1.5}
            />
            <p className="text-xs font-medium text-foreground">
              好行程，从容安排
            </p>
            <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
              选好往返交通和住宿后，
              <br />
              确认的安排会保存在这里。
            </p>
          </div>
          <div className="space-y-3 px-0.5 pt-1">
            {[
              "先聊聊出发地、日期与期待",
              "一起选定交通与住宿",
              "你确认后，再安排每日行程",
            ].map((text, i) => (
              <div className="flex items-center gap-2.5" key={text}>
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-medium text-secondary-foreground">
                  {i + 1}
                </span>
                <p className="text-xs text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <p className="text-xs leading-5 text-muted-foreground">
            最近确认的安排。如需调整，在聊天中告诉我即可重新确认。
          </p>
          {(
            [
              ["去程", trip.outbound],
              ["回程", trip.inbound],
            ] as const
          ).map(([label, leg]) => {
            const Icon = leg.type === "train" ? TrainFront : Plane;
            return (
              <Card
                key={label}
                className="gap-2.5 rounded-2xl border-border/80 py-3.5 shadow-2xs"
              >
                <CardHeader className="gap-1 px-4">
                  <div className="flex items-center justify-between">
                    <CardDescription className="flex items-center gap-1.5 text-[11px]">
                      <Icon className="size-3.5 text-primary" />
                      {label} · {leg.type === "train" ? "火车" : "飞机"}
                    </CardDescription>
                    {leg.purchased && (
                      <Badge variant="secondary" className="gap-1 text-[10px]">
                        <Check className="size-3" />
                        已购买
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="text-sm font-semibold">
                    {leg.number}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2.5 px-4 text-xs">
                  <p className="flex items-center gap-2 font-medium text-foreground">
                    {leg.departure_station}
                    <ArrowRight className="size-3 shrink-0 text-muted-foreground" />
                    {leg.arrival_station}
                  </p>
                  <p className="leading-5 text-muted-foreground">
                    <time>{leg.departure_time.replace("T", " ")}</time>
                    <br />
                    抵达 <time>{leg.arrival_time.replace("T", " ")}</time>
                  </p>
                  {!leg.purchased && leg.purchase_url && (
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                      className="h-8 w-full rounded-xl text-xs"
                    >
                      <a
                        href={leg.purchase_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        前往购买
                        <ArrowUpRight className="size-3" />
                      </a>
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
          {trip.stays.map((stay, i) => (
            <Card
              key={i}
              className="gap-2.5 rounded-2xl border-border/80 py-3.5 shadow-2xs"
            >
              <CardHeader className="gap-1 px-4">
                <div className="flex items-center justify-between">
                  <CardDescription className="flex items-center gap-1.5 text-[11px]">
                    <Hotel className="size-3.5 text-primary" />
                    住宿
                  </CardDescription>
                  {stay.booked && (
                    <Badge variant="secondary" className="gap-1 text-[10px]">
                      <Check className="size-3" />
                      已预订
                    </Badge>
                  )}
                </div>
                <CardTitle className="text-sm font-semibold leading-5">
                  {stay.hotel}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 px-4 text-xs">
                <p className="leading-5 text-muted-foreground">
                  {stay.address}
                </p>
                <p className="leading-5 text-foreground/90">
                  {stay.check_in} 入住 · {stay.check_out} 退房
                </p>
                {!stay.booked && stay.purchase_url && (
                  <Button
                    asChild
                    variant="outline"
                    size="sm"
                    className="h-8 w-full rounded-xl text-xs"
                  >
                    <a
                      href={stay.purchase_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      前往预订
                      <ArrowUpRight className="size-3" />
                    </a>
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
          {!trip.stays.length && (
            <p className="text-xs text-muted-foreground">
              同日往返，无酒店住宿。
            </p>
          )}
        </>
      )}
      <Separator />
      <p className="flex gap-2 text-[11px] leading-5 text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
        确认方案不代表已经购买。请前往预订页面自行确认并支付。
      </p>
    </div>
  );
}

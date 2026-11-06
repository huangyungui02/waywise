import { useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLoaderData,
  useNavigate,
  useNavigation,
  useRevalidator,
} from "react-router";
import {
  CircleAlert,
  Compass,
  LoaderCircle,
  Menu,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { api } from "@/api";
import type { Conversation } from "@/api";

export type TravelActions = {
  create: (prompt?: string) => Promise<void>;
  creating: boolean;
};

function Brand() {
  return (
    <Link
      to="/"
      className="flex items-center gap-2.5 rounded-lg py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label="知途首页"
    >
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-2xs">
        <Compass className="size-4" strokeWidth={1.75} />
      </span>
      <span className="flex items-baseline gap-2">
        <span className="text-base font-semibold tracking-wide text-foreground">
          知途
        </span>
        <span className="text-[11px] text-muted-foreground">旅行助手</span>
      </span>
    </Link>
  );
}

export function Layout() {
  const conversations = useLoaderData() as Conversation[];
  const navigate = useNavigate();
  const revalidator = useRevalidator();
  const navigation = useNavigation();
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [deleting, setDeleting] = useState<Conversation | null>(null);
  const [removing, setRemoving] = useState(false);

  async function create(prompt?: string) {
    if (creating) return;
    setCreating(true);
    try {
      const conversation = await api<Conversation>("/conversations", {
        method: "POST",
      });
      setMobileOpen(false);
      await navigate(`/chat/${conversation.id}`, { state: { prompt } });
      revalidator.revalidate();
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  }

  async function remove() {
    if (!deleting) return;
    setRemoving(true);
    try {
      await api(`/conversations/${deleting.id}`, { method: "DELETE" });
      setDeleting(null);
      await navigate("/");
      revalidator.revalidate();
    } catch (e) {
      setError(String(e));
    } finally {
      setRemoving(false);
    }
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-sidebar px-3.5 py-5 text-sidebar-foreground">
      <div className="px-2">
        <Brand />
      </div>
      <Button
        onClick={() => void create()}
        disabled={creating}
        variant="outline"
        className="mt-5 h-10 w-full justify-start gap-2 rounded-xl border-border/90 bg-card text-xs font-medium text-foreground shadow-2xs hover:bg-card/80"
      >
        {creating ? (
          <LoaderCircle className="size-4 animate-spin text-primary" />
        ) : (
          <Plus className="size-4 text-primary" />
        )}
        开始一段旅行
      </Button>
      <div className="mb-2 mt-6 flex items-center justify-between px-2.5 text-[11px] font-medium text-muted-foreground">
        <span>我的旅行</span>
        {conversations.length > 0 && (
          <span className="tabular-nums text-[10px]">
            {conversations.length}
          </span>
        )}
      </div>
      <nav
        aria-label="我的旅行"
        className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-0.5"
      >
        {!conversations.length && (
          <p className="px-2.5 py-6 text-xs leading-6 text-muted-foreground">
            还没有旅行记录。
            <br />
            从一个想去的地方开始吧。
          </p>
        )}
        {conversations.map((c) => (
          <div className="group relative" key={c.id}>
            <NavLink
              to={`/chat/${c.id}`}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-between gap-2 rounded-xl px-2.5 py-2.5 pr-9 text-left transition-colors",
                  isActive
                    ? "bg-card font-medium text-foreground shadow-2xs ring-1 ring-border/70"
                    : "text-sidebar-foreground/85 hover:bg-sidebar-accent/70 hover:text-foreground",
                )
              }
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs leading-5">
                  {c.title}
                </span>
                <span className="mt-0.5 block text-[10px] font-normal text-muted-foreground">
                  {new Date(c.updated_at).toLocaleDateString("zh-CN")}
                </span>
              </span>
            </NavLink>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`删除 ${c.title}`}
              onClick={() => setDeleting(c)}
              className="absolute right-1 top-1/2 size-7 -translate-y-1/2 rounded-lg text-muted-foreground hover:bg-sidebar-accent hover:text-foreground md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100"
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
      </nav>
      <div className="mt-4 border-t border-sidebar-border pt-3.5 px-2.5">
        <p className="text-[11px] text-muted-foreground">
          往返交通 · 酒店住宿 · 每日行程
        </p>
      </div>
    </div>
  );

  return (
    <div className="flex h-dvh overflow-hidden bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 border-r border-border/80 md:block">
        {sidebar}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border/80 bg-background/90 px-3.5 backdrop-blur-xs md:hidden">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="打开旅行列表">
                <Menu className="size-4" />
              </Button>
            </SheetTrigger>
            <SheetContent
              side="left"
              className="w-64 gap-0 border-r border-border bg-sidebar p-0 text-sidebar-foreground"
            >
              <SheetHeader className="sr-only">
                <SheetTitle>我的旅行</SheetTitle>
                <SheetDescription>新建、切换或删除旅行会话</SheetDescription>
              </SheetHeader>
              {sidebar}
            </SheetContent>
          </Sheet>
          <Link
            to="/"
            className="flex items-center gap-2 text-sm font-semibold tracking-wide"
          >
            <span className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Compass className="size-3.5" />
            </span>
            知途
          </Link>
          <Button
            variant="ghost"
            size="icon"
            aria-label="新建旅行"
            onClick={() => void create()}
            disabled={creating}
          >
            <Plus className="size-4" />
          </Button>
        </div>
        {error && (
          <Alert variant="destructive" className="m-3 w-auto">
            <CircleAlert />
            <AlertDescription className="flex items-center justify-between gap-2">
              {error}
              <Button
                variant="ghost"
                size="icon"
                aria-label="关闭错误提示"
                onClick={() => setError("")}
              >
                <X />
              </Button>
            </AlertDescription>
          </Alert>
        )}
        <main className="relative flex min-h-0 min-w-0 flex-1 flex-col">
          {navigation.state === "loading" && (
            <div
              role="status"
              aria-label="正在打开旅行"
              className="absolute inset-x-0 top-0 z-20 h-0.5 animate-pulse bg-primary"
            />
          )}
          <Outlet context={{ create, creating } satisfies TravelActions} />
        </main>
      </div>
      <AlertDialog
        open={!!deleting}
        onOpenChange={(open) => {
          if (!open && !removing) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除这段旅行？</AlertDialogTitle>
            <AlertDialogDescription>
              「{deleting?.title}」的聊天记录和已确认安排将一并删除，无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={removing}>保留旅行</AlertDialogCancel>
            <AlertDialogAction
              disabled={removing}
              onClick={(event) => {
                event.preventDefault();
                void remove();
              }}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {removing ? "正在删除…" : "确认删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

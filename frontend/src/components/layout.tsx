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
  Sparkles,
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

function formatTitle(title: string): string {
  if (title.startsWith("这次旅行的想法：")) {
    return "旅行规划手札";
  }
  return title;
}

function Brand() {
  return (
    <Link
      to="/"
      className="group flex items-center gap-3 rounded-xl py-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label="知途首页"
    >
      <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-white shadow-sm transition-transform duration-200 group-hover:scale-105">
        <Compass className="size-4.5" strokeWidth={1.75} />
      </span>
      <div className="flex flex-col">
        <span className="font-serif text-lg font-medium tracking-wide text-foreground">
          知途
        </span>
        <span className="font-mono text-[9px] tracking-widest text-muted-foreground uppercase">
          JOURNEY
        </span>
      </div>
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
    const conversationId = deleting.id;
    setRemoving(true);
    try {
      await api(`/conversations/${conversationId}`, { method: "DELETE" });
      setDeleting(null);
      await navigate("/");
      revalidator.revalidate();
    } catch (e) {
      setError(String(e));
    } finally {
      setRemoving(false);
    }
  }

  const sidebarContent = (
    <div className="flex h-full flex-col p-4 text-sidebar-foreground">
      {/* 品牌与空间 */}
      <div className="px-2 pt-1 pb-2">
        <Brand />
      </div>

      {/* Arc 风格主操作按钮 */}
      <Button
        onClick={() => void create()}
        disabled={creating}
        variant="outline"
        className="mt-4 h-10 w-full justify-start gap-2.5 rounded-xl border-white/80 bg-white/70 px-3.5 text-xs font-medium text-foreground shadow-xs backdrop-blur-md transition-all duration-200 hover:bg-white hover:shadow hover:scale-[1.01]"
      >
        {creating ? (
          <LoaderCircle className="size-4 animate-spin text-primary" />
        ) : (
          <Plus className="size-4 text-primary" />
        )}
        <span>开始一段旅行</span>
      </Button>

      {/* 旅程列表 */}
      <div className="mb-2 mt-7 flex items-center justify-between px-2 text-[10px] font-medium tracking-wider text-muted-foreground/70 uppercase font-mono">
        <span>我的旅行</span>
      </div>

      <nav
        aria-label="我的旅行"
        className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-0.5"
      >
        {!conversations.length && (
          <div className="px-3 py-10 text-center">
            <p className="font-serif text-xs leading-relaxed text-muted-foreground/60">
              心之所向，皆为旅程。
              <br />
              随时开启一段漫游。
            </p>
          </div>
        )}
        {conversations.map((c) => (
          <div className="group relative" key={c.id}>
            <NavLink
              to={`/chat/${c.id}`}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-between gap-2 rounded-lg px-2.5 py-2.5 pr-9 text-left text-xs transition-colors",
                  isActive
                    ? "bg-white text-foreground shadow-2xs font-medium"
                    : "text-muted-foreground hover:bg-white/50 hover:text-foreground",
                )
              }
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs leading-5">
                  {formatTitle(c.title)}
                </span>
                <span className="mt-0.5 block text-[10px] font-normal text-muted-foreground/60 font-mono">
                  {new Date(c.updated_at).toLocaleDateString("zh-CN")}
                </span>
              </span>
            </NavLink>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`删除 ${c.title}`}
              onClick={() => setDeleting(c)}
              className="absolute right-1 top-1/2 size-7 -translate-y-1/2 rounded-md text-muted-foreground hover:bg-black/5 hover:text-foreground md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100"
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
      </nav>
    </div>
  );

  return (
    <div className="flex h-dvh w-full overflow-hidden p-0 sm:p-2.5 md:p-3">
      {/* 桌面端侧边栏 */}
      <aside className="hidden w-60 shrink-0 md:block">
        {sidebarContent}
      </aside>

      {/* 悬浮主窗口 (Arc Floating Window) */}
      <div className="arc-window flex min-w-0 flex-1 flex-col">
        {/* 移动端顶栏 */}
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-black/[0.04] bg-white/70 px-4 backdrop-blur-md md:hidden">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label="打开旅行列表"
                className="size-9 rounded-full"
              >
                <Menu className="size-4" />
              </Button>
            </SheetTrigger>
            <SheetContent
              side="left"
              className="w-64 gap-0 border-r border-black/[0.04] bg-[#f6f4ee] p-0"
            >
              <SheetHeader className="sr-only">
                <SheetTitle>我的旅行</SheetTitle>
                <SheetDescription>新建、切换或删除旅行会话</SheetDescription>
              </SheetHeader>
              {sidebarContent}
            </SheetContent>
          </Sheet>
          <Link
            to="/"
            className="flex items-center gap-2 font-serif text-base font-medium tracking-wide"
          >
            <span className="flex size-7 items-center justify-center rounded-xl bg-primary text-white">
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
            className="size-9 rounded-full"
          >
            <Plus className="size-4" />
          </Button>
        </div>

        {error && (
          <Alert variant="destructive" className="m-3 w-auto rounded-2xl">
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

        <main className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {navigation.state === "loading" && (
            <div
              role="status"
              aria-label="正在打开旅行"
              className="absolute inset-x-0 top-0 z-20 h-0.5 animate-pulse bg-primary/60"
            />
          )}
          <Outlet context={{ create, creating } satisfies TravelActions} />
        </main>
      </div>

      {/* 删除确认对话框 */}
      <AlertDialog
        open={Boolean(deleting)}
        onOpenChange={(open) => {
          if (!open && !removing) setDeleting(null);
        }}
      >
        <AlertDialogContent className="max-w-sm rounded-2xl border-0 bg-white/95 p-6 shadow-2xl backdrop-blur-2xl">
          <AlertDialogHeader className="text-left">
            <AlertDialogTitle className="font-serif text-base font-medium tracking-wide text-foreground">
              移除这段旅行记录？
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-muted-foreground leading-relaxed">
              将从历史记录中移除「{deleting?.title}」。已确认的行程安排也将一并清理。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="m-0 border-0 bg-transparent p-0 pt-2 sm:justify-end">
            <AlertDialogCancel
              variant="ghost"
              size="sm"
              disabled={removing}
              className="rounded-full px-4 text-xs font-normal text-muted-foreground hover:bg-black/5 hover:text-foreground"
            >
              保留
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              size="sm"
              disabled={removing}
              onClick={(event) => {
                event.preventDefault();
                void remove();
              }}
              className="rounded-full px-4 text-xs font-normal shadow-xs"
            >
              {removing ? "正在删除…" : "确认删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

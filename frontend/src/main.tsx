import { createRoot } from "react-dom/client";
import {
  createBrowserRouter,
  RouterProvider,
  useRouteError,
} from "react-router";
import { ArrowRight, Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Layout } from "@/components/layout";
import { Welcome } from "@/components/welcome";
import { ChatRoute } from "@/components/chat";
import { listConversations, loadConversation } from "./chat/cache";
import "./style.css";

function RouteError() {
  const error = useRouteError();
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-5 bg-background px-6 text-center">
      <Compass className="size-10 text-primary" />
      <h1 className="font-serif text-2xl">暂时无法打开</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        {error instanceof Error ? error.message : "会话不存在或服务不可用"}
      </p>
      <Button asChild variant="outline">
        <a href="/">
          返回首页
          <ArrowRight className="size-4" />
        </a>
      </Button>
    </div>
  );
}
const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    errorElement: <RouteError />,
    loader: listConversations,
    children: [
      { index: true, element: <Welcome /> },
      {
        path: "chat/:id",
        element: <ChatRoute />,
        loader: ({ params, request }) => loadConversation(params.id!, request.signal),
      },
    ],
  },
]);
createRoot(document.getElementById("root")!).render(
  <RouterProvider router={router} />,
);

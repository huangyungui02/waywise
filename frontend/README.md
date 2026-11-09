# 知途 · Waywise Web

Svelte 5 + SvelteKit 静态 SPA，通过官方 `@ai-sdk/svelte` 连接 FastAPI。

```bash
pnpm install --frozen-lockfile
pnpm dev
```

开发服务器默认代理 `/api` 到 `http://127.0.0.1:7932`。后端和 Redis 配置见根目录 README。

```bash
pnpm check
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

构建产物在 `build/`，由 FastAPI 托管，不需要额外 Node 服务。路由在 `src/routes/`，聊天状态在 `src/lib/chat/`，界面组件在 `src/lib/components/`。

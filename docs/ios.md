# 知途 · Waywise 个人 iOS 客户端

客户端将 SvelteKit 静态页面打包进 Capacitor，连接同一个 FastAPI 后端；聊天、回复恢复与行程仍由后端保存。App 仅在个人设备安装，不做分发；使用账号密码登录，业务数据按用户隔离。同一前端也由生产 Caddy 托管，可直接使用浏览器登录。

## 准备后端

按 README 使用 `docker compose -f compose.prod.yml up -d --build` 部署前端、后端与 Caddy，配置真实域名和服务端 `JWT_SECRET_KEY`。开放 80、443，后端 7932 只在容器网络内可访问。Caddy 自动申请并续期证书，FastAPI 不托管网页。

后端 `.env` 保留 iOS WebView 来源：

```dotenv
CORS_ORIGINS=["capacitor://localhost"]
```

跨域配置允许 WebView 发送请求，业务接口仍统一校验访问令牌；健康检查和 CORS 预检无需令牌。修改服务端配置后执行生产 Compose 的 `up -d` 重新创建容器。

## 配置和构建客户端

需要 macOS、Xcode 和已安装的 iOS SDK，以及 Node.js 22.18+ 和 pnpm 10。工程使用 Capacitor 8 和 Swift Package Manager，首次编译需要下载 Swift 依赖。

```bash
pnpm --dir frontend install --frozen-lockfile
cp frontend/.env.example frontend/.env.local
```

在 `frontend/.env.local` 填写后端地址（不含 `/api`）：

```dotenv
VITE_API_BASE_URL=https://travel.example.com
```

只有后端地址写入 App，JWT 签名密钥与旅游服务密钥始终留在后端。登录后 access token 只存在内存，refresh token 使用 `@aparajita/capacitor-secure-storage` 保存到 iOS Keychain。账号由后端启动时根据 `.env` 中的 `INITIAL_USERNAME` 和 `INITIAL_PASSWORD` 自动创建。

本地网页调试使用 `docker compose up --build`，Compose 自动将 `VITE_API_BASE_URL` 设为空并启用 Vite API 代理；网页使用 localStorage 保存 refresh token。

```bash
pnpm --dir frontend ios:sync
pnpm --dir frontend ios:open
```

`ios:sync` 先构建静态页面，再同步到已纳入仓库的 `frontend/ios` 工程。修改前端或后端地址后需要重新执行。无需再次运行 `cap add ios`。

在 Xcode 中选择 App scheme 和 iPhone 模拟器，点击 Run。真机运行需要在 Signing & Capabilities 选择自己的 Team，并将 Bundle Identifier 改为自己可用的标识；同时更新 `frontend/capacitor.config.ts` 中的 `appId`，保持一致。

也可执行 `pnpm --dir frontend ios:run` 选择设备。手机的 `localhost` 指手机自身；只有模拟器可用 Mac 的本机地址。推荐模拟器和真机统一使用可访问的 HTTPS 后端，不开启全局 HTTP 放行。

## 验证

依次检查新建会话、流式回复、切换会话、停止回复、确认方案和删除会话；生成期间切到后台再返回，检查历史和回复流能恢复。预订链接需在真机检查是否能打开目标页面。

App 的页面随安装包提供，但查询和聊天需要连接后端。初版保留 Capacitor 模板图标，尚未配置发布签名、TestFlight 或 App Store 发布。

启动时若显示无法连接服务器，检查构建时的 `VITE_API_BASE_URL`、设备网络、HTTPS 证书，以及后端是否允许 `capacitor://localhost` 跨域来源。登录失效时重新输入账号密码。修改前端配置后重新执行 `ios:sync` 并在 Xcode 中安装。

保留 `capacitor.config.ts` 中的 `server.appStartPath: '/'`，让入口为 `capacitor://localhost/`。无路径入口 `capacitor://localhost` 在根布局请求失败时会触发 SvelteKit 重载，表现为白屏、闪烁和重复的 `WebView loaded`。

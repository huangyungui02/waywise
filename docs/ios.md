# 知途 · Waywise 个人 iOS 客户端

客户端将 SvelteKit 静态页面打包进 Capacitor，连接同一个 FastAPI 后端；聊天、回复恢复与行程仍由后端保存。App 仅在个人设备安装，不做分发；使用构建时写入的个人 Bearer 令牌，无登录和用户隔离。网页只用于本地开发，不在服务器部署。

## 准备后端

按 README 使用 `docker compose -f compose.prod.yml up -d --build` 部署后端与 Caddy，配置真实域名和服务端 `ACCESS_TOKEN`。开放 80、443，后端 7932 只在容器网络内可访问。Caddy 自动申请并续期证书，FastAPI 不托管网页。

后端 `.env` 保留 iOS WebView 来源：

```dotenv
CORS_ORIGINS=["capacitor://localhost"]
```

跨域配置允许 WebView 发送请求，业务接口仍统一校验访问令牌；健康检查和 CORS 预检无需令牌。修改服务端配置后执行生产 Compose 的 `up -d` 重新创建容器。

## 配置和构建客户端

需要 macOS、Xcode 和已安装的 iOS SDK，以及 README 中的 Node.js、pnpm。工程使用 Capacitor 8 和 Swift Package Manager，首次编译需要下载 Swift 依赖。

```bash
pnpm --dir frontend install --frozen-lockfile
cp frontend/.env.example frontend/.env.local
```

在 `frontend/.env.local` 填写后端地址（不含 `/api`）和与后端相同的访问令牌：

```dotenv
VITE_API_BASE_URL=https://travel.example.com
VITE_ACCESS_TOKEN=<与后端 ACCESS_TOKEN 相同的令牌>
```

地址和个人访问令牌都会写进 App 的静态资源，令牌可从安装包提取，因此只用于个人安装，不分发安装包。实际配置放在被 Git 忽略的 `.env.local`，不要写入源码；不要在前端填写模型、高德或飞猪密钥。轮换服务端令牌后，必须同步修改前端配置、重新构建并安装。

本地 Vite 调试时 `VITE_API_BASE_URL` 留空，令牌仍需与本地后端一致；Docker 本地 Compose 会自动传入根目录 `.env` 的令牌。

```bash
pnpm --dir frontend ios:sync
pnpm --dir frontend ios:open
```

`ios:sync` 先构建静态页面，再同步到已纳入仓库的 `frontend/ios` 工程。修改前端、后端地址或令牌后需要重新执行。无需再次运行 `cap add ios`。

在 Xcode 中选择 App scheme 和 iPhone 模拟器，点击 Run。真机运行需要在 Signing & Capabilities 选择自己的 Team，并将 Bundle Identifier 改为自己可用的标识；同时更新 `frontend/capacitor.config.ts` 中的 `appId`，保持一致。

也可执行 `pnpm --dir frontend ios:run` 选择设备。手机的 `localhost` 指手机自身；只有模拟器可用 Mac 的本机地址。推荐模拟器和真机统一使用可访问的 HTTPS 后端，不开启全局 HTTP 放行。

## 验证

依次检查新建会话、流式回复、切换会话、停止回复、确认方案和删除会话；生成期间切到后台再返回，检查历史和回复流能恢复。预订链接需在真机检查是否能打开目标页面。

App 的页面随安装包提供，但查询和聊天需要连接后端。初版保留 Capacitor 模板图标，尚未配置发布签名、TestFlight 或 App Store 发布。

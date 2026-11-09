# 个人 iOS 客户端

客户端将 SvelteKit 静态页面打包进 Capacitor，连接同一个 FastAPI 后端；聊天、回复恢复与行程仍由后端保存。当前没有登录和用户隔离，请通过个人 VPN 或受控网络访问，勿直接开放无认证的公网接口。

## 准备后端

按 README 启动后端，并通过手机可访问的 HTTPS 地址提供服务。后端 `.env` 增加：

```dotenv
CORS_ORIGINS=["capacitor://localhost"]
```

修改后重启后端。Compose 默认仅绑定服务器的 `127.0.0.1:7932`，可由同机 HTTPS 反向代理转发到该端口；Redis 不需要对手机开放。代理应关闭聊天流响应缓冲，并允许较长的连接时间。

跨域配置仅允许 WebView 发请求，不提供访问认证；个人网络访问限制应由 VPN 或部署入口实现。

## 配置和构建客户端

需要 macOS、Xcode 和已安装的 iOS SDK，以及 README 中的 Node.js、pnpm。工程使用 Capacitor 8 和 Swift Package Manager，首次编译需要下载 Swift 依赖。

```bash
pnpm --dir frontend install --frozen-lockfile
cp frontend/.env.example frontend/.env.local
```

在 `frontend/.env.local` 填写后端地址，不含 `/api`：

```dotenv
VITE_API_BASE_URL=https://travel.example.com
```

地址在构建时写入前端，不是密钥。不要在此填写模型或飞猪凭据。网页同源部署时留空；若同时构建网页和 App，注意该文件会影响两种构建，也可以只在构建命令中设置环境变量。

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

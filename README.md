# 知途 · Waywise

知途（Waywise）是一个支持网页和个人 iOS App 的国内旅行助手，帮你查询火车票、机票、大巴商品和酒店，提供购买链接，并安排每日游览路线和预算。

先聊清楚需求，再选定交通和住宿；你确认方案后，助手再安排具体行程。已经订好的车票和酒店也可以直接告诉它。

目前支持 **国内多目的地串联、分段交通和酒店住宿**，各段可使用火车、飞机、大巴、自驾、打车或轮渡（含换乘），支持单程、往返或异地结束。

## 配置

复制配置文件，填写初始账号、百炼 API Key、高德 **Web 服务** Key 和 JWT 签名密钥：

```bash
cp .env.example .env
openssl rand -hex 32
```

将生成的随机值填入 `.env` 的 `JWT_SECRET_KEY`。这个密钥只保存在后端，不能提交到 Git 或编入 App；模型及其他服务密钥只保存在后端。

| 配置项 | 是否必填 | 说明 |
| --- | --- | --- |
| `INITIAL_USERNAME` | 是 | 初始用户名，支持字母、数字、下划线、点和连字符，统一转小写 |
| `INITIAL_PASSWORD` | 是 | 初始密码，8 至 128 个字符；只用于创建，不覆盖已有用户密码 |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥，至少 32 个字符 |
| `DATABASE_URL` | Compose 自动设置 | PostgreSQL 连接 URL；无需手动配置 |
| `DBOS_DATABASE_URL` | 否 | 默认与业务数据库共用，DBOS 使用独立 schema |
| `DASHSCOPE_API_KEY` | 是 | [百炼 API Key](https://help.aliyun.com/zh/model-studio/get-api-key) |
| `AMAP_MAPS_API_KEY` | 是 | [高德开放平台](https://console.amap.com/)的 Web 服务 Key |
| `DOMAIN` | 生产必填 | 解析到服务器的真实域名，供 Caddy 自动申请 HTTPS 证书 |
| `FLYAI_API_KEY` | 否 | 飞猪凭据，申请与试用说明见[飞猪快速开始](https://flyai.open.fliggy.com/docs/quickstart) |
| `TRAVEL_MODEL` | 否 | 默认 `qwen3.8-flash`，开启思考（`medium`） |
| `DASHSCOPE_BASE_URL` | 否 | 默认北京兼容地址，需与 Key 的地域和业务空间匹配 |

## Docker 本地开发

安装 Docker Engine 或 Docker Desktop，以及 Docker Compose v2。无需在宿主机安装 Python、Node.js 或飞猪 CLI。

```bash
docker compose up --build
```

打开 **http://127.0.0.1:5173**。本地 Compose 启动 Vite 前端和 FastAPI 后端，支持前后端代码热更新。
Vite 将 `/api` 代理到后端；前端通过用户名和密码登录，不包含服务端密钥。
后端 API 在 `http://127.0.0.1:7932`，不挂载网页；`/docs` 可通过 Authorize 输入令牌调试。
首次启动需要下载镜像及依赖，修改依赖后需重新构建或重启对应服务。

启动时会自动创建 `.env` 中 `INITIAL_USERNAME` 和 `INITIAL_PASSWORD` 配置的账号，直接使用该账号登录即可。已有同名账号时保留原密码；页面改密后，重启不会重置密码。暂不提供公开注册。

停止本地服务使用 `docker compose down`。本地项目名为 `travel-agent-dev`，数据库与生产数据卷分开。

## Docker 生产部署

生产配置独立使用，包含前端、后端、PostgreSQL 和 Caddy；前端在镜像构建阶段生成静态文件，由 Caddy 托管。服务器安装 Docker 和 Compose，配置 `.env`，
将 `DOMAIN` 改成真实域名并解析到服务器，允许公网 TCP 80、443 访问，然后运行：

```bash
docker compose -f compose.prod.yml up -d --build
docker compose -f compose.prod.yml ps
docker compose -f compose.prod.yml logs -f
```

Caddy 自动申请和续期证书，证书状态保存在持久卷中。后端 7932 不向宿主机发布。
打开 `https://你的域名`，使用创建的账号登录。前端与 `/api` 共用域名，无需额外配置前端 API 地址或网页 CORS。
访问 `https://你的域名/api/health` 检查服务；业务 API 需要 `Authorization: Bearer <access_token>`，令牌通过 `/api/auth/login` 获取。
iOS App 使用账号密码登录，聊天和行程按用户隔离。

两份 Compose **不要叠加使用**。生产项目名为 `travel-agent`，与原默认部署的数据卷命名保持一致；旧数据不会自动进入本地开发卷。
生产容器配置了退出重启和日志轮转，仍需自行监控磁盘并定期备份。

更新前等待当前回复结束，再执行同一条 `up -d --build` 命令。配置变更也使用 `up` 重新创建容器，不能只执行 `restart`。
停止并移除生产容器：

```bash
docker compose -f compose.prod.yml down
```

不要加 `-v`，否则会删除数据库和证书数据卷。运行时 `.env` 不进入后端镜像，容器也不读取宿主机的飞猪 CLI 配置；已有飞猪凭据通过 `FLYAI_API_KEY` 传入。

### 数据与备份

业务数据与 DBOS 执行记录保存在 PostgreSQL 的 `waywise` 数据库，分别使用 `public` 和 `dbos` schema；持久卷为 `postgres-data`。
Compose 内置数据库的用户名、密码和数据库名均为 `waywise`，仅供内部网络访问，无需配置数据库密码或连接地址。
本地开发也由 Compose 启动 PostgreSQL；宿主机数据库工具可连接 `127.0.0.1:5432`。独立部署后端时，可用 `DBOS_DATABASE_URL` 将执行记录放到独立 PostgreSQL 数据库。
首次启动会直接建表，不迁移原有数据。
DBOS 默认同时执行 4 个会话；已结束的执行记录保留 7 天并每小时清理，使用 `DBOS_RETENTION_DAYS` 调整。聊天历史和安排不受清理影响。

备份数据库，并将备份保存到服务器之外：

```bash
docker compose -f compose.prod.yml exec -T postgres pg_dump -U waywise -d waywise -Fc > waywise.dump
```

恢复时先停止后端，将备份恢复到空数据库，再启动后端：

```bash
docker compose -f compose.prod.yml stop travel-agent
docker compose -f compose.prod.yml exec -T postgres pg_restore -U waywise -d waywise --no-owner < waywise.dump
docker compose -f compose.prod.yml start travel-agent
```

## iOS 个人客户端

前端静态页面通过 Capacitor 打包进 iOS App，只在个人设备安装，不做分发。
只有后端地址在构建时写入 App；登录后 access token 保存在内存，refresh token 保存在 iOS Keychain。
构建配置和 Xcode 使用方式见 [iOS 使用说明](docs/ios.md)。也可以直接使用生产网页，两个客户端连接同一个后端。

## 可观测性（Logfire）

可选接入 [Logfire](https://pydantic.dev/docs/ai/integrations/logfire/)，查看 API 请求、
Agent 运行、模型调用和工具调用（包括 `call_flyai`）的链路、耗时、异常和 Token 用量。
在 Logfire 创建项目并取得 **Write Token**，将其填入本地 `.env` 的 `LOGFIRE_TOKEN`，
再执行 `docker compose -f compose.prod.yml up -d --build`。发送一条旅行咨询后，在对应项目查看 `travel-agent` 服务。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `LOGFIRE_TOKEN` | 空 | 留空不启用 Logfire；凭据只通过运行时环境传入 |
| `LOGFIRE_ENVIRONMENT` | `development` | 区分环境；`.env.example` 为 Docker 部署设为 `production` |
| `LOGFIRE_INCLUDE_CONTENT` | `false` | 设为 `true` 后采集对话、模型回复、工具参数和结果 |

默认不采集对话和工具正文、二进制内容、HTTP 请求头与 FastAPI 解析后的请求参数，
健康检查请求也不记录。开启正文采集后，旅行安排等信息会发送到 Logfire，
请按实际排查需要配置。飞猪 CLI 内部没有单独埋点，链路显示整个 `call_flyai` 调用。
PostgreSQL 负责保存聊天和已确认行程，Logfire 不替代业务存储。

## 如何使用

可以从一次完整需求开始：

> 想下个月找个周末，从上海去杭州玩三天，两个人，总预算 3000 元，坐高铁，
> 想去西湖和灵隐，住宿交通方便一点。车票和酒店都还没订，帮我推荐一下。

也可以告诉助手已有的安排：

> 我已经订好了去重庆的机票和酒店，想请你安排三天行程，回程还没买。

助手会补充询问必要信息，推荐各城市间未订的交通和酒店，并提供可用的购买链接。交通尚未购买且暂未找到购票链接时，也可以确认方案，助手会说明仍需核实的购票渠道。
你选定后，它会在聊天中展示交通与住宿方案卡片。点击“确认方案”或发消息同意后，再生成每日路线和预算。
后续想换车次、航班或酒店，直接告诉助手，调整后重新确认即可。

确认方案只表示同意按此规划，**不代表已经购买**。购票和订房需要你通过提供的链接前往预订页面完成。

推荐的酒店、门票和大巴等商品会自动加入本次旅行的备选清单。点击聊天右上角的购物袋图标，
可查看商品、跳转预订或移除备选；移动端从底部打开，桌面端从右侧打开。
清单保存在后端，保留推荐时的参考价和时间，不代表已购买；早期聊天中的商品不会自动补入清单。

左侧可以新建、切换和删除旅行。聊天、待确认方案和已确认安排保存在后端数据库，关闭页面或重启服务后，
重新打开对应会话即可读取。备份方式见上面的 Docker 部署说明。

长对话默认在估算上下文超过 500000 Token 时自动压缩较早内容，
保留摘要、最初需求及最近 12 条消息（工具调用配对可能使保留数量增加）。摘要使用同一个百炼模型，会产生额外模型调用费用；
可通过 `.env` 的 `COMPACT_MAX_TOKENS` 调整触发阈值。压缩后的上下文保存到服务端并用于后续对话，较早内容可能丢失细节。

## 当前限制

- 暂不支持非酒店住宿；凌晨入住等特殊安排需额外核对。
- 价格、余票、房态和退改规则以预订页面为准，售票期外可能无法查询。
- 关闭页面、刷新或切换会话后，回复会继续生成；返回会话可查看最新输出并接收后续内容。点击“停止”才会取消生成，并保存已生成的部分回复。
- 浏览器使用 IndexedDB 缓存已读取的消息以便快速预览；同步期间会显示提示，最终内容以服务端为准。清空浏览器缓存不会删除服务端历史。
- 当前部署使用单节点、单后端进程和 PostgreSQL。DBOS 默认同时执行 4 个会话，可通过 `MAX_CONCURRENT_RUNS` 调整，超出后排队。同一版本服务重启后会恢复未完成的工作流；已完成的模型和工具步骤不重跑，中断中的步骤可能重新执行并产生额外调用费用。
- 未完成模型请求的部分输出会在恢复时被替换为重试结果。DBOS 不保证外部接口恰好调用一次；本项目不执行代下单与支付。
- 更新代码会改变 DBOS 应用版本；部署新版本前请等待当前回复完成。PostgreSQL 数据卷必须持久化；当前仍按单后端进程部署。
- 使用账号密码登录与 PyJWT 签发的 JWT；access token 15 分钟、登录会话最长 30 天，刷新时轮换 refresh token。退出立即撤销当前会话，改密撤销全部会话。暂不提供公开注册、密码找回和设备管理。
- 网页 refresh token 存在 localStorage，iOS App 使用 Keychain；access token 仅存在内存。当前浏览器请使用单个标签页，尚未实现跨标签页刷新协调。
- Capacitor iOS 客户端支持个人后端连接，真机交互及发布需自行配置和验证，见 [iOS 使用说明](docs/ios.md)。

## 参与开发

账号与令牌设计见 [账号说明](docs/auth.md)。会话执行、恢复及缓存机制见 [会话恢复说明](docs/chat-recovery.md)。

项目基于 [PydanticAI](https://pydantic.dev/docs/ai/llms.txt)，接入高德地图与[飞猪 Skill](https://github.com/alibaba-flyai/flyai-skill)。
开发前请阅读 [AGENTS.md](AGENTS.md)，飞猪上游文件来源见 [skills/UPSTREAM.md](skills/UPSTREAM.md)。

本地开发统一使用上面的 `docker compose up --build`，一次启动 PostgreSQL、后端和 Vite 前端，支持代码热更新；无需分别启动前后端，也无需在宿主机安装飞猪 CLI。查看日志可运行 `docker compose logs -f`，后端 API 文档位于 `http://127.0.0.1:7932/docs`。

如需在宿主机执行检查或离线测试，另行安装 Python 3.12+、uv、Node.js 22.18+ 和 pnpm 10，再安装测试依赖：

```bash
uv sync
corepack enable
pnpm --dir frontend install --frozen-lockfile
```

运行离线测试（需本地 PostgreSQL，测试角色具有 CREATE DATABASE 权限）。可在另一终端启动临时测试库：

```bash
docker run --rm --name waywise-test-postgres -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55432:5432 postgres:18-bookworm
```

该测试库仅监听本机，不设置密码；正式部署使用上面的 Compose 配置。然后运行：

```bash
TEST_DATABASE_URL=postgresql://localhost:55432/postgres uv run python -m pytest -q
```

浏览器测试会自动启动离线测试后端和前端，无需旅游服务凭据；同样使用 `TEST_DATABASE_URL`（默认 `postgresql://localhost:55432/postgres`）：

```bash
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

Python 和浏览器测试均使用真实 DBOS、PostgreSQL 与官方 FunctionModel/TestModel，不需要 Redis，
不调用真实模型或旅游服务。Python 测试包含独立进程被强制终止后的恢复验证。

实际模型、地图和飞猪服务需要另行配置凭据并验证。

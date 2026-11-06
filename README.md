# 国内旅行 Agent

一个可以在浏览器里聊天的国内旅行助手，帮你查询往返火车票、机票和酒店，提供购买链接，并安排每日游览路线和预算。

先聊清楚需求，再选定交通和住宿；你确认方案后，助手再安排具体行程。已经订好的车票和酒店也可以直接告诉它。

目前支持 **单个目的城市、直达往返、酒店住宿**，去程和回程可以使用不同交通方式。

## Docker 部署

安装 Docker Engine 或 Docker Desktop，并确保可以使用 Docker Compose v2。
无需在宿主机安装 Python、Node.js 或飞猪 CLI，镜像会安装运行依赖并构建前端。

下载或克隆仓库，进入项目根目录：

```bash
cp .env.example .env
```

编辑 `.env`，填写百炼 API Key 和高德 **Web 服务** Key：

```dotenv
DASHSCOPE_API_KEY=你的百炼APIKey
AMAP_MAPS_API_KEY=你的高德Web服务Key
```

| 配置项 | 是否必填 | 说明 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 是 | [百炼 API Key](https://help.aliyun.com/zh/model-studio/get-api-key) |
| `AMAP_MAPS_API_KEY` | 是 | [高德开放平台](https://console.amap.com/)申请的 Web 服务类型 Key |
| `FLYAI_API_KEY` | 否 | 飞猪访问凭据，申请与试用说明见[飞猪快速开始](https://flyai.open.fliggy.com/docs/quickstart) |
| `TRAVEL_MODEL` | 否 | 默认 `qwen3.8-flash`，需支持 Responses 接口、内置搜索和工具调用 |
| `DASHSCOPE_BASE_URL` | 否 | 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`，需与 Key 的地域和业务空间匹配 |

Compose 在运行时读取 `.env`，该文件不会进入镜像。容器不读取宿主机的飞猪 CLI 配置，
已有飞猪凭据请通过 `FLYAI_API_KEY` 配置。模型、搜索及其他服务费用以提供方为准。

启动：

```bash
docker compose up -d --build
docker compose ps
```

打开 **http://127.0.0.1:7932**。首次构建需要下载镜像和依赖，可通过以下命令查看日志：

```bash
docker compose logs -f travel-agent
```

更新代码后重新运行 `docker compose up -d --build`；停止并移除容器：

```bash
docker compose down
```

聊天和行程保存在 Docker 命名卷 `travel-data` 的 `/app/data/travel.db`，
重建镜像或执行上述停止命令会保留数据。请勿使用 `docker compose down -v`，它会删除数据卷。
Compose 固定数据库路径，`.env` 中的 `DATABASE_PATH` 仅供本地开发使用。

备份时先停止服务，再复制整个数据目录：

```bash
docker compose stop travel-agent
docker compose cp travel-agent:/app/data ./backup
docker compose start travel-agent
```

Docker 默认使用独立数据卷，不会自动导入旧的本地 `data/` 数据。需要迁移时，
先启动一次容器以建立数据卷，然后停止服务，将旧数据库目录内容复制进去并修正权限：

```bash
docker compose stop travel-agent
docker compose cp ./data/. travel-agent:/app/data/
docker compose run --rm --no-deps --user root travel-agent chown -R traveler:traveler /app/data
docker compose start travel-agent
```

迁移前先备份原数据库和容器数据；复制时两端服务都应停止。
默认只绑定本机地址，当前没有用户登录与多用户隔离。

## 可观测性（Logfire）

可选接入 [Logfire](https://pydantic.dev/docs/ai/integrations/logfire/)，查看 API 请求、
Agent 运行、模型调用和工具调用（包括 `call_flyai`）的链路、耗时、异常和 Token 用量。
在 Logfire 创建项目并取得 **Write Token**，将其填入本地 `.env` 的 `LOGFIRE_TOKEN`，
再执行 `docker compose up -d --build`。发送一条旅行咨询后，在对应项目查看 `travel-agent` 服务。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `LOGFIRE_TOKEN` | 空 | 留空不启用 Logfire；凭据只通过运行时环境传入 |
| `LOGFIRE_ENVIRONMENT` | `development` | 区分环境；`.env.example` 为 Docker 部署设为 `production` |
| `LOGFIRE_INCLUDE_CONTENT` | `false` | 设为 `true` 后采集对话、模型回复、工具参数和结果 |

默认不采集对话和工具正文、二进制内容、HTTP 请求头与 FastAPI 解析后的请求参数，
健康检查和静态资源请求也不记录。开启正文采集后，旅行安排等信息会发送到 Logfire，
请按实际排查需要配置。飞猪 CLI 内部没有单独埋点，链路显示整个 `call_flyai` 调用。
SQLite 仍负责保存聊天和已确认行程，Logfire 不替代业务存储。

## 如何使用

可以从一次完整需求开始：

> 想下个月找个周末，从上海去杭州玩三天，两个人，总预算 3000 元，坐高铁，
> 想去西湖和灵隐，住宿交通方便一点。车票和酒店都还没订，帮我推荐一下。

也可以告诉助手已有的安排：

> 我已经订好了去重庆的机票和酒店，想请你安排三天行程，回程还没买。

助手会补充询问必要信息，推荐未订的往返交通和酒店，并提供购买链接。
你选定后，它会汇总完整安排供你确认；确认并检查通过后，再生成每日路线和预算。
后续想换车次、航班或酒店，直接告诉助手，调整后重新确认即可。

确认方案只表示同意按此规划，**不代表已经购买**。购票和订房需要你通过提供的链接前往预订页面完成。

左侧可以新建、切换和删除旅行。聊天和已确认安排保存在后端数据库，关闭页面或重启服务后，
重新打开对应会话即可读取。备份方式见上面的 Docker 部署说明。

## 当前限制

- 暂不支持中转、多目的城市或非酒店住宿；凌晨入住等特殊安排需额外核对。
- 价格、余票、房态和退改规则以预订页面为准，售票期外可能无法查询。
- 关闭页面、切换会话或停止生成会中断当前回复，保留已保存的消息和完整步骤；重新打开后可继续咨询，不会自动重跑中断的工具。
- 当前适合本地单进程运行，尚未提供用户登录和多用户数据隔离；暂不启动多个服务进程共享数据库。
- Tauri 移动端尚未接入。

## 参与开发

项目基于 [PydanticAI](https://pydantic.dev/docs/ai/llms.txt)，接入高德地图与[飞猪 Skill](https://github.com/alibaba-flyai/flyai-skill)。
开发前请阅读 [AGENTS.md](AGENTS.md)，飞猪上游文件来源见 [skills/UPSTREAM.md](skills/UPSTREAM.md)。

本地开发需要 Python 3.12+、uv、Node.js 22.12+ 和 npm。安装依赖并配置 `.env`：

```bash
uv sync
npm install -g @fly-ai/flyai-cli@1.0.16
npm --prefix frontend ci
```

后端模块保留在根目录：`agent.py` 定义 Agent 和工具，`app.py` 提供 FastAPI 接口，
`settings.py` 管理配置，`trip.py` 定义和保存行程。前端位于 `frontend/`，使用 Tailwind CSS 和 shadcn/ui。页面组件在 `src/components/`，
官方 UI 组件在 `src/components/ui/`；`src/style.css` 只保留样式导入和主题配置。

分别在两个终端启动后端和前端：

```bash
uv run uvicorn app:create_app --factory --host 127.0.0.1 --port 7932
npm --prefix frontend run dev
```

打开 Vite 打印的地址（通常为 `http://127.0.0.1:5173`）。
API 文档位于 `http://127.0.0.1:7932/docs`。
本地开发默认数据库为 `data/travel.db`，可通过 `DATABASE_PATH` 修改。
若需由本地后端托管前端，先执行 `npm --prefix frontend run build`。

运行离线测试：

```bash
uv run python -m pytest -q
```

浏览器测试会自动启动离线测试后端和前端，无需真实凭据：

```bash
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

测试不调用真实模型或旅游服务；实际使用需要配置凭据并验证服务可用性。

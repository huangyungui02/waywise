# 国内旅行 Agent

一个可以在浏览器里聊天的国内旅行助手，帮你查询往返火车票、机票和酒店，提供购买链接，并安排每日游览路线和预算。

先聊清楚需求，再选定交通和住宿；你确认方案后，助手再安排具体行程。已经订好的车票和酒店也可以直接告诉它。

目前支持 **单个目的城市、直达往返、酒店住宿**，去程和回程可以使用不同交通方式。

## 准备环境

- Python 3.12 或以上版本
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 22.12 或以上版本和 npm，用于构建界面及安装飞猪命令行工具
- 百炼 API Key 和高德 Web 服务 Key

## 安装

下载或克隆本仓库，进入项目根目录，执行：

```bash
uv sync
npm install -g @fly-ai/flyai-cli
cp .env.example .env
npm --prefix frontend ci
npm --prefix frontend run build
```

## 配置

编辑项目根目录的 `.env`：

```dotenv
DASHSCOPE_API_KEY=你的百炼APIKey
AMAP_MAPS_API_KEY=你的高德Web服务Key
```

| 配置项 | 是否必填 | 说明 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 是 | [百炼 API Key](https://help.aliyun.com/zh/model-studio/get-api-key) |
| `AMAP_MAPS_API_KEY` | 是 | [高德开放平台](https://console.amap.com/)申请的 **Web 服务** 类型 Key |
| `FLYAI_API_KEY` | 否 | 飞猪访问凭据，申请与试用说明见[飞猪快速开始](https://flyai.open.fliggy.com/docs/quickstart) |
| `TRAVEL_MODEL` | 否 | 默认 `qwen3.8-flash`，更换时需支持 Responses 接口、内置搜索和工具调用 |
| `DASHSCOPE_BASE_URL` | 否 | 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`，需与 Key 的地域和业务空间匹配 |
| `DATABASE_PATH` | 否 | 默认 `data/travel.db`，保存聊天、执行快照和已确认安排 |

已有飞猪 CLI 本机配置时可以继续使用。环境变量优先于 `.env`；请勿提交包含密钥的 `.env`。
模型、搜索及其他服务的费用与额度以各服务提供方为准。

## 启动

在项目根目录运行：

```bash
uv run uvicorn app:create_app --factory --host 127.0.0.1 --port 7932
```

在浏览器打开 **http://127.0.0.1:7932**，即可开始聊天。停止服务时在终端按 `Ctrl+C`。

界面由本地服务提供，无需从 CDN 加载。若页面无法打开，检查前端构建是否完成以及终端是否启动成功。

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
重新打开对应会话即可读取。备份时先停止服务，再复制 `data/` 目录（修改路径后请备份实际数据库文件）。

## 当前限制

- 暂不支持中转、多目的城市或非酒店住宿；凌晨入住等特殊安排需额外核对。
- 价格、余票、房态和退改规则以预订页面为准，售票期外可能无法查询。
- 关闭页面、切换会话或停止生成会中断当前回复，保留已保存的消息和完整步骤；重新打开后可继续咨询，不会自动重跑中断的工具。
- 当前适合本地单进程运行，尚未提供用户登录和多用户数据隔离；暂不启动多个服务进程共享数据库。
- Tauri 移动端尚未接入。

## 参与开发

项目基于 [PydanticAI](https://pydantic.dev/docs/ai/llms.txt)，接入高德地图与[飞猪 Skill](https://github.com/alibaba-flyai/flyai-skill)。
开发前请阅读 [AGENTS.md](AGENTS.md)，飞猪上游文件来源见 [skills/UPSTREAM.md](skills/UPSTREAM.md)。

前端开发时，在两个终端分别启动上面的后端命令和：

```bash
npm --prefix frontend run dev
```

打开 Vite 在终端打印的地址（通常为 `http://127.0.0.1:5173`），支持热更新。
FastAPI 接口文档位于 `http://127.0.0.1:7932/docs`。

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

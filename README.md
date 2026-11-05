# 国内旅行 Agent

一个可以在浏览器里聊天的国内旅行助手，帮你查询往返火车票、机票和酒店，提供购买链接，并安排每日游览路线和预算。

先聊清楚需求，再选定交通和住宿；你确认方案后，助手再安排具体行程。已经订好的车票和酒店也可以直接告诉它。

目前支持 **单个目的城市、直达往返、酒店住宿**，去程和回程可以使用不同交通方式。

## 准备环境

- Python 3.12 或以上版本
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 和 npm，用于安装飞猪命令行工具
- 百炼 API Key 和高德 Web 服务 Key

## 安装

下载或克隆本仓库，进入项目根目录，执行：

```bash
uv sync
npm install -g @fly-ai/flyai-cli
cp .env.example .env
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

已有飞猪 CLI 本机配置时可以继续使用。环境变量优先于 `.env`；请勿提交包含密钥的 `.env`。
模型、搜索及其他服务的费用与额度以各服务提供方为准。

## 启动

在项目根目录运行：

```bash
uv run uvicorn app:create_app --factory --host 127.0.0.1 --port 7932
```

在浏览器打开 **http://127.0.0.1:7932**，即可开始聊天。停止服务时在终端按 `Ctrl+C`。

页面首次加载需要访问 CDN。如果页面无法打开，先检查终端是否启动成功，以及浏览器能否加载页面资源。

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

## 当前限制

- 暂不支持中转、多目的城市或非酒店住宿；凌晨入住等特殊安排需额外核对。
- 价格、余票、房态和退改规则以预订页面为准，售票期外可能无法查询。
- 确认的旅行安排保存在服务内存中，重启后会清空，重要安排请自行留存。
- 当前提供本地聊天界面，尚未提供适合公开部署的登录和持久化能力。

## 参与开发

项目基于 [PydanticAI](https://pydantic.dev/docs/ai/llms.txt)，接入高德地图与[飞猪 Skill](https://github.com/alibaba-flyai/flyai-skill)。
开发前请阅读 [AGENTS.md](AGENTS.md)，飞猪上游文件来源见 [skills/UPSTREAM.md](skills/UPSTREAM.md)。

运行离线测试：

```bash
uv run python -m pytest -q
```

测试不调用真实模型或旅游服务；实际使用需要配置凭据并验证服务可用性。

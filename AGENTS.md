# 开发约定

## 项目范围

- 保持单 Agent，支持国内单目的地、直达火车、飞机或大巴往返和酒店住宿。
- 咨询顺序：了解需求与已有预订 → 推荐并选定交通和住宿 → 用户确认、工具校验并保存 → 每日行程规划。修改基础安排后重新确认。
- 确认采用方案与实际购买分别记录。用户通过真实预订链接自行购买；不实现代下单、支付或乘客证件存储。

## 实现原则

- 保持代码简洁，优先官方示例、API 和集成，避免重复实现框架已有能力。使用前核对已安装版本；[PydanticAI 官方参考](https://pydantic.dev/docs/ai/llms.txt)。
- 不为测试方便牺牲正式代码的简洁性，不添加仅供测试使用的可选参数、注入入口、分支或抽象。测试替身与依赖替换放在测试侧，优先使用 pytest fixture、monkeypatch、框架原生测试机制和官方测试模型；正式代码的扩展点必须有实际业务需求。
- 前端位于 frontend，使用 Svelte 5 + TypeScript + SvelteKit，样式使用 Tailwind CSS 和 shadcn-svelte，使用静态 SPA 构建与客户端路由；聊天使用官方 AI SDK，不自行实现流协议。后端位于 `app/`，使用 FastAPI 与官方 `VercelAIAdapter`，方便后续 Capacitor 客户端复用 API。
- 历史由后端 SQLite 管理，使用官方 `SqliteConversationStore` 保存会话，待确认和已确认的 TravelArrangements 通过 SQLAlchemy 定义存储表并同库保存，业务模型保留 Pydantic；浏览器提交的历史不能替代服务端记录。
- MCP 使用官方 `MCP` capability；飞猪查询使用 Harness `Skills`、`FileSystem` 加载上游 Skill 和参考文档，由专用工具 `call_flyai` 统一执行 CLI。
- 不自建 Agent 调度器、Skill 加载器、MCP 客户端、checkpoint 框架或通用工具抽象。
- 默认使用百炼 `qwen3.8-flash`，通过 `OpenAIResponsesModel` / `AlibabaProvider` 接入，开启思考（reasoning effort 为 medium），使用官方 `WebSearch` capability 启用原生搜索。
- 时间等动态信息通过工具按需获取，避免注入不断变化的系统指令。
- `skills/flyai/` 尽量保留上游内容；更新时在 `skills/UPSTREAM.md` 记录来源与本地变更，不为调整措辞改写上游 Skill 或官方工具描述。

## 提示词与工具

- 系统指令、工具描述和参数说明应自然连贯，符合真实旅行咨询流程。先明确需求，再确定交通和住宿；已知信息不重复询问。
- 系统指令描述整体流程和信息边界；工具描述说明用途、调用时机、所需信息及结果如何影响下一步，避免重复堆砌限制。
- 工具调用自然衔接用户当前的决定，面向用户的回复聚焦旅行安排，不暴露内部状态、参数或执行步骤。
- 价格、库存、时刻和预订链接以真实查询结果为依据，已有预订可依据用户提供的信息。缺失和失败要明确说明，不编造数据或宣称购买成功。

## 配置与凭据

- 环境配置统一使用 Pydantic Settings，凭据使用 `SecretStr`，不直接调用 `os.getenv` 或 `load_dotenv`。
- 密钥只放环境变量或本地 `.env`，不得写入代码、文档示例、测试快照或日志。

## 文档与验证

- 修改 Python 代码后运行 `uv check --fix` 和 `uv format`，处理剩余检查问题，再运行相关测试。前端修改运行 `pnpm --dir frontend check` 和 `pnpm --dir frontend build`，涉及交互时运行浏览器测试。
- README 面向首次接触项目的开源用户，优先说明用途、环境准备、安装配置、启动、使用示例和实际限制，确保命令与配置可照做。
- README 只保留简短开发入口；架构、框架 API 和内部状态等必要细节放在对应代码或单独文档，不加入调试过程和本次开发记录。
- 测试使用官方 `FunctionModel` / `TestModel` 和本地替身，默认不访问真实模型、地图或飞猪服务。运行 `uv run python -m pytest -q`，区分离线验证与真实服务联调结果。

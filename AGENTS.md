# 开发约定

- 当前只实现单 Agent，负责需求澄清、工具调用、方案比较和行程整合。
- 代码尽量保持简洁。优先使用官方文档示例、官方 API 和官方集成写法，而非自己造轮子；先核对已安装版本，再使用对应 API。
- PydanticAI 官方参考：https://pydantic.dev/docs/ai/llms.txt 。
- UI 使用官方 `Agent.to_web()`；MCP 使用官方 `MCP` capability；飞猪使用官方 Harness `Skills`、`FileSystem` 和 `Shell` 配合上游 Skill 与 CLI。
- 不自建前端、Agent 调度器、Skill 加载器、MCP 客户端、会话管理或通用工具抽象。
- 飞猪 Skill 在 `skills/flyai/`。尽量保留上游内容，更新时记录来源及本地变更。
- 价格、余票、时刻、酒店与预订链接必须来自真实工具结果；缺失和失败要明确说明，不伪造库存或下单成功。
- 当前预订以飞猪返回的链接交给用户完成，不新增支付、代下单或存储乘客证件的逻辑。
- 密钥只放环境变量或本地 `.env`，不得写入代码、文档示例、测试快照或日志。
- 环境配置统一使用 Pydantic Settings；凭据使用 SecretStr，不直接调用 os.getenv 或 load_dotenv。
- 默认模型为百炼 qwen3.8-flash，通过官方 OpenAIResponsesModel/AlibabaProvider 接入，使用官方 WebSearch capability 启用百炼原生联网搜索。
- 测试使用官方 `FunctionModel` / `TestModel` 和本地替身，默认不访问真实模型、地图或飞猪服务。

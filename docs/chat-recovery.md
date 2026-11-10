# 会话执行与恢复

PydanticAI 负责执行和正式历史，`VercelAIAdapter` 产生官方 AI SDK v6 事件。`fastapi-redis-sdk` 负责临时事件流和后台生产者。浏览器只发送本轮输入，模型历史来自服务端。

## 服务端

依赖固定在 `feature/resumable-streams` 分支 commit `fd7f483022c9b97ae437e972e2b84ea54b3034e6`，不是 PyPI 0.9.1。Redis 必须支持 SDK 所需的 XCFGSET、DELEX 和幂等 XADD；最低 8.6.2，建议 8.6.6 以上，Compose 固定为 8.8.0。

应用装配时创建一个 `StreamBackend`，在 lifespan 中调用 `detect()` 检查能力，并在连接池关闭前调用 `aclose()`。使用显式客户端读取应用的 SecretStr 配置。SDK 的 `open()` 创建运行，`spawn()` 持有后台任务并负责心跳和异常结束，`follow()` 完成历史重放及后续订阅。断开 HTTP 只关闭 reader。

`app/main.py` 负责应用装配和生命周期，`app/routes/` 提供 HTTP 接口。路由通过 FastAPI 依赖分别获取会话存储、`TravelStore` 和 `Replies`；列表、创建、重命名和商品移除不依赖回复执行器。`app/replies.py` 的 `Replies` 管理启动、停止、并发名额及恢复关联；私有的 `_ReplyExecution` 持有一轮回复的历史和保存结果，通过绑定方法接收官方适配器的完成与取消回调。完成状态只在历史保存成功后记录，异常时才补存本轮开始的历史，所有退出路径统一释放运行名额。`app/db/conversations.py` 的 `ConversationStore` 实现官方 `pydantic_ai.conversation_store.ConversationStore` 的 SQLAlchemy 存储原语，负责会话历史、首轮标题和启动收尾，与 `ArrangementStore`、`ProductStore` 一起归 `TravelStore` 持有。删除会话先校验并删除官方历史，再清理交通住宿安排与商品；三个存储通过 aiosqlite 共用 SQLite 文件与异步 Engine，消息保存及版本校验在同一事务中完成，整体会话删除仍按三个存储依次执行。`TravelStore` 是异步上下文管理器，启动时建表，关闭时释放 Engine；数据库方法直接使用 `AsyncSession`，调用方直接 await，不再手工转交线程池。后台任务仍由 Redis SDK 创建和持有。

协议桥接位于 `app/streams.py`：保存 `chunk.encode(6)`，读取 SDK 事件后交还官方适配器输出；SDK 结束事件转换为官方 DoneChunk，流中断转换为官方 ErrorChunk。每个已应用事件附加 transient `data-progress`，用于触发界面与预览缓存更新。没有自建 Redis 读循环、通知、事务检查点或任务调度器。

每个会话还保存一个应用自己的 Redis 键，内容只有当前运行 ID 和本轮开始前的 UI 消息（包括本轮用户输入）。这是会话与流的关联，不保存运行状态、事件或消费游标。读取详情通过 SDK 验证流仍存在；流已过期则只返回正式历史。旧运行由 SDK TTL 清理，删除会话后移除关联键并禁止访问其流。

SDK 原生 `REDIS_STREAM_MAX_RUN` 默认 3600 秒，最多 86400 秒；`REDIS_STREAM_DONE_TTL` 默认 120 秒，结束只能缩短寿命，不能超过运行剩余时间。它们由 SDK 的 Pydantic Settings 读取，无需再维护一份应用配置。流不裁剪。到期后正式消息仍在 SQLite，但临时协议事件不再可重放。

停止通过 PydanticAI CancellationToken 协作取消，使官方适配器保存已生成的部分消息；接口等待 SDK 持有的任务完成。服务关闭由 SDK 取消任务，应用保留本轮开始时保存的历史和用户输入，不保存未提交的中间步骤。执行异常时也使用这份历史收尾；正常完成和主动停止仍通过官方适配器回调保存消息。启动时将 SQLite 遗留的 running 状态收尾为 cancelled；没有自动续跑模型或工具。当前仍要求单后端进程，因为会话互斥与取消令牌保存在进程中。

## 浏览器

详情携带恢复基线、运行 ID 和追平游标，不携带事件前缀。活动运行的游标直接来自 SDK `writer.append()` 返回的已写入事件 ID，由现有运行对象保存；运行结束后游标为 null，前端等待完整重放结束。`ConversationTransport` 读取详情、设置本轮基线，随后通过官方 `DefaultChatTransport` 从同一 SDK 流重放并接收实时输出。消息、reasoning 与工具状态全部由 AI SDK 还原；没有自建 reducer 或手工拼接两段流。

恢复期间保留完整预览，直到 `data-progress` 达到服务端给出的追平位置才切换为实时消息；内部尚未追平的消息不会写回预览缓存。Svelte 5 直接订阅官方 `@ai-sdk/svelte` Chat 的响应式状态，不复制消息到另一套 store。Markdown 使用 derived 文本与 DOMPurify 安全渲染，未变化的内容保留 DOM；工具记录只在条数变化时滚动。聊天内容由一个随组件清理的 ResizeObserver 观察尺寸变化，隐藏的思考增量不触发滚动计算。主画布和消息卡片不叠加背景模糊。用户上滑立即暂停跟随，阅读位置与是否跟随最新输出分别维护。

SvelteKit 路由 load 只负责打开会话时提供初始数据或缓存预览；同一会话的列表重验证不再重新执行详情 load。会话的响应式 Conversation 实例统一读取最新详情，回复完成后刷新详情和会话列表，消息仍由 AI SDK 持有。切换会话只停止订阅。Svelte 的 window/document 事件声明在页面中：重新可见时，没有活动连接才同步，健康连接继续使用；联网事件和手动重试先关闭旧订阅，再从后端校准，避免沿用已经失效的连接。重建 AI SDK 实例必须从本轮基线重放，不能直接将缓存消息与任意增量拼接。

IndexedDB 只保存可随时丢弃的预览，流式期间先记录最新消息引用，按 250ms 合并执行完整消息复制和写入；完成、页面离开和卸载时提交最近预览。读取失败、写入失败或缓存被清空不影响服务端恢复。离线时可阅读缓存；联网后向服务端校准。删除会话或收到 404 时清理缓存。它不负责后台执行，也不提供应用资源离线安装。

## 验证

Python 业务测试使用 SDK 边界的本地替身，不仿真 Redis 8.6 协议。显式 `--redis-url` 测试与浏览器测试使用真实 SDK 和 Redis。模型使用官方 FunctionModel/TestModel，不访问真实旅行服务。

会话消息由官方 ConversationStore 基类组织为追加日志。SQLAlchemy 后端只实现五个必需存储方法，记录与新增消息在同一事务中写入，保留官方版本校验；历史读取使用基类默认实现。业务侧直接使用官方 Conversation，ConversationSummary 定义在路由中，仅作为 Pydantic 接口响应模型，Store 直接返回数据库记录。标题和回复状态是项目元数据，启动恢复仅将 running 状态更新为 cancelled，不重写消息。自动起名只在首轮完成时执行，手动改名直接更新标题，不维护标题标记或标题版本。

删除会话会移除会话记录、交通住宿和商品；消息日志暂留 SQLite，以免破坏官方 fork 共享的历史，不代表物理擦除消息。项目没有提供分支或 fork 接口，也不维护全库消息回收算法。

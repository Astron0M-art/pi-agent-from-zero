# Lessons

每个版本会在这里保留一份独立可运行的冻结快照。课程按照目录编号顺序学习，最新工程实现位于 `src/pi_agent_from_zero/`。

| 版本 | 课程 | 核心问题 |
|---|---|---|
| `v0.1.0` | [约 100 行最小 Agent](01-minimal-agent/README.md) | 模型如何请求工具，宿主如何审批、执行并回填结果？ |
| `v0.2.0` | [消息与模型适配](02-message-provider/README.md) | 如何统一模型可见消息，并让 Agent 脱离具体 Provider SDK？ |
| `v0.3.0` | [流式事件与取消](03-streaming-cancellation/README.md) | 如何增量展示模型输出，并在取消或超时时保持上下文一致？ |
| `v0.4.0` | [工具运行时](04-tool-runtime/README.md) | 如何用 Registry 和 Schema 安全地把工具声明、校验、执行与 Agent 循环解耦？ |
| `v0.5.0` | [Coding Tools](05-coding-tools/README.md) | 如何让 Agent 在项目边界内读、写、改、执行和搜索，并控制工具结果的上下文成本？ |

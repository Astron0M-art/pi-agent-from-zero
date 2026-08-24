# Pi 源码映射

锁定基线：`earendil-works/pi@1e95e16b61f4a561b932df83d58df52589e58635`（package `0.83.0`）。

| 教学概念 | Pi 源码锚点 | 本版保留 | 本版简化 |
|---|---|---|---|
| 统一消息联合 | [`ToolCall`、`UserMessage`、`AssistantMessage`、`ToolResultMessage`、`Message`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/types.ts#L356-L444) | 角色判别、结构化 ToolCall、调用 ID 与错误标记 | 只支持文本；省略 timestamp、usage、provider、model、stopReason 和多模态 content |
| 模型上下文 | [`Context`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/types.ts#L498-L503) | system prompt、消息序列、可用工具 | `available_tools` 只有名称，没有 Tool Schema |
| Provider 合约 | [`Provider`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/models.ts#L97-L154) | Agent 不依赖具体 SDK；Provider 负责模型调用 | 只有同步 `complete`；不含认证、模型目录、stream、refresh 和 deferred |
| 完成适配 | [`completeSimple`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/compat.ts#L291-L298) | 把一次模型请求收敛成最终 AssistantMessage | 教学版没有先构造 EventStream，v0.3.0 才补流式协议 |
| 离线替身 | [`MockAssistantStream` 与消息工厂](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/test/agent-loop.test.ts#L1-L62) | 可预测响应、记录/检查模型输入、无真实 API | 用同步脚本 FakeModel 代替事件流 Mock |

## 可以得出的结论

- Agent 内部应有 Provider 无关的消息语义，SDK 格式转换属于适配层。
- ToolCall 与 ToolResult 必须靠稳定 ID 关联，不能依赖数组位置或自然语言猜测。
- 测试替身必须走同一个 Provider 边界，否则只能证明另一套测试代码。

## 不能得出的结论

- 教学 `Provider.complete()` 不是 Pi 完整 Provider API，也不能推导所有 SDK 都支持同步完成。
- 统一 Message 不代表所有 Provider 原生格式相同；适配器仍需处理兼容差异。
- tuple 和 frozen dataclass 只保护进程内边界，不提供持久化、并发安全或跨语言协议。
- FakeModel 的确定性不代表真实模型确定性，也不替代行为评测。

源码结论只依据固定公开提交；本地上游工作区中的个人改动没有被读取为课程事实。

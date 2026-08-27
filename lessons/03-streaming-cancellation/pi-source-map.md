# Pi 源码映射

锁定基线：`earendil-works/pi@1e95e16b61f4a561b932df83d58df52589e58635`（package `0.83.0`）。

| 教学概念 | Pi 源码锚点 | 本版保留 | 本版简化 |
|---|---|---|---|
| 通用事件流 | [`EventStream`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/utils/event-stream.ts#L1-L88) | 可异步消费的增量事件、终点与最终结果概念 | Python 同步生成器，没有 Promise、队列和合并逻辑 |
| Assistant 流事件 | [`AssistantMessageEvent`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/types.ts#L512-L528) | text delta、done/error 终点 | 不含 thinking、tool-call delta、usage 和 stopReason |
| Agent 生命周期 | [`AgentEvent`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/types.ts#L422-L437) | agent、message、tool 的开始/更新/结束层次 | 教学事件更少，尚无 steering 消息 |
| 流转译与提交 | [`streamAssistantResponse`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/agent-loop.ts#L281-L371) | Provider signal、partial update、最终 AssistantMessage | 教学版用字符串一致性校验，不构造可变 partial message |
| 主循环 | [`runLoop`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/agent-loop.ts#L155-L275) | 模型—工具循环、事件外发、取消信号 | 无队列、follow-up、transformContext 和多工具并行 |
| 取消测试 | [`agent.test.ts` abort 场景](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/test/agent.test.ts#L263-L299) | 用 Abort/Cancellation token 验证停止 | 教学版离线 FakeModel，无真实 SDK 请求 |

## 结论边界

- 可以得出：事件流是 Provider 和宿主之间的控制协议，不只是打印动画；最终 Message 仍要有明确提交点。
- 不能得出：同步 Python 生成器等价于 Pi 的异步 EventStream，或 `terminate()` 足以提供生产级进程隔离。
- 本课只依据固定公开提交；本地上游仓库保持只读，私人改动不作为课程事实。

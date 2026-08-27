# 练习：实现安全的增量渲染器

实现 `render(events)`，要求：

1. 收到 `TextDelta` 时立即追加到缓冲区并打印。
2. 收到 `ToolStarted` / `ToolCompleted` 时记录工具名和错误状态。
3. 只有 `AgentCompleted` 才返回完整缓冲文本。
4. 收到 `AgentFailed` 时清空内部缓冲并抛出包含 kind 的异常。
5. 事件结束却没有终止事件时必须报协议错误。

再写三个离线测试：正常流、半流取消、缺失终点。不要修改 Agent，也不要读取 `Agent.messages` 来猜结果。

加分题：允许调用方传入 `on_delta` 与 `on_tool` 回调，同时保证回调异常不会被误分类为 Provider 错误。

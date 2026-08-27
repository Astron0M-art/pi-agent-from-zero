# 参考思路

渲染器应是 AgentEvent 的纯消费者：用局部 `chunks` 累积 TextDelta，用 `terminal_seen` 防止两个终点。`AgentCompleted` 返回 `"".join(chunks)`；`AgentFailed` 先清空列表再抛出自定义 `RenderError(kind, message)`；for 循环自然结束时若没有终点则抛 `ProtocolError`。

理解检验答案：

1. delta 是尚未提交的展示状态，Message 是下一轮模型可见的已提交语义。
2. token 只设置状态，执行代码必须到达 checkpoint，或把 signal 传入真正的异步 SDK。
3. Provider 错误意味着本次模型响应无效；命令超时是模型可以观察并据此改正的工具事实。
4. 单一终点让消费者无需猜测是成功、失败还是仍在等待，也避免完成后继续输出。
5. 事件没有稳定序列号、时间、schema version、持久化和确定性重放约束。

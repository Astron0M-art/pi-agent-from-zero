# 架构说明

## 一次运行，两条不同的数据管线

```text
模型可见上下文（跨轮）                运行时事件（即时消费）
UserMessage                           AgentStarted
     │                                     │
ModelRequest ──► Provider.stream ──► ProviderTextDelta
     ▲                                     │
     │                                TextDelta ──► CLI/TUI
     │                                     │
ToolResultMessage ◄── ToolCompleted ◄── AssistantCompleted
     ▲                                     │
     └──── ToolCall / 审批 / Bash ◄── ToolStarted
                                           │
                                AgentCompleted | AgentFailed
```

运行时事件供渲染器、日志或未来 TUI 观察；Message 只承载下一次模型调用需要看见的语义。把 `TextDelta` 逐字加入 messages 会产生许多伪 Assistant 轮次，并让取消后的半成品污染上下文。

## 提交点

Provider 可以产生多个 `ProviderTextDelta`，但必须以一个 `ProviderCompleted` 或 `ProviderFailed` 结束。Agent 会累积 delta，并在完成时检查拼接文本等于最终消息内容。只有通过校验，`AssistantMessage` 才进入 `Agent.messages`。

这形成一个小型事务：delta 是暂存输出，completed 是提交记录，failed/取消则回滚暂存消息。终端消费者仍然已经看见 delta，因此回滚的是模型历史，不是屏幕。

## 五个架构问题

| 问题 | v0.3.0 的答案 |
|---|---|
| 请求入口 | `Agent.stream(prompt, cancellation, timeout_seconds)`；`run()` 是兼容包装器 |
| 权威状态 | `Agent.messages` 保存已提交的模型上下文；事件本身不是持久状态 |
| 谁决定下一步 | 模型用最终 AssistantMessage 的 ToolCall 表达意图；Agent 验证事件协议、预算与取消后调度 |
| 副作用位置 | Bash 仍只在 `_execute()`；审批前后和轮询子进程时检查取消 |
| 完成证据 | 恰好一个终止事件、delta/final 一致、取消不提交半消息、外部副作用与离线测试 |

## 三种停止不是一种失败

- 用户取消：`cancelled`，由外部 token 触发。
- 运行截止：`timeout`，限制整个 Agent run。
- 命令超时：一个可回填模型的错误 ToolResult，模型可以改正方案。
- Provider/协议错误：分别是上游明确失败和事件序列违反合约。

检查点只会在 Agent/Provider 主动调用时生效。如果真实 SDK 在一个不可中断的同步调用内阻塞，token 无法神奇地抢占它；适配器必须把 signal 传给 SDK 或定期让出控制权。

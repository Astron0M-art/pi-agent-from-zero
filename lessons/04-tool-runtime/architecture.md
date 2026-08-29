# 架构说明

## 从条件分支到运行时管线

```text
ToolRegistry
  │ definitions
  ▼
ModelRequest.tools ──► Provider ──► AssistantMessage.ToolCall
                                           │
                                           ▼
                                  Registry.find(name)
                                           │
                                  validate(arguments)
                                           │  失败：统一错误 ToolResult
                                           ▼
                                  handler(arguments, token)
                                           │
                                           ▼
                                  ToolResultMessage(call_id)
                                           │
                                           └──► 下一轮 ModelRequest
```

ToolDefinition 是模型可见能力声明，handler 是宿主拥有的执行能力。模型只能提出 ToolCall；Registry 查找并校验后，宿主才可能发生副作用。

## 五个架构问题

| 问题 | v0.4.0 的答案 |
|---|---|
| 请求入口 | `Agent.stream(prompt)`；Registry 由宿主在构造 Agent 时注入 |
| 权威状态 | `Agent.messages` 保存模型上下文；`ToolRegistry` 保存本次进程可用工具集合 |
| 谁决定下一步 | 模型选择工具名与参数；Registry 决定调用是否合法；Agent 决定预算是否允许继续 |
| 副作用位置 | 只在已注册 handler 内；Schema 校验先于审批和执行 |
| 完成证据 | Provider 收到 Schema、错误参数不触发 handler、结果 ID 正确、预算前阻断外部文件 |

## ToolResult 是边界对象

handler 只返回 `ToolOutcome(content, is_error)`，不负责伪造调用 ID。Registry 用原始 ToolCall 补齐 `tool_call_id` 和 `tool_name`，并把未知工具、校验失败、预期执行失败和意外异常统一成 ToolResultMessage。这样 Agent 不需要知道每个工具如何失败。

## 两种预算

- `max_turns` 限制模型往返次数，防止模型一直请求工具。
- `max_tool_calls` 限制一次 run 的实际工具调度数，防止单条 AssistantMessage 批量请求过多副作用。

第二个预算在发出 ToolStarted 和执行 handler 之前检查，因此验收可以用“第二个文件没有出现”证明阻断真实发生。

## 错误、取消和恢复

- 未知工具和 Schema 错误成为 `is_error=True` 的模型可见结果，模型可在下一轮修正。
- handler 抛出的异常被 Registry 归一化，避免破坏 Agent 事件终点。
- CancellationToken 仍贯穿 Registry 与 handler；取消/整轮超时不会降级为普通工具错误。
- 工具调用预算耗尽直接产生 AgentFailed，不再发起更多副作用。
- messages、Registry 和预算计数尚未持久化；进程退出后不能恢复。

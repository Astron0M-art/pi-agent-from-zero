# 架构说明

## 从一个函数拆成三个权责边界

```text
                    模型可见边界
用户 ──► Agent.messages: tuple[Message, ...]
                    │
                    ▼
             ModelRequest
        model / system / messages / tools
                    │
             Provider 协议边界
                    ▼
   ┌──────── FakeModel ────────┐
   │   未来真实 SDK Adapter     │
   └───────────┬───────────────┘
               ▼
       AssistantMessage
          │           │
       最终文本     ToolCall(id)
                       │
                 Agent 宿主执行
                       ▼
              ToolResultMessage(id)
                       │
                       └────► 下一次 ModelRequest
```

## 五个架构问题

| 问题 | v0.2.0 的答案 |
|---|---|
| 请求入口 | `Agent.run(prompt)` |
| 权威状态 | `Agent.messages` 是当前进程内模型可见上下文；Provider 收到不可变 tuple 快照 |
| 谁决定下一步 | Provider 返回的 `AssistantMessage.tool_calls` 表达模型意图；Agent 根据是否存在工具调用决定继续 |
| 副作用位置 | 仍只在 `Agent._execute()` 中，Provider 和 Message 类不执行工具 |
| 完成证据 | FakeModel 捕获的 `ModelRequest`、关联 ID 正确的 ToolResult、磁盘外部状态和自动化测试 |

## 三种消息不是三份历史

- `UserMessage`：用户交给模型的任务或补充信息。
- `AssistantMessage`：模型文本与结构化工具意图。
- `ToolResultMessage`：宿主执行后的事实，包含请求 ID、工具名、内容与错误标记。

这三者组成一条模型可见消息序列。运行时事件、TUI 展示记录和未来的持久化 Session 都不在本版消息对象中，避免一个列表承担所有权责。

## Provider 的职责

Provider 接收 `ModelRequest`，负责把统一类型转换成目标 SDK 的负载，再把响应转换回 `AssistantMessage`。本版只实现离线 `FakeModel`；它记录每次请求并按脚本返回结果，允许测试精确断言模型看见了什么。

## 错误、停止与恢复

- 未知工具或错误参数会变成带原调用 ID 的错误 ToolResult，模型可以修正。
- Provider 抛错会直接终止本轮；v0.3.0 将把错误和取消纳入事件协议。
- FakeModel 脚本耗尽会明确报错，避免测试误用最后一次结果。
- 循环预算仍限制 Provider 往返次数。
- messages 没有写盘、版本或 Session identity，进程退出后不能恢复。

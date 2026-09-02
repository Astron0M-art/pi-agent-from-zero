# 架构说明：从通用 Registry 到项目内 Coding Tools

## 数据流

```text
用户请求
  ↓
Agent → ModelRequest(五个 ToolDefinition) → FakeModel
  ↑                                      ↓
messages ← ToolResult ← ToolRegistry ← ToolCall
                              ↓
                    Schema 校验 + Cancellation
                              ↓
          ProjectWorkspace → read/write/edit/grep
                    项目 cwd → bash
                              ↓
                    OutputLimits 统一截断
```

## 1. 请求入口

入口仍是 `Agent.stream(prompt)`。Agent 不知道如何读写文件，只把 Registry 的五个声明交给模型，并按模型返回的 `ToolCall` 调用 Registry。

## 2. 权威状态

- 对话权威状态：`Agent.messages`；
- 工具权威定义：`ToolRegistry.definitions`；
- 文件事实：磁盘，不是模型的自然语言总结；
- 路径边界：解析后的 `ProjectWorkspace.root`；
- 输出预算：Registry 的 `OutputLimits`。

测试总是重新读取磁盘验证副作用，因此“模型说完成”不是完成证据。

## 3. 谁决定下一步

模型决定调用哪个工具及其参数；宿主代码决定参数是否合法、路径是否留在项目内、是否批准副作用、何时取消、结果最多能占多少上下文。工具执行结果回填后，模型再决定继续调用或结束。

## 4. 副作用在哪里

- `read` 和 `grep` 读取磁盘，不修改项目；
- `write` 创建目录并创建或覆盖文件；
- `edit` 在唯一精确匹配后覆盖文件；
- `bash` 可以产生任意命令允许的副作用。

教学版要求 `write/edit/bash` 经宿主审批。路径边界只约束 Python 文件工具；Bash 仍是高能力工具，完整规则将在权限版本实现。

## 5. 错误、取消与恢复

Schema 错误在处理器执行前转为 `ToolResultMessage(is_error=True)`。路径逃逸、文件不存在、非 UTF-8 和非唯一编辑属于预期工具错误，也回填模型，让模型有机会修正参数。取消信号不会降级成普通工具错误，而是终止本轮。

`write/edit` 在写入前检查取消，写后再检查一次；本版尚未实现临时文件替换和事务恢复，因此进程在底层写入期间崩溃仍可能留下部分文件。

## 6. 输出截断为何放在 Registry

若每个工具各自决定是否截断，新工具很容易忘记预算。`ToolRegistry.execute()` 是所有成功工具结果进入模型的单一出口，因此在这里统一应用字符数与行数上限。教学版保留头部和截断标记；Pi 会按工具语义区分 head/tail，并按 UTF-8 字节数限制。

## 五个必答问题

1. **上一版失败在哪里？** 只有 Bash，缺少稳定、可测试的文件领域接口，任意输出也可能挤满上下文。
2. **最小新抽象是什么？** 共享项目根解析的 `ProjectWorkspace`，以及 Registry 级 `OutputLimits`。
3. **谁决定下一步？** 模型选择工具；宿主拥有校验、边界、审批、取消与预算的最终决定权。
4. **哪些副作用需要权限和审计？** `write/edit/bash`；本版只有审批，审计留到 v0.8.0。
5. **什么证明完成？** FakeModel 验证协议，临时目录验证真实文件，测试验证失败时不发生副作用，结果长度与行数验证截断。

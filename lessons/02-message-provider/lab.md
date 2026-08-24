# 实验手册

## 实验 1：正常 Provider 往返

运行：

```bash
python lessons/02-message-provider/snapshot/agent.py "告诉我当前目录"
```

批准 `pwd`。在代码中打印 `fake.requests`，确认第一次请求末尾是 `UserMessage`，第二次请求末尾是 `ToolResultMessage`，且 `tool_call_id == "call-1"`。

## 实验 2：边界任务——未知工具

把 FakeModel 第一条响应改成：

```python
AssistantMessage(tool_calls=(ToolCall("call-x", "read", {"path": "README.md"}),))
```

预期：审批函数不应被调用，Agent 不崩溃，下一次 ModelRequest 包含 `is_error=True` 且保留 `call-x` 的 ToolResult。这证明“能力不可用”也能通过统一协议反馈。

## 实验 3：故障注入——脚本耗尽

只给 FakeModel 一条 Bash ToolCall 响应，不提供第二条响应。运行后应看到 `FakeModel has no scripted response left`。这个失败说明 Provider 调用错误尚未成为模型可见事件，正是 v0.3.0 要解决的问题。

## 实验 4：实现适配器

完成 [`exercises/README.md`](exercises/README.md) 中的 `UppercaseProvider`：它模拟一家字段完全不同的外部 SDK，但对 Agent 仍暴露 `complete(ModelRequest) -> AssistantMessage`。不得修改 Agent。

## 自动验收

```bash
python -m unittest discover -s lessons/02-message-provider/tests -v
pytest -q
```

验证重点不是模型自报，而是：Provider 收到结构正确的请求、ToolResult ID 关联正确、获批副作用确实发生、未知工具没有被执行。

## 理解检验

1. Provider 为什么不应该直接修改 `Agent.messages`？
2. `tool_call_id` 解决了哪一种歧义？
3. 为什么 `available_tools=("bash",)` 还不算 Tool Registry？
4. FakeModel 与在测试里直接 mock `Agent.run()` 有什么本质区别？
5. 哪些状态绝不能因为有了 Message 类型就塞进 messages？

参考答案见 [`solution/README.md`](solution/README.md)。

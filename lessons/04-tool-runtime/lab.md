# 实验手册

## 实验 1：正常 Registry 往返

```bash
python lessons/04-tool-runtime/snapshot/agent.py
```

输入 `y`。观察第一次 `ModelRequest.tools` 中的 bash 定义，然后确认 ToolResult 的 `tool_call_id == "call-1"`，最终回答来自第二次模型请求。

## 实验 2：边界任务——错误参数

把第一条 ToolCall 改成：

```python
ToolCall("bad-1", "bash", {"command": 42})
```

预期：不出现审批提示，不启动 shell，下一次 ModelRequest 收到 `is_error=True` 且内容含 `arguments.command: expected string`。Schema 校验必须先于权限询问，否则无效调用也会骚扰用户。

## 实验 3：故障注入——未知工具与 handler 异常

依次尝试未注册的 `read` 工具，以及一个直接 `raise RuntimeError("boom")` 的 handler。预期两者都保留原调用 ID 并成为错误 ToolResult，Agent 可继续让 FakeModel 给出最终回答。

## 实验 4：外部结果验收——工具预算

构造同一条 AssistantMessage，依次请求 `touch first` 和 `touch forbidden`，把 `max_tool_calls=1`。运行后必须同时满足：

- `first` 存在；
- `forbidden` 不存在；
- 最终事件是 `AgentFailed(kind="budget")`；
- 第二个调用没有 ToolStarted。

这比断言 Agent 文本说“我停止了”更强。

## 实验 5：注册新工具

完成 [`exercises/README.md`](exercises/README.md) 的 `repeat` 工具。不得修改 Agent，也不得在 System Prompt 中硬编码参数规则。

## 自动验收

```bash
python -m unittest discover -s lessons/04-tool-runtime/tests -v
pytest -q
```

## 理解检验

1. ToolDefinition 为什么不应该包含真实执行结果？
2. 为什么 Schema 校验必须发生在审批之前？
3. handler 为什么不直接返回 ToolResultMessage？
4. 模型轮次预算与工具调用预算分别防什么？
5. Registry 中注册成功为什么不等于获得权限？

参考答案见 [`solution/README.md`](solution/README.md)。

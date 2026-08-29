# v0.4.0：工具运行时

v0.3.0 虽然有 ToolCall 和 ToolResult，但 Agent 仍把 `bash` 名称、参数检查、审批、进程执行和错误格式全部写死在 `_execute()` 里。Provider 只看见 `("bash",)`，不知道工具用途和参数 Schema；增加第二个工具只能继续堆条件分支。

本版引入最小 Tool Runtime：`ToolDefinition` 描述模型可见合约，`ToolRegistry` 负责查找、Schema 校验、执行和结果归一化，Agent 只负责编排事件与预算。所有错误结果都保留 `tool_call_id`，模型可以在下一轮修正。

## 学习目标

完成本课后，你应该能：

1. 区分 ToolDefinition、Tool handler、ToolCall 和 ToolResultMessage。
2. 解释为何 Schema 必须在审批和副作用之前校验。
3. 让 Provider 收到完整工具定义，而不只是工具名称。
4. 用 Registry 增加工具，而不修改 Agent 循环。
5. 用模型轮次预算和工具调用预算阻止不同形式的失控循环。

先修内容：[v0.3.0 流式事件与取消](../03-streaming-cancellation/README.md)。

## 运行

无需 API Key，从仓库根目录执行：

```bash
python lessons/04-tool-runtime/snapshot/agent.py
```

看到 `pwd` 审批时输入 `y`。预期依次看到增量文本、`tool:start`、`tool:done` 和工具结果。输入 `n` 会得到可回填模型的错误 ToolResult。

独立测试：

```bash
python -m unittest discover -s lessons/04-tool-runtime/tests -v
```

## 阅读顺序

1. [`snapshot/tools.py`](snapshot/tools.py)：定义、Schema、Registry、结果归一化。
2. [`snapshot/providers.py`](snapshot/providers.py)：确认 ModelRequest 携带工具定义。
3. [`snapshot/agent.py`](snapshot/agent.py)：观察 Agent 如何只依赖 Registry。
4. [`architecture.md`](architecture.md) 与 [`pi-source-map.md`](pi-source-map.md)。
5. [`lab.md`](lab.md)：注册新工具并注入错误参数。

## 本版不解决

- 教学 Schema 只支持顶层 object 和少量标量约束，不是完整 JSON Schema 实现，也不做 Pi 的参数 coercion。
- Bash 仍是唯一内置副作用工具；read、write、edit、grep 和输出截断属于 v0.5.0。
- 每个工具仍自行调用审批回调；统一 allow/ask/deny、路径边界和审计属于 v0.8.0。
- 工具按顺序执行，没有并行批次、动态注册、流式工具进度或生产级沙箱。
- Registry 是进程内对象，不等于 MCP 工具发现，也不提供 Session 恢复。

# 实验：从事件序列重建一块终端屏幕

## 实验 1：正常任务

```bash
python lessons/06-tui-basics/snapshot/tui.py
python -m unittest discover -s lessons/06-tui-basics/tests -v
```

确认最终帧同时包含用户消息、两段助手消息、成功 grep 卡片、空输入光标和 completed 状态。

## 实验 2：边界任务——窄而短的视口

将 Renderer 改为 `width=48, height=12`，输入 20 条消息。预期旧显示行被替换为 `earlier entries hidden`，每行长度均为 48，输入与状态仍在底部。

## 实验 3：故障注入——工具拒绝

构造 `ToolStarted(write)`，随后发送 `ToolCompleted(..., is_error=True)`，最后发送 `AgentFailed`。检查失败卡片、输出原因和失败状态栏同时存在。不得在失败时清空消息。

## 实验 4：故障注入——流式重复

依次发送 `TextDelta("hel")`、`TextDelta("lo")` 和 `AssistantCompleted("hello")`。正确结果只有一个 `hello`。若出现 `hellohello`，说明把增量文本和最终快照都当成了追加事件。

## 实验 5：修改代码

给 `InputBuffer` 增加 `move_left()` 与 `move_right()`：

- 光标不能小于 0 或大于文本长度；
- 在边界调用时返回等价状态；
- 插入仍发生在光标位置；
- 增加空文本、ASCII 和中文测试。

## 理解检验

1. 为什么 `TuiState.messages` 不能直接交给 Provider？
2. 为什么 `AssistantCompleted` 应替换当前流式快照而不是追加？
3. 工具失败后为何不立即把整个运行标成失败？
4. 固定帧测试能证明什么，不能证明什么？
5. Session 恢复时应保存终端帧还是事实记录？

参考答案见 [`solution/README.md`](solution/README.md)。

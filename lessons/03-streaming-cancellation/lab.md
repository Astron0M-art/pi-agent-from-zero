# 实验手册

## 实验 1：观察正常事件顺序

```bash
python lessons/03-streaming-cancellation/snapshot/agent.py
```

输入 `y`，观察文本 delta、`tool:start`、`tool:done` 和最终 delta。回答：CLI 为什么不需要等待完整回答才开始显示？

## 实验 2：半流取消

打开 `tests/test_agent.py` 的 `cancel_mid_stream`。它先产生“半句”，随后调用 `token.cancel()`。运行：

```bash
python -m unittest lessons/03-streaming-cancellation/tests/test_agent.py -v
```

预期：消费者看见一个 TextDelta，最终得到 `AgentFailed(kind="cancelled")`，但 messages 只有 UserMessage。

## 实验 3：故障注入——完成内容不一致

让 Provider 先发 `ProviderTextDelta("甲")`，最后完成 `AssistantMessage("乙")`。预期 Agent 拒绝提交最终消息。再删除 `ProviderCompleted`，观察“缺失终点”失败。

这两类错误说明流协议必须有可验证的不变量，而不是“生成器结束就当成功”。

## 实验 4：统一截止时间

当前工程实现支持：

```python
events = list(agent.stream("任务", timeout_seconds=0))
```

预期先得到 `AgentStarted`，再得到 `AgentFailed(kind="timeout")`，且 Provider 没有收到请求。冻结快照保留最小 `CancellationToken(timeout=...)` 供你自行接入 CLI。

## 实验 5：练习渲染器

完成 [`exercises/README.md`](exercises/README.md) 的缓冲渲染器；参考答案见 [`solution/README.md`](solution/README.md)。

## 自动验收

```bash
python -m unittest discover -s lessons/03-streaming-cancellation/tests -v
pytest -q
```

验收的是事件顺序、提交点和外部状态，不以模型自称“已取消”作为证据。

## 理解检验

1. TextDelta 和 AssistantMessage 为什么不能共用一条 history？
2. `cancel()` 为什么不会自动打断任意阻塞函数？
3. Provider 错误与命令超时为什么采用不同反馈路径？
4. 终止事件为什么必须恰好一个？
5. 当前事件为什么还不能称为可回放 Trace？

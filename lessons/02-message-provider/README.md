# v0.2.0：消息与模型适配

v0.1.0 已经跑通最小循环，但 history 是随手拼出的字符串字典，`ModelOutput.bash_command` 把模型、消息和 Bash 耦合在一起。只要接入第二家模型服务、需要关联工具调用，或字段拼错，问题就会扩散到 Agent 循环。

这一版引入两个最小边界：统一 `Message` 联合类型负责“模型看见什么”，`Provider.complete(ModelRequest)` 负责“如何调用某个模型服务”。`FakeModel` 实现同一接口，所以测试与真实适配器将共享调用边界。

## 学习目标

完成本课后，你应该能：

1. 区分 User、Assistant 和 ToolResult 三种消息的职责。
2. 用 `tool_call_id` 证明结果属于哪次工具请求。
3. 解释为什么 Agent 依赖 Provider 协议，而不是某家 SDK。
4. 用 FakeModel 检查完整请求，而不连接网络或付费模型。
5. 识别“统一消息”与“把所有运行时状态都塞进消息”的区别。

先修内容：完成 [v0.1.0](../01-minimal-agent/README.md)，理解模型—工具循环和审批边界。

## 运行

在仓库根目录执行：

```bash
python lessons/02-message-provider/snapshot/agent.py "告诉我当前目录"
```

批准 `pwd` 后，FakeModel 会通过第二个 `ModelRequest` 读到类型化 `ToolResultMessage` 并给出最终答案。无需 API Key。

独立测试冻结快照：

```bash
python -m unittest discover -s lessons/02-message-provider/tests -v
```

## 阅读顺序

1. [`snapshot/messages.py`](snapshot/messages.py)：先认识模型可见协议。
2. [`snapshot/providers.py`](snapshot/providers.py)：观察 Provider 的稳定输入输出。
3. [`snapshot/agent.py`](snapshot/agent.py)：看 Agent 如何只依赖抽象。
4. [`architecture.md`](architecture.md) 与 [`pi-source-map.md`](pi-source-map.md)：区分教学简化与 Pi 实装。
5. [`lab.md`](lab.md)：通过假 Provider 和错误消息验证边界。

## 本版不解决

- `complete()` 仍是一次性同步结果，没有增量事件、取消或 Provider 错误事件；这是 v0.3.0。
- Bash 参数仍靠 `isinstance` 手工检查，没有 Tool Registry 和 JSON Schema；这是 v0.4.0。
- 只有 Bash，没有文件工具和输出截断；这是 v0.5.0。
- 消息只在内存中，不等于 Session，也不能恢复。
- FakeModel 证明控制流，不证明真实模型的答案质量。

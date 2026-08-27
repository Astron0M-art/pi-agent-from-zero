# v0.3.0：流式事件与取消

v0.2.0 的 `Provider.complete()` 只能等待整条消息返回。它隐藏了首字延迟，调用方看不到工具生命周期；Provider 卡住或用户改变主意时，Agent 也没有统一的停止协议。

本版把 Provider 输出改成事件流，并把模型可见消息与运行时事件明确分开。`TextDelta` 可以立即渲染，但 `AssistantMessage` 只有在完成事件到达且文本一致时才进入 history。取消或超时只在检查点生效，因此这是“协作式取消”，不是强制抢占。

## 学习目标

完成本课后，你应该能：

1. 区分 Provider 事件、Agent 生命周期事件和模型可见 Message。
2. 解释增量文本为何不能直接写进下一轮模型上下文。
3. 用同一 CancellationToken 终止模型流与运行循环。
4. 区分用户取消、统一截止时间、Provider 错误和协议错误。
5. 用 FakeModel 注入半流取消、缺失终点和内容不一致故障。

先修内容：[v0.2.0 消息与模型适配](../02-message-provider/README.md)。

## 运行

从仓库根目录执行，无需 API Key：

```bash
python lessons/03-streaming-cancellation/snapshot/agent.py
```

看到 `pwd` 审批时输入 `y`；输入 `n` 可验证拒绝路径。独立测试：

```bash
python -m unittest discover -s lessons/03-streaming-cancellation/tests -v
```

## 阅读顺序

1. [`snapshot/events.py`](snapshot/events.py)：事件词汇和取消检查点。
2. [`snapshot/providers.py`](snapshot/providers.py)：`Provider.stream()` 合约。
3. [`snapshot/agent.py`](snapshot/agent.py)：流转译、提交点和终止事件。
4. [`architecture.md`](architecture.md)：两条数据管线为何不能混在一起。
5. [`pi-source-map.md`](pi-source-map.md)：与 Pi 固定提交逐项对照。
6. [`lab.md`](lab.md)：亲手制造协议错误与取消。

## 兼容性与边界

- `Provider.complete()` 被 `Provider.stream()` 替代，这是 0.x 教学 API 的刻意演进。
- 当前工程的 `Agent.run()` 仍保留为一次性结果包装器；冻结快照聚焦 `stream()`。
- Python 生成器只有被消费时才运行；调用 `stream()` 本身不会启动后台线程。
- Bash 子进程可被当前工程终止，但孙进程和跨平台进程组隔离尚未解决。
- 事件未持久化，不是 Trace；会话恢复与 Trace 分别留到 v0.9.0、v0.14.0。

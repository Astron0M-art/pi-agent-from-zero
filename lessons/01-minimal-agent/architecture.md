# 架构说明

## 最小闭环

```text
用户 prompt
    │
    ▼
内存 history ──► 单个 model(history)
                      │
            ┌─────────┴─────────┐
            │最终文本            │bash_command
            ▼                    ▼
         返回用户          approve(command)
                                  │
                         ┌────────┴────────┐
                         │拒绝             │允许
                         ▼                 ▼
                    DENIED 结果       subprocess.run
                         └────────┬────────┘
                                  ▼
                           tool 结果写回 history
                                  │
                                  └────► 下一轮 model
```

## 五个架构问题

| 问题 | v0.1.0 的答案 |
|---|---|
| 请求入口 | `Agent.run(prompt)` |
| 权威状态 | `Agent.history`，只存在当前进程内存 |
| 谁决定下一步 | 模型通过 `ModelOutput.bash_command` 决定是否请求工具；宿主决定是否批准和执行 |
| 副作用在哪里 | 只在 `_call_bash()` 内的 `subprocess.run()` |
| 完成证据 | 返回最终文本、外部文件状态、FakeModel 看到的 tool 结果和自动化测试 |

## 正常路径

1. `run()` 把用户消息追加到 history。
2. 模型收到 history 的只读副本并返回 `ModelOutput`。
3. 没有 `bash_command` 时，文本就是最终答案。
4. 有命令时，宿主先调用 `approve()`。
5. 允许后运行 Bash，把 stdout、stderr 和退出码编码成 tool 消息。
6. 下一轮模型看到真实工具结果，再决定继续或结束。

## 错误、拒绝与停止

- 用户拒绝：命令不运行，history 写入 `DENIED`，模型可据此收尾或换方案。
- 非零退出：stderr 与退出码返回模型，而不是伪装成功。
- 超时：进程由 `subprocess` 终止，并返回 `ERROR`。
- 无限循环：超过 `max_turns` 抛出错误；没有静默“完成”。
- 恢复：本版没有持久化，进程退出后 history 丢失。

## 这一抽象为什么足够小

本版没有工具注册表、JSON Schema、事件总线和 Provider 类。唯一模型是一个可调用对象，唯一工具分支就是 Bash。这样读者可以先看到不可再删的控制流，再在后续版本中用失败案例驱动抽象，而不是先背框架名词。

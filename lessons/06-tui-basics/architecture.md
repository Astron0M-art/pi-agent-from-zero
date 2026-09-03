# 架构说明：TUI 是事件投影，不是 Agent 大脑

## 数据流

```text
InputBuffer --submit--> prompt --> Agent.stream()
                                  |
                                  v
                              AgentEvent
                                  |
                                  v
TuiState <---------------- reduce_event
   |                              |
   |                              +-- message views
   |                              +-- tool cards
   |                              +-- run status
   v
TuiRenderer(width, height) --> deterministic frame
```

## 1. 请求入口

用户先把字符写入 `InputBuffer`，`submit()` 拒绝空白输入并清空缓冲。`TuiApp.frames()` 将 prompt 交给已有的 `Agent.stream()`；TUI 不直接调用模型或工具。

## 2. 权威状态

- 模型可见上下文：`Agent.messages`；
- 运行时事实：有顺序的 `AgentEvent`；
- 当前显示投影：`TuiState`；
- 输入草稿：`InputBuffer`；
- 文件与命令结果：工具返回的 `ToolResultMessage`。

`MessageView` 和 `ToolCard` 只服务显示，不能回填模型。未来恢复 Session 时，应从持久事件/消息重建视图，而不是序列化终端帧。

## 3. 谁决定下一步

模型仍决定是否调用工具；Agent 决定事件与预算；工具宿主决定校验和副作用；Reducer 只能决定“如何显示已经发生的事实”。界面不能把一个 running 卡片擅自改成 succeeded。

## 4. 副作用在哪里

Reducer 和 Renderer 都是纯内存计算。真实副作用仍只发生在 v0.5 的工具层。CLI 最后 `print()` 一帧是显示副作用，不改变 Agent 任务结果。

## 5. 错误、取消与恢复

工具错误先把对应卡片标为 `failed`，Agent 若仍能修正可继续运行；终止性的 `AgentFailed` 把状态栏设为 `failed` 并保留已有消息和卡片。这样部分输出不会在失败时消失。

本版不持久化 `TuiState`。进程退出后无法恢复；这是 v0.9 的范围。

## 6. 为什么使用 Reducer

直接在每个事件回调里修改多个组件，容易产生“文字更新了、状态栏没更新”的分裂状态。Reducer 对每个旧状态和事件只返回一个新状态，测试可以逐事件断言，也能回放同一事件序列得到相同结果。

## 五个必答问题

1. **上一版失败在哪里？** 运行能力存在，但输出是零散日志，没有稳定、可测试的交互视图。
2. **最小新抽象是什么？** `AgentEvent -> TuiState` 的纯归约器。
3. **谁决定下一步？** 模型与 Agent 决定任务；TUI 只投影事实。
4. **哪些副作用需要权限和审计？** 仍是 write/edit/bash；显示本身不授予权限。
5. **什么证明完成？** 事件序列测试、固定帧尺寸、真实工具调用卡片和模型/UI 状态隔离断言。

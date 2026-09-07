# v0.6.0：TUI 状态与文本帧渲染基础

前五版的 Agent 已经能完成真实工具调用，但用户只能看见散落的 `print()` 输出：流式文本、工具状态、输入和失败原因没有统一视图。更严重的是，如果直接拿模型消息当界面状态，显示细节会污染模型上下文，未来也无法独立恢复或重绘 UI。

本版在 v0.5 的多轮 Coding Agent 外增加事件驱动的 TUI 状态与文本帧渲染教学内核：行式输入循环、单行输入区状态、消息流、工具执行卡片、固定状态栏和有限视口。它不依赖付费模型或第三方终端库；渲染器自身不生成 ANSI，并把不可信内容中的终端控制字符显示成转义文本，因而每一帧都可以确定性测试。它仍不是 raw mode、逐键编辑和差分重绘的完整 TUI。

## 学习目标

- 把 `AgentEvent` 看作运行时事实，把 `TuiState` 看作可重建的显示投影；
- 用纯函数 `reduce_event(state, event)` 处理流式文本与工具生命周期；
- 理解输入缓冲、消息区、工具卡片和状态栏各自的权威边界；
- 在固定逻辑宽高下保留最新信息，同时始终显示输入区与状态栏；
- 用 FakeModel 验证完整 UI 链路，而不是截图后凭肉眼判断。

先修：[`v0.5.0 Coding Tools`](../05-coding-tools/README.md)。

## 5 分钟运行

要求 Python 3.11 或更高版本。先按仓库首页创建 `.venv`，再在仓库根目录执行：

```bash
.venv/bin/python lessons/06-tui-basics/snapshot/tui.py
.venv/bin/python -m unittest discover -s lessons/06-tui-basics/tests -v
```

第一条命令会进入持续输入循环。依次输入普通文字、`/read README.md`、`/bash pwd`、`y` 和 `/exit`，可以看到每一轮最终的 18 行文本帧；Unicode 字符实际占用的终端显示列可能更多。第二条命令应显示 7 个测试全部通过。

## 阅读顺序

1. [`architecture.md`](architecture.md)：事件如何变成显示状态；
2. [`snapshot/tui.py`](snapshot/tui.py)：输入、Reducer、Renderer、App 四层；
3. [`pi-source-map.md`](pi-source-map.md)：回到 Pi 的组件接口与 InteractiveMode；
4. [`lab.md`](lab.md)：流式、失败和窄视口实验；
5. [`exercises/README.md`](exercises/README.md)：增加光标移动与工具卡片折叠。

## 最小新增抽象

- `InputBuffer`：不可变的单行文本和光标；
- `TuiState`：消息、工具卡片、输入与运行状态的显示投影；
- `reduce_event`：唯一状态转移入口；
- `TuiRenderer`：按 Python 字符数预算固定逻辑宽高的纯文本帧；
- `TuiApp`：逐次提交 prompt，把 Agent 事件渲染成帧，并在轮次间保留状态。

## 完成证据

- 流式 `hel` + `lo` 最终只显示一个 `hello`，不会重复；
- 工具开始、成功和失败状态均由同一调用 ID 更新；
- 视口溢出时隐藏旧显示行，但输入区和状态栏始终存在；
- TUI 的 `MessageView` 从未进入 `Agent.messages`；
- 消息、状态和工具输出中的 ESC/BEL 等终端控制字符只会以可见转义文本出现；
- 完整 UI 链路测试使用 FakeModel 和临时目录；累计测试还覆盖多轮、Bash 审批以及 write → read → edit → grep 组合路径。

## 本版不解决

- Raw mode、键盘事件解析、鼠标、颜色、IME 与差分重绘；
- Markdown、图片、可展开工具详情和 Unicode 显示列精确计算；
- 运行中插话、follow-up、abort 与队列（v0.7.0）；
- Session 恢复后重建 UI（v0.9.0）。

因此它是可验证的 TUI 状态内核，不是 Pi 完整终端界面的 Python 移植。

# 累计能力矩阵

本表描述主分支中每个 lesson 的可观察能力。勾选表示该阶段的独立入口可以实际运行该能力，不只是 Roadmap 中出现过名称。

| 能力 | v0.1 | v0.2 | v0.3 | v0.4 | v0.5 | v0.6 / 当前 src |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 无参数终端启动与多轮内存上下文 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Bash 与逐次 `y` / `yes` 审批 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Message、ToolCall ID 与 Provider 边界 |  | ✓ | ✓ | ✓ | ✓ | ✓ |
| 流式事件、取消与超时协议 |  |  | ✓ | ✓ | ✓ | ✓ |
| Tool Registry、Schema 与双重预算 |  |  |  | ✓ | ✓ | ✓ |
| read / write / edit / grep 与项目路径校验 |  |  |  |  | ✓ | ✓ |
| TUI 状态、文本帧与工具卡片 |  |  |  |  |  | ✓ |

## 可执行证据

- `tests/test_cumulative_repl.py` 对六个阶段运行同一份终端合同，并从 v0.5 起组合 write、read、edit、grep。
- `tests/test_tui.py` 对安装后的 `pi-agent-zero` 组合多轮对话、Bash 审批、Coding Tools、事件归约与文本帧。
- `scripts/run_lesson_tests.py` 在隔离进程中运行每个 lesson 自己的正常、边界与失败路径测试。

所有入口使用离线确定性 Provider，因此可验证的是协议、控制流和副作用，不是自然语言回答质量。v0.6 的“交互”仍是行式 `input()` 循环；raw mode、逐键编辑、IME 和差分重绘尚未实现。

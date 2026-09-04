# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

## [0.6.1] - 2026-09-05

### Changed

- 将首页和课程索引中的 v0.6 能力限定为 TUI 状态与确定性文本帧渲染，明确它不是完整交互式终端。
- 移除已经失效的固定发版节奏，并披露 Codex 自动维护与三轮上下文隔离 AI 审计的边界。
- CI 在 Python 3.11 和 3.12 下枚举每个冻结 lesson，要求发现测试后再以隔离进程运行，并为测试任务设置超时；源码包也携带课程材料并在构建后复验。
- 移除公开文档中的本机绝对路径，并让源码包携带英文入口、Changelog 与引用元数据。

## [0.6.0] - 2026-09-04

### Added

- 增加不可变 `InputBuffer`、显示时间线、`ToolCard`、`TuiState` 和纯函数事件归约器。
- 增加固定宽高、无 ANSI 的确定性 `TuiRenderer`，在视口溢出时保留最新内容、输入区和状态栏。
- 增加一次一问的 `TuiApp`，把输入提交、Agent 事件流和逐帧渲染连接起来；包入口改为离线 TUI 演示。
- 增加 `06-tui-basics` 独立冻结快照、中文讲义、架构说明、Pi 源码映射、实验、练习、答案和人工事件样例。
- 增加离线 FakeModel 测试，覆盖输入编辑、流式文本去重、时间顺序、工具成功/失败卡片、终止失败、视口预算和模型/UI 状态隔离。

### Changed

- CLI 从日志式工具演示演进为固定尺寸终端帧，消息与工具卡片按真实事件顺序显示。
- 当前包版本升级到 `0.6.0`；旧版本继续由各自冻结快照保留。

## [0.5.0] - 2026-09-02

### Added

- 增加共享 `ProjectWorkspace` 的 `read`、`write`、`edit` 与字面 `grep`，并与现有 `bash` 组成稳定的五工具集合。
- 增加项目根路径约束，拒绝绝对路径、父目录逃逸和已存在的符号链接逃逸。
- 增加 `OutputLimits` 和 Registry 级统一输出截断，限制每个成功工具结果进入模型上下文的字符数与行数。
- 增加 `05-coding-tools` 独立冻结快照、中文讲义、架构说明、Pi 源码映射、实验、练习、答案和人工协议样例。
- 增加离线 FakeModel 与临时目录测试，覆盖读取、写入审批、唯一精确编辑、搜索预算、路径边界、无副作用失败和结果截断。

### Changed

- 离线 CLI 演示从审批执行 `pwd` 演进为用五工具 Registry 读取项目 README。
- 当前包版本升级到 `0.5.0`；v0.4.0 继续由冻结快照保留。

## [0.4.0] - 2026-08-29

### Added

- 增加模型可见 `ToolDefinition`、不可变 Schema 副本和工具名称/Schema 声明校验。
- 增加 `ToolRegistry`，统一工具查找、参数验证、执行、异常归一化和 ToolResult 调用 ID 关联。
- 增加独立的工具调用预算，与模型轮次预算共同阻止失控循环和额外副作用。
- 增加 `04-tool-runtime` 独立冻结快照、中文讲义、架构说明、Pi 源码映射、实验、练习、答案和人工轨迹。
- 增加离线 FakeModel 与工具运行时测试，覆盖正常调用、错误 Schema、错误参数、未知/重复工具、执行异常、审批、取消和预算阻断。

### Changed

- `ModelRequest` 从工具名称元组演进为完整工具定义元组。
- Bash 参数校验与执行从 Agent 主循环迁移到可注入 Registry；Agent 只负责编排事件和预算。

## [0.3.0] - 2026-08-27

### Added

- 增加 Provider 流事件与 Agent 生命周期事件，支持增量文本、工具开始/完成和单一终止事件。
- 增加协作式 `CancellationToken`、整轮截止时间，以及可响应取消的 Bash 子进程轮询。
- 增加 `03-streaming-cancellation` 独立冻结快照、中文讲义、Pi 源码映射、实验、故障注入和人工事件样例。
- 增加离线 FakeModel 测试，覆盖半流取消、零秒截止、Provider 失败、协议不一致、命令超时和循环预算。

### Changed

- Provider 边界从 `complete(ModelRequest)` 演进为 `stream(ModelRequest, CancellationToken)`。
- `Agent.stream()` 成为可观察入口；`Agent.run()` 保留为返回最终文本或抛出带失败类型异常的兼容包装器。

## [0.2.0] - 2026-08-25

### Added

- 增加统一 `Message` 联合类型：User、Assistant、ToolResult 与结构化 ToolCall。
- 增加 `Provider.complete(ModelRequest)` 边界和可脚本化、可记录请求的离线 FakeModel。
- 增加 `02-message-provider` 独立冻结快照、架构讲义、Pi 源码映射、Provider Adapter 实验与故障注入。
- 增加消息不可变、请求适配、调用 ID 关联、未知工具与脚本耗尽测试。

### Changed

- 当前 Agent 从字符串字典 history 演进为类型化模型上下文，并通过 Provider 获取 AssistantMessage。
- CLI 演示和包公开 API 更新到 v0.2.0，v0.1.0 继续由冻结快照保留。

## [0.1.0] - 2026-08-24

### Added

- 交付约 100 行的最小 Agent：单模型、单 Bash 工具、执行前审批和循环预算。
- 增加独立可运行的 `01-minimal-agent` 冻结快照、中文讲义、架构说明、Pi 源码映射、实验、练习、参考答案和人工轨迹。
- 增加离线 FakeModel 测试，覆盖直接回答、获批执行、拒绝、非零退出和无限工具循环。
- 增加 `pi-agent-zero` 命令行离线演示。

### Changed

- 项目状态从初始化更新为首个可运行教学版本。

## [0.0.0] - 2026-08-22

### Added

- 初始化标准开源项目骨架。
- 定义一个月、15 个教学版本的路线。
- 增加完整英文 README、中文优先语言策略、CODEOWNERS 和引用信息。

### Changed

- 明确项目作者和主要维护者为 Astron_ma（GitHub：`Astron0M-art`）。

[Unreleased]: https://github.com/Astron0M-art/pi-agent-from-zero/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/Astron0M-art/pi-agent-from-zero/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.6.0
[0.5.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.5.0
[0.4.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.4.0
[0.3.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.3.0
[0.2.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.2.0
[0.1.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.1.0
[0.0.0]: https://github.com/Astron0M-art/pi-agent-from-zero/commits/5d06d3a917ed2f304722eb6ce3176f35c1ca1b93

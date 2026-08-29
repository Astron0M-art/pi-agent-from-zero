# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

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

[Unreleased]: https://github.com/Astron0M-art/pi-agent-from-zero/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.4.0
[0.3.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.3.0
[0.2.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.2.0
[0.1.0]: https://github.com/Astron0M-art/pi-agent-from-zero/releases/tag/v0.1.0
[0.0.0]: https://github.com/Astron0M-art/pi-agent-from-zero/commits/5d06d3a917ed2f304722eb6ce3176f35c1ca1b93

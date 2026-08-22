# Roadmap

## 发布节奏

计划每两天发布一个教学版本，一个月形成 15 个版本。质量门禁优先于日历：代码、讲义或测试不完整时，不发布空版本。

| 版本 | 主题 | 核心产物 |
|---|---|---|
| `v0.1.0` | 约 100 行最小 Agent | 单模型、单 Bash Tool、审批、最小循环 |
| `v0.2.0` | 消息与模型适配 | 统一 Message、Provider 接口、FakeModel |
| `v0.3.0` | 流式事件与取消 | Event Stream、增量输出、超时、取消 |
| `v0.4.0` | 工具运行时 | Registry、Schema 校验、ToolResult、循环预算 |
| `v0.5.0` | Coding Tools | read、write、edit、bash、grep、输出截断 |
| `v0.6.0` | TUI 基础 | 输入区、消息流、工具卡片、状态栏 |
| `v0.7.0` | Steering 与队列 | 工作中插话、follow-up、abort、消息队列 |
| `v0.8.0` | 权限与信任 | allow/ask/deny、路径边界、项目 trust、审计 |
| `v0.9.0` | Session 持久化 | JSONL、Session identity、恢复、迁移 |
| `v0.10.0` | 分支与 Compaction | Entry Tree、branch、摘要、Context 投影 |
| `v0.11.0` | MCP | stdio client、工具发现、命名空间、断线处理 |
| `v0.12.0` | Skills 与上下文 | SKILL.md、按需加载、作用域、Prompt 预算 |
| `v0.13.0` | Extensions | Hook、动态工具、命令扩展、资源重载 |
| `v0.14.0` | Trace 与回放 | 统一事件格式、JSONL Trace、确定性回放 |
| `v1.0.0` | Evals 与开源发布 | Golden Set、行为评测、基线对比、完整文档 |

## 每版必须回答的问题

1. 上一版具体失败在哪里？
2. 本版新增的最小抽象是什么？
3. 谁决定下一步，代码还是模型？
4. 哪些副作用需要权限和审计？
5. 用什么测试证明本版完成？

## 暂不进入 v1.0 的范围

- 垂类求职或招聘应用
- 生产级多租户服务
- 跨平台强隔离沙箱
- 完整 IDE 或 Web IDE
- 为追求功能数量而加入的伪 Multi-Agent

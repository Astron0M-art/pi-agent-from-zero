# Security Policy

## Supported versions

在 `v1.0.0` 之前，仅最新教学版本接受安全修复。冻结课程快照中的安全问题会通过说明和测试标注，避免静默改写历史。

## Reporting

请优先使用 GitHub Private Vulnerability Reporting 或其他私密渠道报告漏洞，不要在公开 Issue 中粘贴：

- API Key、Token 或 Cookie
- 未脱敏的 Session、Trace 或提示词
- 可直接利用的破坏性命令
- 包含个人信息的本地路径或数据

报告应包含受影响版本、复现条件、可能影响和建议修复。

## Educational boundary

本项目用于教学，不应被视为操作系统级沙箱。权限策略、路径校验和命令过滤只能减少风险，不能替代容器、虚拟机或成熟的系统隔离方案。

# Pi Agent from Zero

[简体中文](README.md) | [English](README_EN.md)

一个中文优先、源码对照、可运行的本地 Coding Agent 教学项目。

本项目从约 100 行 Python Agent 出发，以两天一个教学版本的节奏，逐步加入流式事件、工具系统、TUI、权限控制、会话恢复、MCP、Skills、扩展机制、Trace 回放与评测。

> 本项目受 [earendil-works/pi](https://github.com/earendil-works/pi) 启发，但不是 Pi 官方项目，也不是 Pi 的 Python 移植版。

## 项目状态

当前版本：[`v0.6.0` TUI 基础](lessons/06-tui-basics/README.md)。新增事件驱动的输入区、消息时间线、工具卡片、固定状态栏和有限视口，并保持显示状态与模型上下文分离。

## 5 分钟跑通最新版本

无需 API Key。在仓库根目录执行：

```bash
python lessons/06-tui-basics/snapshot/tui.py
```

演示会用离线 FakeModel 搜索仓库 README，并渲染一块固定尺寸的最终终端帧，不需要 API Key，也不会修改仓库。冻结快照的独立测试：

```bash
python -m unittest discover -s lessons/06-tui-basics/tests -v
```

想从最小循环开始，请按顺序进入 [`lessons/`](lessons/README.md)；旧版本冻结快照不会被最新实现覆盖。

## 教学原则

- 每一版都能独立运行，不要求先理解最终工程。
- 每项能力都对应真实 Pi 源码位置，并明确相同点与简化点。
- 每一版都有实验、故障注入、测试和理解检验。
- 先证明行为正确，再增加功能和抽象。
- 不把 MCP 当成权限系统，不把角色提示词当成 Multi-Agent。

## 计划中的学习路径

```text
100 行 Agent
→ 消息与模型适配
→ 流式事件和取消
→ 工具运行时
→ Coding Tools
→ TUI
→ Steering 与队列
→ 权限和项目信任
→ Session 与恢复
→ 分支和 Compaction
→ MCP
→ Skills
→ Extensions
→ Trace 回放
→ Evals 与 v1.0
```

完整计划见 [ROADMAP.md](ROADMAP.md)，每个版本的交付标准见 [docs/teaching-contract.md](docs/teaching-contract.md)。

## 面向中文世界

中文是本项目的主要教学语言和内容事实源。公共 API、代码标识符与协议字段保持英文，Issue 和 Pull Request 同时接受中文与英文。详细约定见 [语言策略](docs/language-policy.md)。

## 仓库结构

```text
pi-agent-from-zero/
├── lessons/                 # 每一版的冻结教学快照
├── src/pi_agent_from_zero/  # 当前最新实现
├── tests/                   # 当前版本的自动化测试
├── docs/                    # 架构、源码映射和教学规范
├── ROADMAP.md
└── CHANGELOG.md
```

## 本地开发

要求 Python 3.11 或更高版本。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
mypy src
pytest
python -m build
```

## 开源协作

- 贡献方式：[CONTRIBUTING.md](CONTRIBUTING.md)
- 行为准则：[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 安全问题：[SECURITY.md](SECURITY.md)
- 上游基线：[docs/upstream-baseline.md](docs/upstream-baseline.md)

## 作者与维护者

- [Astron_ma](https://github.com/Astron0M-art)（GitHub：`Astron0M-art`）

## License

[MIT](LICENSE)

# Pi Agent from Zero

[简体中文](README.md) | [English](README_EN.md)

一个中文优先、源码对照、可运行的本地 Coding Agent 教学项目。

本项目从约 100 行 Python Agent 出发，按路线逐步加入流式事件、工具系统、终端交互、权限控制、会话恢复、MCP、Skills、扩展机制、Trace 回放与评测。版本成熟后才发布，不以自动检查频率代替质量门禁。

> 本项目受 [earendil-works/pi](https://github.com/earendil-works/pi) 启发，但不是 Pi 官方项目，也不是 Pi 的 Python 移植版。

> **维护透明度：** 本仓库由 Codex 自动维护。候选发布需经过三轮上下文隔离的 AI 审计和公开 CI；AI 审计不等于人工代码审查、安全认证或真实用户反馈。

## 项目状态

当前源码版本：`v0.6.2` 累计交互修正版，教学主题仍对应 [`v0.6.0` TUI 状态与文本帧渲染基础](lessons/06-tui-basics/README.md)。默认 CLI 会持续读取输入，并在同一个 Agent 中保留多轮内存上下文；普通文字由确定性离线 Provider 回显，`/read`、`/grep`、`/write`、`/edit`、`/bash` 会进入真实工具运行时，写、改、执行必须逐次输入 `y` 或 `yes` 才会发生副作用。

显示层会把事件投影为消息时间线、工具卡片、状态栏和有限视口。它已有行式输入循环，但仍**不是**支持 raw mode、逐键编辑、IME 和差分重绘的完整交互式 TUI，也没有接入真实大模型。

## 5 分钟跑通最新版本

要求本机可以执行 `python3.11`（也可替换成已确认版本不低于 3.11 的解释器），无需 API Key。在仓库根目录先核对版本并创建项目环境：

```bash
python3.11 --version
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pi-agent-zero
```

启动后可按顺序输入：

```text
你好
/read README.md
/grep "Pi Agent" README.md
/bash pwd
y
/exit
```

这条路径同时验证多轮上下文、Coding Tools、Bash 审批、事件流和 TUI 文本帧。离线 Provider 只用于观察控制流，回答质量不代表真实模型。`/write <path> <content>` 和 `/edit <path> <old> <new>` 也可使用，但会请求审批；read、grep、write、edit 会校验路径是否位于启动时的工作目录，写入还会在审批后重新验证。它不是对恶意并发文件系统变更的完整沙箱。Bash 只把该目录作为初始 cwd，获批命令仍可访问目录外部。原来的一次性 README 搜索演示保留为 `.venv/bin/pi-agent-zero --demo`。

渲染器按 Python 字符数预算名义宽度，不保证 Unicode 文本占用相同数量的终端显示列。冻结快照的独立测试：

```bash
.venv/bin/python -m unittest discover -s lessons/06-tui-basics/tests -v
```

想从最小循环开始，请按顺序进入 [`lessons/`](lessons/README.md)。主分支中的课程快照经过累计合同修正；已发布 tag 保持不变，可用于核对当时的原始状态。

## 教学原则

- 每一版都能独立运行，并在上一版终端体验上增加一个主要概念。
- 每项能力都对应真实 Pi 源码位置，并明确相同点与简化点。
- 每一版都有实验、故障注入、测试和理解检验。
- 先证明行为正确，再增加功能和抽象。
- 不把 MCP 当成权限系统，不把角色提示词当成 Multi-Agent。

版本能力是否真正累计，以[能力矩阵](docs/capability-matrix.md)及跨版本端到端测试为准，不以 Roadmap 或功能名称代替运行证据。

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
python3.11 -m venv .venv
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

# v0.1.0：约 100 行最小 Agent

这一版只保留 Coding Agent 最小闭环：用户给任务，单个模型决定是回答还是请求 `bash`，副作用经过用户审批，工具结果回到模型，直到模型给出最终文本。

## 学习目标

完成本课后，你应该能解释：

1. Agent 与普通聊天调用的关键差别为什么是“把工具结果送回模型后继续循环”。
2. 模型只能提出 Bash 请求，真正的进程创建由宿主代码完成。
3. 审批必须发生在副作用之前，拒绝结果也必须对模型可见。
4. 为什么循环预算是最小但必要的安全阀。

先修知识只有 Python 函数、列表、字典和 `subprocess` 基础。

## 上一阶段的局限

仓库初始化版只有路线和规范，没有可运行 Agent，因而不能证明任何工具行为。v0.1.0 第一次交付可以离线运行和测试的完整闭环。

## 运行

在仓库根目录执行：

```bash
python lessons/01-minimal-agent/snapshot/agent.py "告诉我当前目录"
```

程序会展示准备执行的 `pwd`。输入 `y` 后，预期看到当前目录；输入 `n` 后，模型会看到 `DENIED`，磁盘不会产生副作用。

独立运行冻结快照的测试：

```bash
python -m unittest discover -s lessons/01-minimal-agent/tests -v
```

安装项目后也可运行当前版本：

```bash
pi-agent-zero "告诉我当前目录"
```

## 阅读顺序

1. 先看 [`snapshot/agent.py`](snapshot/agent.py) 的 `Agent.run()`。
2. 再看 [`architecture.md`](architecture.md)，定位决策权和副作用边界。
3. 用 [`pi-source-map.md`](pi-source-map.md) 对照 Pi，而不是把本课当成 Pi 的 Python 移植。
4. 完成 [`lab.md`](lab.md) 和 [`exercises/README.md`](exercises/README.md)。

## 本版刻意不解决

- 不接入真实 Provider，也没有统一消息协议；这是 v0.2.0。
- 不流式输出、不支持取消；这是 v0.3.0。
- 只有硬编码 Bash，没有 Registry、Schema 和通用 ToolResult；这是 v0.4.0。
- 审批只有“询问”，没有规则、路径边界和项目信任；这是 v0.8.0。
- 历史只在内存中，退出后无法恢复。

因此，这个版本适合教学，不适合在无人值守或不可信目录中运行真实任务。

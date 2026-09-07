# v0.5.0：Coding Tools

上一版已经让模型看见工具 Schema，也能在 Registry 中安全执行工具，但它实际上只会运行 Bash。一个 Coding Agent 若每次读文件、改文件、搜索代码都拼 Shell 命令，很难获得稳定参数、可解释错误和一致的边界。

本版保留已有多轮终端、流式事件、Registry 和 Bash 审批，把同一工具层扩展为 `read`、`write`、`edit`、`bash`、`grep` 五个工具，并在所有成功结果进入模型上下文前执行统一截断。

## 学习目标

完成本课后，你应该能够解释：

- 为什么 Coding Tool 是模型可调用的领域接口，而不只是 Bash 的别名；
- 为什么路径必须先解析到项目根目录，再发生文件副作用；
- 为什么 `edit` 要求旧文本唯一匹配；
- 为什么输出截断既是上下文预算，也是可靠性边界；
- 为什么“限制在项目目录内”还不等于完整权限系统。

先修内容是 [`v0.4.0 工具运行时`](../04-tool-runtime/README.md)。

## 5 分钟运行

在仓库根目录执行：

```bash
python lessons/05-coding-tools/snapshot/agent.py
python -m unittest discover -s lessons/05-coding-tools/tests -v
```

进入终端后可输入 `/read README.md` 或 `/grep "Pi Agent" README.md` 验证只读路径；输入 `/bash pwd`、`/write note.txt hello` 或 `/edit note.txt hello world` 会先请求审批。斜杠命令被确定性离线 Provider 转为结构化 ToolCall，不需要 API Key。输入 `/exit` 退出；测试应显示 7 个用例全部通过。

## 阅读顺序

1. 先读 [`architecture.md`](architecture.md)，理解项目根、Registry 与副作用的关系；
2. 对照 [`snapshot/coding_tools.py`](snapshot/coding_tools.py) 阅读五个工具；
3. 用 [`pi-source-map.md`](pi-source-map.md) 回到固定 Pi 提交；
4. 按 [`lab.md`](lab.md) 完成正常、边界和故障实验；
5. 独立完成 [`exercises/README.md`](exercises/README.md)，再看参考答案。

## 最小新增抽象

`ProjectWorkspace` 负责把模型给出的相对路径限制在项目内。只读工具拒绝绝对路径、`..` 与已存在的符号链接逃逸；写工具在审批后从稳定的项目根目录描述符重新逐级打开父目录，并通过临时文件原子替换目标。`edit` 还会在落盘前重读目标，若审批等待期间内容变化就中止。五个工具共享它，Registry 则共享 `OutputLimits`。

本版故意不加入 allow/ask/deny 规则表、项目 trust 和审计日志；这些属于 v0.8.0。现在的审批仍是宿主注入的布尔函数，`read/grep` 默认只读，`write/edit/bash` 需要审批。

## 本版完成证据

- 当前工程测试覆盖工具顺序、UTF-8 读取、路径与符号链接逃逸、审批期间父目录替换、并发编辑拒绝、唯一编辑、字面搜索、匹配预算和统一截断；
- 根目录累计测试验证同一会话组合 write → read → edit → grep，并继续保留 Bash 审批；
- 外部结果通过临时目录中的真实文件内容验证，不接受模型自报“已经修改”；
- 讲义命令可离线执行。

## 本版不解决

- 图片、二进制文件、行号分页和大文件流式读取；
- 正则、glob、`.gitignore` 与 ripgrep 的完整行为；
- 跨进程事务、并发文件变更队列和 diff 渲染；
- 跨平台强隔离沙箱；
- 细粒度权限、信任与审计。

这些限制不是 Pi 的限制，而是本教学快照为了突出最小概念作出的选择。

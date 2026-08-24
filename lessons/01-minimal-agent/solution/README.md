# 参考答案

核心不是写一个越来越长的危险命令黑名单，而是把策略留在 Agent 外部：

```python
import shlex


def read_only_approval(command: str) -> bool:
    if any(token in command for token in (";", "&&", "||", "|", ">", "<", "\n")):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return bool(parts) and parts[0] in {"pwd", "ls"}
```

1. 模型提出 Bash 意图，`approve()` 决定是否放行，`subprocess.run()` 才创建进程。
2. 拒绝进入 history，模型才能知道动作没有发生，避免基于虚假世界状态继续推理。
3. `max_turns` 限制模型—工具往返次数，但不限制单条命令的权限、输出体积或资源占用。
4. history 没有稳定 ID、磁盘格式、原子写入和版本迁移，进程结束即丢失。
5. 审批可能被误点、策略可能误判；获批 Bash 仍继承当前用户权限。真正隔离需要更强的执行边界。

即使这个答案通过练习测试，也不要把它作为安全产品使用；v0.8.0 才会系统讨论 allow/ask/deny、路径边界、项目 trust 和审计。

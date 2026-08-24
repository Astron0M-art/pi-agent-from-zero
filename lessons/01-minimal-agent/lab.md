# 实验手册

所有实验默认使用离线确定性模型，不需要 API Key。

## 实验 1：正常任务

运行：

```bash
python lessons/01-minimal-agent/snapshot/agent.py "告诉我当前目录"
```

批准 `pwd` 后，记录三次状态变化：用户消息、助手工具请求、工具结果。回答：如果删除“工具结果写回 history”这一步，模型下一轮缺少什么证据？

## 实验 2：权限边界

再次运行，但对 `pwd` 输入 `n`。

预期：命令不执行；模型收到 `DENIED` 后仍能输出最终文本。拒绝不是异常崩溃，而是一次可观察的工具结果。

## 实验 3：故障注入

在一个临时 Python 文件中导入 `Agent` 和 `ModelOutput`，让 FakeModel 先返回：

```python
ModelOutput("测试失败", "printf boom >&2; exit 7")
```

第二轮打印最后一条 history。验证 stderr 中有 `boom`，并且结果包含退出码 `7`。然后把命令改成 `sleep 2`，把 `timeout_seconds` 设为 `0.01`，验证模型看到超时而不是成功。

## 实验 4：修改代码

完成 [`exercises/README.md`](exercises/README.md) 中的“只读审批器”：只自动允许 `pwd` 和 `ls`，其他命令一律拒绝。不要在 `_call_bash()` 里硬编码命令名单，策略属于宿主注入的 `approve()`。

## 自动验收

```bash
python -m unittest discover -s lessons/01-minimal-agent/tests -v
pytest -q
```

验收关注外部结果：获批命令确实运行、被拒命令没有创建文件、非零退出对模型可见、循环预算确实终止。模型自称“已经完成”不算证据。

## 理解检验

1. 谁决定“想调用 Bash”，谁决定“真的创建进程”？
2. 为什么拒绝也要进入 history？
3. `max_turns` 防住了什么，没防住什么？
4. 当前 history 为什么不能用于会话恢复？
5. 仅有审批为什么仍不等于安全沙箱？

参考答案见 [`solution/README.md`](solution/README.md)。

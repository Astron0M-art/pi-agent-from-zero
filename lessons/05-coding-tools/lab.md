# 实验：让 Agent 安全地操作一个临时项目

所有会写文件的实验都使用临时目录，不要把命令改成个人资料或密钥所在目录。

## 实验 1：正常链路

运行离线演示与快照测试：

```bash
python lessons/05-coding-tools/snapshot/agent.py
python -m unittest discover -s lessons/05-coding-tools/tests -v
```

观察第一次请求包含五个定义，第二次请求末尾是带相同调用 ID 的 `ToolResultMessage`。

## 实验 2：边界任务——路径逃逸

在测试文件的 `test_write_edit_grep_and_project_boundary` 中，把 `../secret` 依次换成绝对路径和一个指向项目外文件的符号链接。预期工具返回错误，并且项目外文件没有被读取或修改。

思考：为何只检查字符串中是否出现 `..` 不够？答案是符号链接和 `a/../b` 都会改变真实路径，所以应先解析再判断父子关系。

## 实验 3：故障注入——模糊编辑

创建内容为 `x x` 的文件，请求把 `x` 替换成 `y`。预期结果为 `is_error=True`、提示找到两个匹配，磁盘内容仍为 `x x`。

然后把 `old_text` 改成完整的 `x x`。获批后应只发生一次明确替换。

## 实验 4：故障注入——上下文洪水

创建 30 行文本，把 Registry 设置为 `OutputLimits(max_chars=90, max_lines=4)` 后调用 `read`。检查：

- 返回字符串不超过 90 个字符；
- 不超过 4 行；
- 包含 `[truncated: ...]`；
- 磁盘原文件未被截短。

## 实验 5：修改代码

为 `read` 增加可选整数参数 `offset`，从 1 开始计行。要求：

- Schema 拒绝布尔值和非整数；
- 小于 1 或超过文件末尾时返回稳定错误；
- 截断提示能够告诉模型下一次应使用的 offset；
- 新增正常、越界和大文件测试。

这会迫使你区分“工具自己的分页语义”和“Registry 的最终兜底预算”。

## 理解检验

1. 为什么 `read` 不审批，但仍不应该读取项目外文件？
2. 为什么参数校验必须早于 `approve()`？
3. `edit` 的唯一匹配保证了什么，又没有保证什么？
4. 为什么 Bash 仍然比四个文件工具危险？
5. 为什么截断后的文本不能覆盖原文件？

参考答案见 [`solution/README.md`](solution/README.md)。

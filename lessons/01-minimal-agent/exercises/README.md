# 练习：注入只读审批器

实现一个 `read_only_approval(command: str) -> bool`，满足：

- 允许 `pwd`。
- 允许不带 shell 运算符的 `ls` 及其参数。
- 拒绝空命令、`rm`、重定向，以及包含 `;`、`&&`、`||`、管道或换行的组合命令。
- 把它作为 `Agent(..., approve=read_only_approval)` 的参数，不修改 Agent 循环。

至少补四个测试：`pwd`、`ls -la`、`ls > files.txt`、`pwd && rm -rf demo`。

思考题：字符串规则为什么只能用于教学，不能升级成真正的命令沙箱？

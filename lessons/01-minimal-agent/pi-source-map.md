# Pi 源码映射

锁定基线：`earendil-works/pi@1e95e16b61f4a561b932df83d58df52589e58635`（package `0.83.0`）。以下链接都固定到该提交。

| 教学概念 | Pi 源码锚点 | 本版保留 | 本版简化 |
|---|---|---|---|
| Agent 循环 | [`runLoop`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/agent-loop.ts#L153-L251) | 模型响应、工具执行、ToolResult 回填、继续/结束 | 不含 streaming、steering、follow-up、取消和事件 |
| 工具执行前拦截 | [`prepareToolCall`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/agent-loop.ts#L603-L663) | 副作用前可以阻止执行 | 用同步 `approve(command)` 代替通用 hook 和参数校验 |
| Bash 工具 | [`createBashToolDefinition`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/core/tools/bash.ts#L316-L495) | 在固定 cwd 中执行命令，收集输出、超时和退出状态 | 不含增量输出、截断、临时文件、abort 和渲染 |
| 工具契约 | [`AgentTool`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/types.ts#L380-L401) | 工具由宿主执行并把结果交还模型 | 只有 Bash 字段，没有 Schema、details 和通用接口 |

## 可以从对照中得出的结论

- Agent 的核心不是“循环调用模型”这么宽泛，而是宿主维护上下文，并把真实工具结果作为下一轮输入。
- 模型提出副作用意图，宿主代码拥有最终执行权。
- 工具失败也是协议的一部分，必须回到上下文中。

## 不能从教学版推导的结论

- 不能认为 Pi 只支持串行、单工具或同步审批。
- 不能认为 `ModelOutput`、history 字典或错误字符串就是 Pi 的公开协议。
- 不能认为 Bash 审批等价于沙箱；v0.1.0 没有路径隔离和细粒度策略。
- 不能用本版的约 100 行规模估算生产 Agent 的复杂度。

本地参考仓库可能有个人未提交改动；本课只依据上面的固定公开提交，不依赖本地状态。

# Pi 源码映射

锁定基线：`earendil-works/pi@1e95e16b61f4a561b932df83d58df52589e58635`（package `0.83.0`）。

| 教学概念 | Pi 源码锚点 | 本版保留 | 本版简化 |
|---|---|---|---|
| 模型可见 Tool 定义 | [`Tool`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/types.ts#L491-L502) | name、description、parameters 随 Context/请求交给 Provider | 只支持教学 JSON Schema 子集，无 constrainedSampling |
| 参数查找与校验 | [`validateToolCall` / `validateToolArguments`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/src/utils/validation.ts#L263-L316) | 先按名称查找，再按 Schema 验证，错误包含稳定路径 | 不使用 TypeBox/AJV，不做 Convert/coercion 或嵌套结构 |
| Agent Tool 合约 | [`AgentTool` / `AgentToolResult`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/types.ts#L354-L403) | 声明和执行分离，执行接收取消信号，统一结果 | 仅文本结果；无 details、usage、partial update、terminate、executionMode |
| 准备与执行管线 | [`prepareToolCall` / `executePreparedToolCall`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/agent-loop.ts#L600-L707) | 未知工具、校验、执行异常均归一化；执行前检查信号 | 无 before/after hook、参数兼容 shim 和异步批次 |
| ToolResult 归一化 | [`createErrorToolResult` / `createToolResultMessage`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/agent-loop.ts#L756-L786) | Registry 统一补调用 ID、工具名、内容和错误标记 | 无多模态内容、details、usage、addedToolNames、timestamp |
| Schema 失败测试 | [`validation.test.ts`](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/ai/test/validation.test.ts#L149-L163) | 错误参数必须被拒绝 | 教学测试另外验证 handler 与外部副作用均未发生 |

## 可以得出的结论

- 工具 Schema 同时服务模型能力描述和宿主执行前验证，不能只写在 Prompt 中。
- ToolCall 是不可信意图；ToolResult 才是宿主执行后可回填的事实。
- 新增工具应通过 Registry 注入，而不是修改 Agent 主循环。

## 不能得出的结论

- 教学校验器不符合完整 JSON Schema 规范，不能替代生产依赖。
- Registry 中存在工具不代表用户授权它执行；发现、校验和权限是不同边界。
- 顺序工具循环不能推导 Pi 的并行批次、hook、动态工具或完整 AgentToolResult 语义。
- 本课只依据固定公开提交；上游本地工作区保持只读，其未提交内容不作为课程事实。

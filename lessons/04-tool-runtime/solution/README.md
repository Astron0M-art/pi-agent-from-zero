# 参考思路

用 ToolDefinition 声明 `text: string`、`count: integer` 和两个 required 字段；handler 从已验证的 Mapping 中读取参数。当前教学 Schema 子集没有 minimum/maximum，所以范围属于业务校验：返回 `ToolOutcome("count must be between 1 and 5", is_error=True)`。把 Tool 放进 ToolRegistry 后，Agent 无需任何修改。

理解检验答案：

1. Definition 是静态能力合约，结果属于某一次带 ID 的运行事实。
2. 无效参数不应触发权限交互，更不能到达副作用代码。
3. Registry 必须从原始 ToolCall 统一补齐可信的调用 ID、工具名和错误格式。
4. 前者限制模型—工具往返，后者限制一次 run 实际调度的副作用数量。
5. 注册只表示能力可发现；授权还需要用户策略、路径信任和审计，留到 v0.8.0。

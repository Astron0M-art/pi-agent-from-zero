# 练习：不修改 Agent，注册 repeat 工具

实现一个 `repeat` Tool：

- Schema 必须要求非空字符串 `text` 和整数 `count`，禁止额外字段。
- handler 返回把 `text` 重复 `count` 次的 ToolOutcome。
- `count < 1` 或 `count > 5` 时返回错误结果，不产生异常堆栈。
- 用 FakeModel 请求 `repeat(text="ha", count=3)`，最终答案应能看见 `hahaha`。

至少编写四个测试：正常调用、缺少 count、count 类型错误、超出业务范围。后两类失败分别属于 Schema 边界和 handler 业务边界，不要混为一谈。

加分题：在教学 Schema 校验器中支持 `minimum` / `maximum`，让范围校验从 handler 前移，并解释这种改变的取舍。

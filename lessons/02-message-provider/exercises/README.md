# 练习：实现一个 Provider Adapter

假设外部 SDK 只有这个接口：

```python
class UppercaseSDK:
    def generate(self, items: list[str]) -> dict[str, str]:
        return {"answer_text": items[-1].upper()}
```

实现 `UppercaseProvider`，要求：

- 具有 `provider_id = "uppercase"`。
- 实现 `complete(request: ModelRequest) -> AssistantMessage`。
- 只把 UserMessage 和 ToolResultMessage 的 `content` 交给 SDK。
- 把 `answer_text` 转回 `AssistantMessage`。
- Agent 代码零修改即可使用。

至少测试：用户直答、ToolResult 参与下一轮、空 messages 的明确错误。思考真实 Provider 还需要处理哪些字段和失败？

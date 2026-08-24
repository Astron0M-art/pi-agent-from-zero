# 参考答案

```python
from messages import AssistantMessage, ToolResultMessage, UserMessage
from providers import ModelRequest


class UppercaseProvider:
    provider_id = "uppercase"

    def __init__(self, sdk):
        self.sdk = sdk

    def complete(self, request: ModelRequest) -> AssistantMessage:
        items = [
            message.content
            for message in request.messages
            if isinstance(message, (UserMessage, ToolResultMessage))
        ]
        if not items:
            raise ValueError("no provider-visible input")
        payload = self.sdk.generate(items)
        return AssistantMessage(payload["answer_text"])
```

1. Provider 接收不可变消息快照并返回新消息；直接改 Agent 状态会破坏单一权威和可测试性。
2. 多次同名工具调用可能并存，ID 让每个结果精确对应原请求。
3. 工具名列表没有定义参数 Schema、执行器、错误规范和生命周期，所以不是 Registry。
4. FakeModel 通过真实 Provider 边界驱动完整循环；mock `Agent.run()` 会跳过被测控制流。
5. UI 展示状态、运行事件、持久化元数据和私密认证信息不属于模型可见 messages。

真实 Provider 还需处理认证、模型选择、超时、重试、限流、流式增量、工具 Schema、供应商错误和消息格式兼容；本课不假装几十行适配器已经覆盖这些问题。

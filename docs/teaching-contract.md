# Teaching Contract

每一个发布版本都必须提供完整教学闭环。

## Required lesson structure

```text
lessons/NN-topic/
├── README.md
├── architecture.md
├── pi-source-map.md
├── lab.md
├── exercises/
├── solution/
├── snapshot/
├── tests/
└── traces/
```

## Required content

### README

- 本版目标和先修知识
- 上一版的具体局限
- 运行方式和预期输出
- 本版不解决的问题

### Architecture

- 请求入口
- 权威状态
- 谁决定下一步
- 副作用位置
- 完成证据
- 错误、取消和恢复路径

### Pi source map

- 对应的 Pi 文件、符号和测试
- 教学版保留了什么
- 教学版简化或改变了什么
- 哪些结论不能由教学版推导

### Lab

- 一个正常任务
- 一个边界任务
- 一个故障注入
- 一个需要修改代码的练习
- 理解检验和参考答案

### Tests

- 默认不调用真实付费模型
- 覆盖正常、边界、权限和失败路径
- 验证外部结果，不接受模型自报“完成”

## Release gate

只有以下条件全部满足才能发布：

- 快照可在干净环境运行
- 自动化测试通过
- 讲义中的命令已实际验证
- Source Map 指向锁定的上游基线
- Changelog 和版本号一致
- 不包含密钥、个人数据和本地生成 Session
- 根目录测试与每一个冻结 lesson 的独立测试都进入公开 CI
- 候选发布经过三轮上下文隔离 AI 审计，并公开说明 AI 审计不等于人工 Review 或安全认证

自动检查机会不构成发布承诺；无法提供可复现缺口或任一门禁失败时，本轮不发布。

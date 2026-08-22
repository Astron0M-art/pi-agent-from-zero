# Contributing

## Contribution types

- 修正代码、测试或讲义中的错误
- 增加可复现的故障案例
- 改善 Pi 源码映射
- 补充跨平台验证
- 提升无真实模型参与的离线测试

## Development workflow

1. 从 `main` 创建短生命周期分支。
2. 一个变更只解决一个明确问题。
3. 同步更新代码、讲义、测试和 Changelog。
4. 运行全部质量检查。
5. 使用 Pull Request 描述教学影响和验证证据。

```bash
ruff format --check .
ruff check .
mypy src
pytest
```

## Commit messages

使用 Conventional Commits：

```text
feat(agent): add minimal tool loop
docs(session): explain entry tree recovery
test(tools): cover malformed arguments
fix(tui): preserve queued input after abort
```

## Teaching changes

改变已有课程结论时，必须说明：

- 原结论为什么不准确
- 对应 Pi 源码证据
- 哪些版本和练习受到影响
- 是否需要迁移已有 Trace 或测试数据

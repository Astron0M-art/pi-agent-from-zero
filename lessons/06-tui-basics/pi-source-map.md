# Pi 源码映射

固定上游基线：[`1e95e16b61f4a561b932df83d58df52589e58635`](https://github.com/earendil-works/pi/tree/1e95e16b61f4a561b932df83d58df52589e58635)。本课只读取该提交，不使用上游工作区的未提交内容。

| 概念 | Pi 源码锚点 | 教学版对应 | 保留与简化 |
|---|---|---|---|
| Component 与 Container | [`packages/tui/src/tui.ts` L20-L47, L208-L245](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/tui/src/tui.ts#L20) | `TuiRenderer` 的行组合 | 保留“给定宽度渲染为行”；省略组件树缓存、焦点、Overlay 与差分重绘。 |
| 输入编辑器 | [`editor.ts` L270-L330, L482-L603](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/tui/src/components/editor.ts#L270) | `InputBuffer` | 保留文本、光标、提交概念；只实现单行插入/退格，无键位、历史、粘贴、滚动和补全。 |
| 界面区域组装 | [`interactive-mode.ts` L513-L558](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/modes/interactive/interactive-mode.ts#L513) | `TuiState` + `TuiRenderer` | 保留 chat/editor/status/footer 的职责分区；教学版用单个纯文本帧。 |
| 事件更新 UI | [`interactive-mode.ts` L3042-L3236](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/modes/interactive/interactive-mode.ts#L3042) | `reduce_event` | 保留 message start/update/end 与 tool start/update/end 的生命周期映射；教学事件集更小。 |
| 用户/助手消息 | [`user-message.ts` L13-L61](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/modes/interactive/components/user-message.ts#L13), [`assistant-message.ts` L14-L79](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/modes/interactive/components/assistant-message.ts#L14) | `MessageView` | 保留角色化显示与流式更新；省略 Markdown、thinking、主题与错误样式。 |
| 工具卡片 | [`tool-execution.ts` L13-L79, L221-L258](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/modes/interactive/components/tool-execution.ts#L13) | `ToolCard` | 保留调用 ID、参数、运行/成功/失败与结果；省略自定义 renderer、图片和折叠。 |
| Footer 与状态 | [`footer.ts` L46-L84](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/modes/interactive/components/footer.ts#L46), [`status-indicator.ts` L7-L40, L105-L113](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/modes/interactive/components/status-indicator.ts#L7) | `status`, `status_detail` | 保留工作/空闲语义；省略 token、上下文、cwd、git、重试倒计时与 spinner。 |

## 可以得出的结论

- TUI 可以订阅 Agent 生命周期，而无需成为模型上下文；
- 流式文本和工具调用需要不同显示实体；
- 终止失败应该保留部分消息与工具证据；
- 固定视口必须明确旧内容隐藏策略。

## 不能得出的结论

- Pi 使用不可变 Reducer：上游主要通过组件实例和事件回调更新；Reducer 是本课为了显式状态转移采用的教学设计；
- Python 字符长度等于终端显示列宽；CJK、emoji 与 ANSI 需要专门的 visible-width 处理；
- 最终打印一帧等价于 Pi 的差分终端渲染；
- TUI 状态可以替代 Session、Trace 或模型消息。

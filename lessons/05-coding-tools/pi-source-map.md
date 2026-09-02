# Pi 源码映射

上游固定基线：[`1e95e16b61f4a561b932df83d58df52589e58635`](https://github.com/earendil-works/pi/tree/1e95e16b61f4a561b932df83d58df52589e58635)。以下是源码事实，不依赖本地上游工作区的未提交内容。

| 概念 | Pi 源码锚点 | 教学版对应 | 保留与简化 |
|---|---|---|---|
| read Schema 与分页 | [`read.ts` L16-L20, L45-L143](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/harness/tools/read.ts#L16) | `create_read_tool` | 保留独立读工具与有界结果；仅支持完整 UTF-8 文本，不含图片、offset/limit。 |
| write | [`write.ts` L8-L38](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/harness/tools/write.ts#L8) | `create_write_tool` | 保留创建父目录、创建/覆盖；教学版额外加入宿主审批，省略文件变更队列。 |
| 精确 edit | [`edit.ts` L17-L37, L77-L126](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/harness/tools/edit.ts#L17) | `create_edit_tool` | 保留精确匹配；只支持一次唯一替换，不含批量 edits、换行/BOM 保留、diff/patch。 |
| bash | [`bash.ts` L11-L14, L51-L58](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/agent/src/harness/tools/bash.ts#L11) | `create_bash_tool` | 保留命令、cwd、取消与超时；教学审批仍由宿主函数注入。 |
| grep | [`grep.ts` L24-L45, L123-L220](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/core/tools/grep.ts#L24) | `create_grep_tool` | 保留 path:line 和匹配预算；用 Python 字面搜索替代 ripgrep，不支持正则、glob、上下文和 `.gitignore`。 |
| 截断 | [`truncate.ts` L1-L45, L71-L160](https://github.com/earendil-works/pi/blob/1e95e16b61f4a561b932df83d58df52589e58635/packages/coding-agent/src/core/tools/truncate.ts#L1) | `OutputLimits`, `truncate_output` | 保留行与容量双预算及截断元信息；教学版按字符而非 UTF-8 字节，并统一保留头部。 |

## 可以从教学版得出的结论

- 模型需要结构化工具契约，但工具执行权属于宿主；
- 文件工具共享路径解析能减少边界规则漂移；
- 精确编辑的唯一匹配约束可以把歧义变成可恢复错误；
- 工具输出必须在进入下一次模型请求前有界。

## 不能从教学版推导的结论

- Pi 只支持项目相对路径：Pi 的环境抽象允许更丰富的路径与远端执行；
- Pi 的 write/edit 使用相同审批函数：审批是本课程当前宿主策略，不是该文件中的上游事实；
- 教学版 grep 等价于 Pi grep：后者使用 ripgrep，并支持正则、glob、大小写、上下文和限制；
- 字符限制等价于 token 或字节限制；
- 项目根约束已经构成生产级沙箱或权限系统。

## 建议继续阅读的上游测试

- `packages/agent/test/harness/truncate.test.ts`：head/tail 截断的边界；
- `packages/coding-agent/test/truncate-to-width.test.ts`：显示宽度截断；
- 上述工具同目录的 path-utils、file-mutation-queue 与 edit-diff：观察生产实现如何处理环境、并发和差异展示。

# Graft 0.22.0 独立审查

## 范围与独立性

- 代码审查：`PinCodeReview`（reviewer）；安全审查：`PinSecurityReview`（security-reviewer）。两者均只读，未运行测试、构建、格式化、安装或宿主操作；父执行者负责修正和唯一验证环境。
- 基线：`3e13f97b28fa29bcfb1c17d5f1e60b445228ce45`，分支 `feat/graft-pin-0.22.0` 的未提交工作树。
- 审查对象：受管 pin／身份识别、canonical 接线生产与 ownership 消费者、构图策略摘要、launcher 与 0.22.0 固定包的 MCP／hook／Trail notes／telemetry／upkeep 消费链，以及变更测试。
- 安装完成与发布、live 接线切换、原生跨平台验证分别判断。前置门晚于首次修改的顺序偏差不追溯为合规。

## Findings 与闭环

| 发现 | 来源 | 修正 | 验证 |
| --- | --- | --- | --- |
| policy 资产已晋升但摘要仍旧，部署前即 state-conflict | 父执行者复现；代码审查确认消费者一致性 | 更新唯一 `GRAFT_BUILD_POLICY_SHA256`，不放宽摘要检查 | policy-before-fix → policy-after-fix；真实 native-build |
| 生成 dist/bin/graft.js 绑定被既有 cli.js ownership 合同拒绝 | 独立代码审查 | discovery 接受官方 npm bin；持久绑定继续 canonical dist/cli.js，删除不必要候选选择 | binding-before-fix → binding-after-fix；all-binding-contracts 覆盖 Codex／OMP／hook |
| Trail 品牌／HOME／cloud／hook-suppression 可从父环境进入 | 两位独立审查者 | 清除 TRAIL_* 后固定 graft 品牌，并禁用 Trail fetch | 修正探针后的实际 brand RED/GREEN；真实 MCP 六工具及 SessionStart |
| 匹配 stamp 仍可能触发上游自动 Trail 接线迁移 | 两位独立审查者 | 固定 GRAFT_NO_TRAIL_SWITCH=1，不以 no-refresh 或 DNT 代替 | helper + PATH trail 的原生 shouldMoveToTrail RED/GREEN；真实 MCP/hook 前后项目字节保全 |
| 新 notes 消费树可经 symlink／hardlink／特殊文件越界 | 独立安全审查 | 复用 contained + nofollow tree 校验 | notes-boundary-red（5 个失败子场景）→ green；MCP 长连接插入链接后请求拒绝 |
| 只校验 root/.trail 未覆盖祖先 checkout／非 Git 根子 checkout | 独立安全复审 | 按上游实际根发现规则拒绝出界祖先；校验范围内排序／过滤后的子 checkout | effective-note-scope-red → green；包含 node_modules 子 checkout |
| SessionStart 新增 .claude/skills 正文读取未被约束 | 独立安全复审 | 完整父路径 containment 后递归 nofollow，拒绝链接／hardlink／FIFO | skill-parent／skill-file／hardlink／FIFO 回归 |

原始执行结果位于 `reports/acceptance-20261015-181205/`，每轮有同 stem 中文汇总。探针最初的引号错误和未 canonicalize 临时目录错误也保留，未作为产品 RED。

## 最终独立结论

- `PinCodeReview` 最后复审：**No remaining findings / Overall correctness: correct**。确认 canonical 路径、环境边界、有效 notes 根与逐请求验证一致；新 helper 职责单一，复用现有原语，无需进一步抽象。
- `PinSecurityReview` 最后复审：**findings: []**。确认祖先／子 checkout 映射、`.trail`／`.claude/skills` 完整路径验证和启动／逐请求覆盖；此前环境与自动迁移发现均关闭。
- Code Readability Review：通过上述有限变更范围审查。
- Ponytail Review：删除 deployment 候选选择；删除复制 pin/catalog 常量及 ENTRYPOINT 文案断言，保留行为成功／失败和 ownership 测试。无其他可安全删减项。

## 审查建议裁决

- 未采纳“只把 ownership 文件名放宽为 graft.js”：官方 npm wrapper 无条件进入同包 cli.js，保持 canonical 持久合同更小、更安全，不需要扩大旧配置的认领范围。
- 未恢复复制常量／文案测试：改由官方 registry + tarball 对实际安装的 661 个文件逐字节校验，以及真实配置生成／消费链证明；不以同一版本字符串在两处相等冒充运行验证。
- 独立审查的通过只表示已审源码未发现剩余问题。所有运行结论由父执行者实际报告支持，不声称审查者执行过测试，也不替代最终全量结果。

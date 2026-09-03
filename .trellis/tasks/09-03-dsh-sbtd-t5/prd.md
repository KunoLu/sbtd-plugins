# dsh-sbtd T5 sbtd_review

## Goal

五项 book gate 有统一入口 `sbtd_review`：输出规定标题的 Review，按源 skill 状态枚举推进 gate 状态，不替代项目规范 / 测试。

## grill-with-docs

未完整调用 `grill-with-docs`。原因：需求已由 `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` T5 / 3.4 与用户 T5 指令钉死，不涉及新的领域模型或长期术语。

## Constraints

- 宿主钉 `@deepseek-ai/dsh@0.1.1-rc.2`。`inject` 仍为 `tools` + `systemPrompt`。
- 对外 tool 只有 `sbtd_plan` 与 `sbtd_review`。不做 T6。
- `kind` 仅 `legacy` `refactor` `ddd` `ddia` `release`。禁止别名与 skill-id 匹配。
- manuals 只读 1:1：legacy→`book-legacy-change-safety`，refactor→`book-refactoring-pass`，ddd→`book-ddd-distilled-modeling`，ddia→`book-ddia-data-design`，release→`book-release-readiness`。不加载 grill / to-spec / trellis manuals。
- 无 plan：指向 `sbtd_plan`。不假装 passed。不推进任何 gate。
- 通过态映射：`characterized` / `proceed` / `confirmed` / `ready` → `passed`。`needs-*` / `seam-required` / `refactor-first` 保持 `running`。`blocked` → `blocked`。
- 不改 `requirement`。on-demand review 不得升为 required。
- 结论只在返回值；状态写入 `reviewStatus`。
- 标题：Legacy Change Safety Review、Refactoring Review、DDD Boundary Review、DDIA Data Design Review、Release Readiness Review。

## Requirements

- R1. 新增 `packages/dsh-sbtd/src/tools/review.ts`，从 `apply` 按 plan tool 方式注册。复用 `sessionIdFromExec`。用 `import.meta.url` 读包内 manuals 的 `SKILL.md`。
- R2. 测试：`packages/dsh-sbtd/test/t5-review.test.mjs` 与 `packages/dsh-sbtd/features/t5-sbtd-review.feature`。既有 `tools.length` 断言改为仅两个 tool。
- R3. legacy `characterized` 后允许生产 write。required 未 passed 的 refactor write、ddd write、ddia 数据路径、release publish-family bash 仍 deny；普通编辑不因 release 被拦。

## Acceptance criteria

- [ ] `apply` 注册恰好 `sbtd_plan` 与 `sbtd_review`；`inject` 仍为 tools + systemPrompt。
- [ ] 非法 kind / skill-id / 别名被拒绝，不推进 gate。
- [ ] 无 plan 时指向 `sbtd_plan`，不 fake pass。
- [ ] 通过态、running、blocked 映射正确；requirement 不变。
- [ ] 返回含规定标题、requirement、state；结论只在返回值；`reviewStatus` 已存。
- [ ] legacy characterized 后生产 write 放行；其余 required unpassed 门禁仍生效。
- [ ] `packages/dsh-sbtd` lint / typecheck / node test 通过。
- [ ] 一笔 commit，push `feat/dsh-sbtd-t5`，对 main 开 PR，不 merge，不做 T6。

## Out of scope

- T6 `sbtd_clarify` 及任何第三个 `sbtd_*` tool
- 改 hooks 分类规则（本轮只通过 review 推进 gate）
- 发布 / 翻 private / 跟 0.1.2-alpha

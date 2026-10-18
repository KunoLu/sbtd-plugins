---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-pr-b-backend
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "in-progress"
branch: feat/dsh-sbtd-0.2.0-rc.1-pr-b-backend
created_at: '2026-10-18T10:47:15+08:00'
updated_at: '2026-10-18T19:12:35+08:00'
completed_at: null
---

# PR-B 后端：sbtd-task 只读层 + workflow_mode + lessons v2 + Graft

omp 正在实现。范围见 PRD 行 B 与本会话 prompt。首个 commit 须回填 PRD 行 A（#94 / `0499af808ebe38a676668af98979c62355775542` / `2026-10-18T10:25:51+08:00`）。

## Book Gate Plan
| Gate | 触发事实 / 阶段 | 生命周期与结论 |
|---|---|---|
| book-ddd-distilled-modeling | 无新 grill；PRD §2.4 已 confirmed（2026-10-18 00:34），PR-B 四主题与其聚合切分吻合 | not-required（本轮）；不重跑、不冒称 |
| book-ddia-data-design | 命中：插件只读 task.md/.sbtd/active-task.json（所有权 TaskStore）、lessons 落盘写路径变更 | passed：DDIA Data Design Review confirmed（2026-10-18 本会话；无迁移、无新 writer、失败路径 default+note） |
| book-legacy-change-safety | 命中：删两个既有后端、改 lessons/hooks/section/validate 既有行为 | passed：Legacy Change Safety Review characterized（基线 342/342 @ ce8e23a；保留面与豁免面已列明） |
| book-refactoring-pass | 命中：修改既有生产代码 | passed：Refactoring Review proceed / no refactor needed（复用现有注入 seam，仅 StoreLayout 增一个 variant） |
| book-release-readiness | 命中：插件运行时行为变更（hooks/工具契约） | planned：在 npm test + ponytail-review + 独立复核后、完成前执行 |
| TDD | lessons 落点、workflow_mode 解析、Graft 六 reason 为高-risk 行为 | running：先写/改测试再改实现，逐主题红绿 |
| ponytail / ponytail-review | 实现期最小化；check 阶段对非平凡 diff 复核 | planned |

## 本轮证据（2026-10-18 19:12 +08:00，续跑收口）

- **t14-lessons.test.mjs 修复（CRITICAL 阻塞解除）**：整文件迁移到 lessons v2，36 个测试全绿。
  - 删除 `import { writeArtifact } from "../dist/backends/trellis.js"`（模块已删；writeArtifact 白名单行为由 t7-sbtd-task 覆盖）。
  - 身份 fixture 改为 host 种植 `.sbtd/developer`（`name=<name>`）；新增断言插件绝不改写该文件；缺失 → `split-name-unresolved`，非法（`Alice`、`zhang_san`）→ `split-name-invalid`，均不落盘。
  - 落点链覆盖：无存储 → 建 `docs/lessons/` layered（五事件各建 topic）；已有 `docs/lessons/index.md` → layered 追加；已有 `docs/spec/lessons.md` → short append（绝不新建）；legacy flat `docs/lessons.md` 或 `.trellis/lessons/index.md` 存在 → record 返回 `skipped kind=migration-skip`（store 分别 docs/trellis），match/read 仍读旧存储。
  - 事件 `gitnexus-mismatch` → `graft-mismatch`；保留 symlink 逃逸（layered store / flat / legacy trellis index）、R6 消毒、R6b 伪造 end-marker、malformed-marker、跨 name marker 可读、docs-flat topic 回退四例。
- **连带陈旧预期修复**：t5-review 六个 deny 测试注入 `workflowMode: "strict"`（required book gate deny 为 strict-only，hooks R2 Q3 A 设计）；t6-clarify section 断言更新为「完整 docs grill 后所有模式都必须有 DDD 复审通过态」；fu4-host-schema 更新为 draft-only output schema（`ok/mode/artifact/markdown/note/blocked`，无 slug/source）。
- **Graft 六 reason（R2 Q4 A，t9-graft.test.mjs 锁定）**：`launcher-missing`、`version-unsupported`、`call-failed`、`guard-failed`、`graph-missing`、`graph-stale`；词表锁测试 "reason vocabulary lock: exactly six reasons (R2 Q4 A)"，各 reason 有独立测试（launcher-missing×2、version-unsupported + 0.22.0 放行、call-failed×2、guard-failed×2、graph-missing、graph-stale）。
- **验证**：`cd packages/dsh-sbtd && npm test`（tsc 重建 dist + node --test）→ **330 pass / 0 fail** / 330 total。dist 已清建，无残留 trellis/gitnexus 编译产物。
- **已披露既有 lint**：`npm run lint`（biome check src）= 10 errors / 4 warnings / 1 info，为既有状态（本轮只改 test/*.mjs，biome 仅查 src；graft.ts 等格式类告警遗留）。
- 未提交、未推送；PR-C、bump/publish/CHANGELOG、manuals、~/.omp 配置均出范围未动。

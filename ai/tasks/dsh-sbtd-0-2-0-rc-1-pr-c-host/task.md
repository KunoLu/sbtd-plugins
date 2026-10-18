---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-pr-c-host
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "in-progress"
branch: feat/dsh-sbtd-0.2.0-rc.1-pr-c-host
created_at: '2026-10-18T20:35:53+08:00'
updated_at: '2026-10-18T20:35:53+08:00'
completed_at: null
---

# PR-C 宿主适配 + T0

omp 正在实现。范围见 PRD 行 C。

**首个 commit 必须回填 PRD 行 B：**
- PR: #96
- merge SHA: `609766b1d911f1a4597e5ee7117877d2238a548f`
- done time: `2026-10-18T20:35:02+08:00`
- 并将行 B status → done；行 C → in-progress + 本 task 路径

## 范围（锁定）
- V4 `kind:'dsh-sbtd'` 且识别兼容 `'plugin:dsh-sbtd'`
- runPreStep 保留 `startsRequestSeries`
- peerDependencies.dsh 与 engines.dsh 同范围，初始 `>=0.2.0-rc.2 <0.3.0-0`；T0 按锁退回则改 `>=0.2.1-rc.2 <0.3.0-0`
- devDep 精确钉 `@deepseek-ai/dsh@0.2.0-rc.2`（退回时改钉 0.2.1-rc.2）
- CI：`dsh-host-compat.yml` unit-pack 两行 REQUIRED（0.2.0-rc.2 + 0.2.1-rc.2），workflow_dispatch，红即停
- T0 判据：R1 Q6 B（npm 下限 ERESOLVE → 退 range；pnpm add 失败才算 T0 失败；peer 警告只记）；R2 Q1 A 两行矩阵双失败不发
- 不碰：bump/publish/CHANGELOG（PR-D/文档 PR）、手动改 ~/.omp

## Book Gate Plan
| Gate | 触发 | 状态 |
|---|---|---|
| book-legacy-change-safety | 改 hooks/宿主适配既有行为 | planned |
| book-refactoring-pass | 改生产代码 | planned |
| book-release-readiness | 运行时/peer/CI 变更 | planned |
| TDD | kind / startsRequestSeries / peer 范围 | planned |

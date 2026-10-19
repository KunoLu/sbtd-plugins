---
schema_version: 1
id: readme-bilingual-redesign
workflow_mode: strict
mode_source: user
mode_note: User explicitly requested strict mode and a new branch
status: "done"
branch: docs/bilingual-workflow-readme
created_at: '2026-10-06T10:08:15.342738+08:00'
updated_at: "2026-10-06T10:26:09.392476+08:00"
completed_at: "2026-10-06T10:26:09.392476+08:00"
---
# Bilingual SBTD README redesign

## Scope and requirements

User explicitly selected strict mode and a new branch. Rebuild README.md in English with a header link to README.zh.md, using wuyoscar/jev-skill README as an information-design reference. Front-load onboarding and workflow usage with copyable recommended prompts. Cover all catalog skills and core workflow contracts through concise summaries and canonical deep links. Delete README.html and update active consumers; preserve historical records. No runtime changes, global installation, live automation sync, release, commit or push.

## Before development

- Branch: docs/bilingual-workflow-readme; starting worktree clean.
- Base SHA: 8c4f84db6acd23d9e757aa4648632490cf2096d9.
- Full grill-with-docs: not-needed; user specified audience entrypoint, template, language, removal and mode, and source contracts answer content questions. No domain rule changes.
- Research: reference README; canonical catalog, Onboard SKILL/REFERENCE, bundled and external entrypoints, task/validation contracts, active documentation consumers.

## Book Gate Plan

| Reviewer | Objective predicate | Stage | Gate state | Reason |
|---|---|---|---|---|
| book-ddd-distilled-modeling | Full grill or ambiguous domain rules | requirements | not-required | Neither applies; existing terms summarized without change. |
| book-ddia-data-design | Data/schema/migration behavior changes | design | not-required | Documentation only; task helper use does not change persisted-data design. |
| book-legacy-change-safety | Existing runtime behavior bug or unclear/high-risk code change | before edit | not-required | No runtime behavior changes. |
| book-refactoring-pass | Existing production-code edit | before edit | not-required | No production-code edits planned. |
| book-release-readiness | Production runtime/deployment behavior changes | after validation | not-required | No install/deploy/release executed or changed. |

## Design

One public English README and one semantically equivalent Chinese README. Centered header, honest inventory/license badges, shared explicit anchors, early installation and prompts, workflow/mode guide, complete linked catalog, concise safety/verification boundaries, reference map and repository maintenance. Deep operational contracts remain in existing REFERENCE and Skills rather than repeated implementation logs. No separate site or new documentation framework.

## Acceptance and check plan

1. Both Markdown entries render and language links resolve; English is default.
2. Usage appears before conceptual/catalog detail, with prompts for bootstrap/init/check/project-only/upgrade/reset/migration/cleanup/recovery and default/lite/strict daily tasks.
3. All 14 bundled and 19 external entries are represented with working canonical links; mode, authorization and release caveats match source.
4. README.html absent; active maintenance/read consumers point to bilingual Markdown; history preserved.
5. Markdown local paths/fragments and rendered structure checked; safe CLI help exercised, no installation commands executed.
6. Relevant project-native contracts run after edits; independent content/safety and reader review, findings fixed before closure.

## Validation boundaries

Documentation-only: no business .feature (repository forbids it), no API/mobile/full-stack requirement, no production-code readability gate. Browser checks cover locally rendered Markdown, not a published GitHub page. Native/raw local reports and same-stem Chinese summaries remain under ignored reports/. Evidence is developer-local, dirty, local-only and not PR-head or release proof.

## 交付与验收结果

- `README.md`：默认英文入口，409 行，安装第 26 行、使用说明第 76 行；不再使用原 882 行的实施日志式首页。居中标题、语言切换、短导航、提示词、模式说明、完整技能目录与深层参考。
- `README.zh.md`：408 行中文对应入口；章节、命令、关键授权／风险与英文一致。两语言均覆盖 14 bundled／19 external Skills。
- 删除 `README.html`；更新 `sbtd-workflow-onboard/SKILL.md` 的模板排除清单、版本化 automation prompt 的双语读写／维护入口、`docs/lessons.md` 的稳定锚点与 upstream sync runbook。
- `CHANGELOG.md` 顶部未发布文档节记录改造；ignored 本机根 `AGENTS.md` 仅更新两 README 维护路径与 repository 锚点，不同步 HOME 生效文件。
- `tests/test_workflow_contracts.py` 删除与旧首页文案／HTML 结构绑定的过时检查，保留真实安装／catalog／ignore／规则契约；移除无用 HTMLParser 与 os import。未新增生产代码或测试框架。

## 验证与独立复核

| 检查 | 结果 | 本地证据 |
|---|---|---|
| Markdown 解析、本地路径／锚点、双语目录覆盖 | 154 个本地链接、33 个 Skill 在双语中完整覆盖；无错误 | reports/markdown-check-final.json 与同 stem 中文汇总 |
| 实际浏览器 smoke | 英文→中文→英文；使用说明锚点；升级／reset 折叠提示词；桌面与 390px 无文档级横向溢出 | reports/browser-smoke.json、.md、readme-zh-mobile.png |
| 最终原生 workflow contracts | `python -B -m unittest tests.test_workflow_contracts`：44 tests，OK | reports/workflow-contracts-review-final.json 与同 stem 中文汇总 |
| Onboard／Bash 帮助与 Bash 语法 | `onboard.py --help`、`bash install.sh --help`、`bash -n install.sh` 均 exit 0 | reports/onboard-help、installer-help、installer-syntax 的 JSON／MD |
| Ruff | 当前仍 4 项既有诊断，无新增；未宣称 lint 全绿 | reports/lint-baseline.json、.md；保留 python-lint 与 python-lint-default 失败记录 |
| 独立读者与契约复核 | 读者无发现；历史 v1 pin 风险已修正并复核关闭；无剩余可操作发现 | reports/independent-review.json、.md |

原生最终测试在审核修正后重跑。浏览器交互之后仅变更 pin 风险段，最终重新渲染并检查转义和锚点，不冒称再次运行浏览器全流程。预览服务器与浏览器已关闭，本任务临时预览目录已移除，报告保留。

## 跳过、风险与恢复边界

- BDD：skipped，文档信息架构改造，不改变业务行为；仓库禁止 `.feature`。Cross-repo context／API Contract：not-needed；Mock Strategy：none。
- 全仓 runtime suite、原生 Windows／Linux CI、真实安装／升级／迁移／清理：未运行；无生产实现变化，本轮范围为文档消费契约与实际渲染。Playwright／Maestro 业务回归和 SEO 线上审计 not-needed。
- rtk：skipped-for-report；原生命令保存 stdout/stderr/exit code。Ruff 4 项 UP022／PLW1510 已在基线同一文件存在，未借此扩大为无关代码修复。
- Code Readability Review：仅测试删除与 import 清理，保留现有可执行契约，不建立新抽象。Ponytail production-diff gate：not-needed。无新增长期经验，既有验证与来源分层 lesson 已覆盖。
- Evidence Source：developer-local；Source Revision：dirty；Evidence Publication：local-only；完整基线 SHA 见上。不是新 commit／PR head、GitHub 已发布页面或完整 v2 release 的证明。
- 未 stage／commit／push，新增中文文件与任务文件仍为工作区交付；没有 sync、live automation 修改、ENTRYPOINT 版本推进或 HOME 安装。历史 changelog／任务／lesson 引用保留。
- 回退只需恢复本分支的文档／测试改动并移除新增中文入口；没有数据迁移。任务记录与忽略报告为本轮证据，不自动归档或删除。

## 后续发布授权

上述验收与“未提交”状态记录的是工作区交付时点。用户随后明确授权提交本次变更、创建 PR 并合并到 main；合并成功后删除本地及远程开发分支。继续沿用 strict 模式，不扩大为工作流 sync、部署、tag 发布或备份清理。最终提交的 CI 与合并状态以对应 GitHub PR 为准，不将此前 dirty 本地证据改标为精确提交证明。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-06T10:08:16.583731+08:00 | planned | in-progress | Confirmed scope and strict documentation gates; analyzing canonical sources | User request and source/reference inspection |
| 2026-10-06T10:20:24.138026+08:00 | in-progress | checking | Bilingual entrypoints, HTML removal and active documentation consumers implemented | README.md; README.zh.md; CHANGELOG.md; consumer handoff; markdown-check.json |
| 2026-10-06T10:26:09.392476+08:00 | checking | done | All requested bilingual README, HTML removal and strict documentation acceptance conditions completed; inherited lint limits explicitly retained | README.md; README.zh.md; reports/markdown-check-final.json; reports/workflow-contracts-review-final.json; reports/browser-smoke.json; reports/independent-review.json; reports/lint-baseline.json |

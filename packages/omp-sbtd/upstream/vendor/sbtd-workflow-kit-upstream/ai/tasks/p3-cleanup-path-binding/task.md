---
schema_version: 1
id: p3-cleanup-path-binding
workflow_mode: strict
mode_source: user
mode_note: 用户确认采用 strict 修复 P1 prepared 路径绑定与备份完整性缺口
status: "done"
branch: fix/cleanup-prepared-path-binding
created_at: '2026-10-02T16:38:40.658349+08:00'
updated_at: "2026-10-02T18:29:11.815888+08:00"
completed_at: "2026-10-02T18:29:11.815888+08:00"
---
# P3 观察问题：清理 prepared 资源路径绑定

## 目标与授权

修复 P3-OBS-PR105-PATH-BINDING / PR #105 discussion_r4163238244：重封 path/before 不得让 vendor 修改未备份的真实项目文件。用户要求按推荐执行，并明确选择 strict。本任务独立于历史 sbtd-cleanup-expansion；不重绑定或重开旧任务。

范围：vendor prepared 校验及 fresh replay 边界、现有回归与真实隔离 vendor 场景、必要文档和观察问题处置。初始实现阶段不含 commit/push；用户随后明确要求按“提交、创建PR、核验最终提交CI、合并并登记问题关闭”的推荐执行，本轮据此开展集成。真实 HOME/项目清理、全局同步、发布或备份处置仍未授权。P3-01 保持观察中。

## 需求与测试 seam

未完整调用 grill-with-docs：既有 PR 意见、已复现问题和清理合同已明确，无领域歧义；DDD 触发不成立。
测试采用现有公开 prepare_trellis_uninstall / execute_trellis_uninstall seam，以及 fresh/batch cleanup 的现有消费测试；不新增内部实现快照或测试框架。

验收：篡改 path/before 并重算摘要的计划必须在 vendor 启动前拒绝，项目原文、decoy 和 vault 不变；合法计划保留完整备份及成功、失败、重试语义。覆盖项目内/外诱饵、非法相对路径与实际 vendor 隔离场景。

## Book Gate Plan

| Gate | 客观触发 | 阶段 | 状态 |
|---|---|---|---|
| DDD | 未完整 grill；领域词和所有权无歧义 | before-dev | not-required |
| DDIA | 持久 prepared 文档、清理备份及恢复完整性 | before-dev | passed / confirmed：root/relative 是路径权威；拒绝重封替换；不改持久 scope 形状，以执行时路径对照绑定 fresh replay |
| Legacy safety | 已确认既有 P1、删除与备份行为 | before-dev | passed / characterized：公开 execute 回归 1 项/2 subtests 均因未拒绝而红；保留现有备份、失败、重试安全网 |
| Refactoring | 既有生产代码定点修改 | before-dev | passed / proceed：只提取复用路径绑定 seam，执行备份/测量使用已绑定 Path；无无关重构 |
| TDD / BDD | 用户可见拒绝行为；以既有设计文档承载，不新建 .feature | implement | passed：两个诱饵 subtests 红→绿；补非法 relative 回归；设计 §7 与公开执行接口对应 |
| Ponytail / Readability | 保留必要的输入边界，无无关重构 | check | passed：单一绑定 helper 服务真实信任边界；无新依赖/协议；独立复核认定路径重放对照可保留作安全清晰性 |
| 独立安全及回归复核 | 持久迁移与卸载 | check | passed：PathBindingSecurity / PathBindingRegression 无本次范围内发现，原文与中文汇总保留 |
| Project validation | 定点、真实隔离 smoke、全量、静态 | check | passed：最终 full-2 1380 tests / 8 skipped / exit 0，受检源码不变；清理子集79项、实际vendor/基线计划兼容、Ruff/ty通过 |
| Release readiness | 迁移/清理运行时改变 | finish | passed / ready：本仓修复交付及PR106集成已验证；不代表全局同步或v2发布，后续合并证据见下文 |

## 初始证据

基线 f58197608609af894733829e4a9c261b90ff3dbc。P3-01 私有 observation-audit-main-2026_10_02-15_35_23 已复现：prepared 重封接受，scope 未变，隔离实际文件被修改但原件未备份，outcome removed；vendor 边界为既有 FakeRunner，不是 live 卸载。无需重复已确立的问题诊断；新回归按 red→green 取证。

LSP 实查无配置；采用源调用点与现有 contract/tests 影响分析，不声称 LSP 验证通过。

## 设计与影响分析

- `_bound_resource_path` 将资源 relative 经既有严格校验后拼接受检 root，要求封存 path 精确相等；不修复或归一化非法输入。绑定不符使用 invalid-document，非法 relative 保留既有 plan-unsafe。
- execute 在备份及 vendor 启动前比较封存绑定路径与 fresh replay 路径；后续前态复验、备份和结果测量只消费绑定 Path，不再直接用未绑定字符串。
- 不把 path 加进持久 scope fingerprint：那会使既有合法计划失效；保持 schema、摘要算法和封存 scope 形状，改用独立执行时对照。
- 调用者：fresh cleanup 和 batch migration cleanup 共用 vendor adapter；两端保留原确认、完整原件、累计回执与重试规则。原 TaskStore 状态和历史失败不改。
- 单元/故障 probe 用既有 FakeRunner；实际安装的 tl 仅在 disposable 隔离项目验证。LSP 无配置，已用源调用点确认两个消费者。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-02T16:44:49.169549+08:00 | planned | in-progress | 用户选择 strict；需求、DDIA/Legacy/Refactoring before-dev 完成，公开执行接口对抗回归已红 | docs/prd/sbtd-cleanup-expansion-design.md §7; red-path-binding: 1 test, 2 failures, ContractError not raised; private evidence sbtd-p3-path-binding-2q9juski |
| 2026-10-02T17:23:09.522543+08:00 | in-progress | checking | 根因修复、对抗回归、实际 vendor/旧计划兼容 smoke、两路独立复核与纠正环境后的完整 suite 均通过；保持检查态，不关闭 P3-01 | sbtd-p3-path-binding-2q9juski/full-2: Ran 1380 tests, OK (skipped=8), exit 0, source unchanged; review-security/review-regression no findings; corrected-real-vendor-smoke; corrected-baseline-plan-compatibility |
| 2026-10-02T18:29:11.815888+08:00 | checking | done | 用户授权提交/PR/合并并明确授权CI通过后的管理员合并；修复PR106已实际MERGED，合并树与验证head一致 | PR106 head 113a0e9eacbc3a74920144be3b7daabd4ef82086; CI run36993191947 linux-full/macos-bash-installer/windows-powershell-installer success; GitHub review threads 0; merge ed4e65c29f2567c7c83188df9e49e025362a4705 at 2026-10-02T10:26:57Z; local main and origin/main match; P3-01 remains in-progress |

## 验证与交付证据

- 私有证据目录逻辑名：`sbtd-p3-path-binding-2q9juski`；全部原生/raw JSON 与同 stem 中文汇总保留，不随源码发布。最终为 `full-2`，不是首次 `full-1`。
- 原生命令：`/Users/lusonglin/TEMP/sbtd-v2-p1-21-venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`；1380 tests，OK (skipped=8)，709.542s，exit 0；实现/测试/文档10个受检文件前后指纹一致。
- 跳过8项：真实host opt-in 5项、Windows junction/ACL 2项、大小写敏感文件系统1项。不把本机结果当作上述平台或CI通过。
- 首轮全量 `full-1`：1380 tests，45 failures / 98 errors / 8 skipped。默认 ansible-dev-tools Python 缺 tomlkit 且 cryptography 50.0.1 超出声明范围；仅切换到已有合规项目venv，不安装依赖、不改变源码。中间子集因从tests目录启动导致 `No module named 'tests'`，改回仓库根标准discovery后79项通过。失败记录保留。
- `corrected-real-vendor-smoke`：实际tl 0.6.17，攻击计划在任何子进程前 invalid-document，项目与vault不变；合法计划实际卸载，3份原件备份匹配，孤立用户hook及Graft块保留。
- `corrected-baseline-plan-compatibility`：基线提交的旧producer生成并序列化prepared计划，修复后consumer未经重封接受，真实vendor成功且3份备份匹配。仅证明vendor描述符兼容，不豁免migration的runtime lineage门。
- Ruff、ty均通过；Python AST、任务schema/分支、索引及lesson链接通过。两路独立只读复核无范围内发现；未由reviewer重复跑测试。报告命令使用原生runner，`rtk: skipped-for-report`。
- BDD：traceable，中文场景表位于清理设计§7；不生成.feature。API/Web/Mobile功能门：not-needed；README.html仅文案变更，HTML文本解析通过，未做浏览器视觉验证。Mock Strategy：vendor异常分支为既有contract-backed fixture，真实smoke无mock。
- Source ref：`fix/cleanup-prepared-path-binding`；基线SHA：`f58197608609af894733829e4a9c261b90ff3dbc`；Source Revision：dirty；Evidence Source：developer-local；Evidence Publication：local-only。不是main或新PR head验证。

## 文档、状态和恢复边界

- README.md、README.html、REFERENCE、版本化automation prompt补充绑定及兼容性边界；CHANGELOG未发布章节记录修复；设计§7作为长期行为规格。
- Lessons split name：kuno，由本地`.sbtd/developer`经DeveloperStore.resolve确认；`LESSON-20261002-kuno-prepared-resource-binding`写入repository-workflow topic并同步index，未改其他作者块或高频短入口。
- 无剩余本次范围内审查发现。修复PR106已合入main，TaskStore已登记done；P3-01仍in-progress。观察问题按仓库集成范围登记，不把main修复宣称为live已同步或整体验收完成。
- 外部vendor按路径执行，不提供原子文件系统事务；必须单一控制者、维护期间无并发写入。这个既有边界未被此次路径绑定消除。
- 合法prepared格式和现有回执/人工恢复合同不变；未执行真实清理或触碰原始备份，无live写入需要回滚。源码回退会恢复漏洞，不能据此宣称安全。
- 提交前阶段未commit/push；该历史本机验证不冒充新提交CI。本轮已完成授权的PR106提交/推送/合并，详见下文；仍未同步本机Skills/配置、未修改live automation、未签名迁移、未创建tag或发布、未删除备份。

## PR 集成授权

用户在本机修复验证交付后回复「按你推荐的执行」，授权提交/推送修复、创建PR、检查最终提交CI与新增审查意见、合并及状态登记。随后用户明确选择「允许本轮管理员合并」：仅在对应最终提交全部CI通过、无未关闭实质审查意见后豁免一条正式批准要求，覆盖修复PR及必要状态PR，不改仓库保护规则。仍不授权全局同步、真实清理、tag/release或备份处置。

## 已证实的仓库集成

- 修复提交：`113a0e9eacbc3a74920144be3b7daabd4ef82086`；[PR #106](https://github.com/KunoLu/640-skills/pull/106) 于 `2026-10-02T10:26:57Z` 实际MERGED，合并提交 `ed4e65c29f2567c7c83188df9e49e025362a4705`。
- 精确head的[CI run 36993191947](https://github.com/KunoLu/640-skills/actions/runs/36993191947)三项通过：linux-full、macos-bash-installer、windows-powershell-installer；包含Linux大小写敏感路径与Windows junction/ACL专用步骤。真实host opt-in仍不因此视为通过。
- GitHub自动审查已完成；合并前GraphQL核对review threads为0。仓库仍要求1条正式批准，按用户本轮授权使用管理员合并，并以match-head-commit锁定已验证head；没有更改保护规则。
- 提交后本机精确head重新运行vendor模块53项、实际vendor及基线旧计划兼容smoke，全部通过，工作树前后clean。原full-2仍保留为提交前dirty证据；10个受检文件的Git对象字节一致性另行复核。
- 合并后只读确认local main与origin/main均为 `ed4e65c29f2567c7c83188df9e49e025362a4705`，合并树与验证head树同为 `61e95588f93e3a0cb3f5b5b8319174c49aecd719`。没有删除分支。
- TaskStore实际完成事件时间为frontmatter completed_at，等于状态事件中的checking→done；保持任务原分支历史，不重绑定P3-01。此后状态文档独立PR只登记已发生事实，不重新开发或扩大部署权限。
- 私有集成证据：`postcommit-113a0e9.{json,md}`、`pr106-ci-review.{json,md}`；CI来源为GitHub Actions，提交后本机来源仍为developer-local，二者分开。

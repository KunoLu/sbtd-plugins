---
schema_version: 1
id: sbtd-changelog-backfill
workflow_mode: strict
mode_source: user
mode_note: 用户 2026-10-22 22:56 +08:00 在 SBTD 群内确认 CHANGELOG 回填，Lord 记录；本次明确指定 strict、唯一 writer、两个本地提交，不 push/PR/comment/tag/publish/merge。
status: done
branch: docs/changelog-backfill
created_at: '2026-10-23T12:40:50+08:00'
updated_at: '2026-10-23T13:10:17+08:00'
completed_at: '2026-10-23T13:06:30+08:00'
---
# SBTD CHANGELOG backfill

## 目标 / 范围 / 非目标

- 提交 1：仅追加 #116 merge、FINAL 模型计数及标题生成纠正到 `omp-sbtd-offline-cache-smoke/task.md`；只更新 status/updated_at/completed_at 当前值，不改旧事件或历史正文。
- 提交 2：补齐两个包已发布 0.1.0 RC 的双语 CHANGELOG；日期按 npm publish UTC 转 Asia/Shanghai；保留已有英文正文。新增本 strict 记录及 index 一行。
- 不改代码、版本、README、ROADMAP、PRD、全局配置或其他任务；不发布、不推送、不开 PR、不评论、不打 tag、不合并。
- 唯一写入 worktree `/workspace/sbtd-plugins-changelog`，branch `docs/changelog-backfill`，基线 `25d7e83bbc25b6f7d2c5018d7f945376670a2d9a`；入口工作区 clean。`/workspace/KPi` 及编排方于 2026-10-23 只读采集的日志/tarball 仅作只读来源，不入提交。
- 未完整调用 grill-with-docs：用户已明确版本、证据来源、双语镜像及验收，无领域歧义。
- 沿用前任务明确记录的 TaskStore 全库历史 schema blocker，不重跑确认、不调用 lifecycle、不写 active pointer。本记录是用户显式要求的共享文档产物，不宣称 TaskStore 或自动恢复通过。目标父路径已核对无 symlink，旧 task/index 已 tracked，新 task 不被 ignore；不写本地状态、身份或 handoff。
- 旧 offline-cache 任务保持历史 branch `chore/offline-cache-smoke`；本次仅显式授权的历史回填，不重绑定。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T12:40:50+08:00 | planned | in-progress | 用户明确 strict 与两个提交的文档范围；核实根、分支及路径安全 | git status --short --branch；git rev-parse --show-toplevel；路径无 symlink；git ls-files / git check-ignore |
| 2026-10-23T12:50:42+08:00 | in-progress | checking | 双语回填、逐版本证据、原始 npm JSON、模型 SNAPSHOT 与文档 smoke 完成；本地交付不标 done | 四文件 9/9/4/4 个版本日期匹配；原 EN body 保留；提交 1 append-only；全表 Git ranges/counts 与 raw JSON 比对通过；completed_at null |
| 2026-10-23T12:54:37+08:00 | checking | checking | provenance wording fix | 按本次明确纠正，将本分支新增文字中的 PR body、npm JSON、日志/tarball 与 ping 归属改为编排方；保留用户决策归属及基线旧正文 |
| 2026-10-23T13:06:30+08:00 | checking | done | 回填 PR #117 squash-merge；Lord 合并 | main merge SHA 46680a5f6403d9c6032e1dd6a3d2cb49cb2ff842；merge commit %cI 与 GitHub mergedAt 均为 2026-10-23T13:06:30+08:00；远程 docs/changelog-backfill 已删除，本地分支及 worktree /workspace/sbtd-plugins-changelog 也已移除（本次任务提供的完成事实）；本轮 git ls-remote --heads origin docs/changelog-backfill 无输出 |
| 2026-10-23T13:10:17+08:00 | done | done | record correction | 历史「提交 1 `965dca5`」保留不改；965dca5 是 autosquash 前 SHA，合并分支的实际提交 1 为 2058673；本轮 git log --oneline -3 2058673 已确认该提交存在 |
| 2026-10-23T13:51:14+08:00 | done | done | record correction | 纠正 d60b4c1 版本第 32、159、169 行的来源归属：「本次任务提供的完成事实 / FINAL 计数 / 最终统计」均为编排方整理，不是用户提供；原行及 0410bf1 已提交内容保留不改 |
| 2026-10-23T13:51:14+08:00 | done | done | record correction | #117 的 pid 79530 title-gen 日志还包含子代理成功：OmpHistory 1 次（cursor/composer-2.5 success，2026-10-23 12:40:46 +08:00）、DshHistory 1 次（cursor/composer-2.5 success，2026-10-23 12:41:03 +08:00）；此前「pid 79530（main）… 没有生成标题」仅指 main session，不包含子代理；本轮只读核对 omp.2026-10-23.79530.log 的 title-generator success 记录 |

## Book Gate Plan

| Reviewer | 触发事实 / 判定 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、领域术语或模型边界变更 | before-dev | not-required |
| book-ddia-data-design | 仅文档历史回填，不改变数据 schema、运行时读写路径或恢复协议 | before-dev | not-required |
| book-legacy-change-safety | 无生产/测试行为修改；历史正文用 append-only 比较保护 | before-dev | not-required |
| book-refactoring-pass | 无生产代码编辑 | before-dev | not-required |
| book-release-readiness | 不改变运行时、部署或发布，不执行发布 | after-validation | not-required |

## 验证证据

- #116：`git log -1 --format='%H %cI' 25d7e83` 返回 `25d7e83bbc25b6f7d2c5018d7f945376670a2d9a 2026-10-23T12:15:38+08:00`。
- `gh pr view 116 --json state,mergedAt,mergeCommit,mergedBy,headRefName` 返回 MERGED、mergedAt `2026-10-23T04:15:38Z`（+08:00 为 `2026-10-23T12:15:38+08:00`）、同 merge SHA、mergedBy `KunoLu`、headRefName `chore/offline-cache-smoke`。
- `ai/tasks/index.md` 没有 status 列，提交 1 不改；PRD 第 78 行仅后续注记，没有 item-1/#116 merge 字段行，按用户要求整份 PRD 不改。

## 当前值 / 交付边界

- 最终本地交付保留 checking / completed_at null；FINAL 会话计数由后续编排补充，本轮仅记 SNAPSHOT。
- 本地文档验证不等于 CI、Reviewy CLEAN、合并或发布；不承诺跨机器自动恢复。

## 逐版本证据

计数口径：`git log --format='%h %cI %s' <from>..<to> -- <package-path>` / `git rev-list --count <from>..<to> -- <package-path>`，使用 Git 默认 path-history simplification；不是全仓提交数，也不是已发布字节的逐提交认证。KPi 的 package-path 为 `plugins/omp-sbtd`，本仓为 `packages/<package>`。截止点取 npm publish 之前的可见历史；dsh rc.2 优先使用 Registry 的 `gitHead` 分支而非 main 的时间截止点。UTC 时间仅在本表及原始 npm 输出保留，记录事件与其他时间均为 Asia/Shanghai。

| package | version | npm time (UTC) | UTC+8 | commit range（repo；path-filtered count） | 内容来源 | 不可考部分 / 边界 |
|---|---|---|---|---|---|---|
| omp-sbtd | 0.1.0-rc.1 | 2026-07-28T06:19:21.956Z | 2026-07-28T14:19:21.956+08:00 | KPi `55d95ce..4abf891`；6 | `c58a23e` foundation 至 `6851674` P0 gates；tarball 356 files、extension、Kit、SBOM、peer 17.1.3 | 精确 publish 源 SHA 不可考；窗口终点早于发布两天 |
| omp-sbtd | 0.1.0-rc.2 | 2026-07-28T10:03:22.561Z | 2026-07-28T18:03:22.561+08:00 | KPi `4abf891..4abf891`；0 | tarball 对 rc.1 仅新增 README、修改 package.json/SBOM；归档 `07-28-omp-plugin-publish-docs/check.md` | 0 仅指现存窗口提交；不能解释为零变更；README 对应提交不可考 |
| omp-sbtd | 0.1.0-rc.6 | 2026-08-06T06:01:05.665Z | 2026-08-06T14:01:05.665+08:00 | KPi `4abf891..4abf891`；0 | tarball 253 files、peer 17.2.9；归档 RC6 check 的 SHA-256 与实物一致，四命令验收为历史证据 | 缺口内逐版本功能归属不可考；保留「已发布，变更明细不可考」 |
| omp-sbtd | 0.1.0-rc.10 | 2026-08-14T03:41:18.965Z | 2026-08-14T11:41:18.965+08:00 | KPi `4abf891..b81ee90`；1 | tarball 266 files、peer 17.2.9；rc.11–rc.14 随包旧 CHANGELOG 的 rc.10 段 | bump/提交时间晚于 npm；仅修标题日期，原 migration notes 不动，不制造功能归属 |
| omp-sbtd | 0.1.0-rc.11 | 2026-08-18T04:56:08.338Z | 2026-08-18T12:56:08.338+08:00 | KPi `b81ee90..b1a26e2`；13 | `e515f76` findings、`ceebd5a` candidate、`dba7ce8` exact 17.3.5；tarball 279 files + CHANGELOG | 随包标题原为 08-17；按 npm 修为 08-18，正文作为历史保留 |
| omp-sbtd | 0.1.0-rc.12 | 2026-08-20T07:44:12.574Z | 2026-08-20T15:44:12.574+08:00 | KPi `b1a26e2..5b6e13b`；2 | `44a5b43` M2、`20896d1` ownership；tarball 376 files、plugin.json、92 个 skills 文件、CHANGELOG | 随包标题原为 08-18；正文已记 08-20 发布，修标题即可 |
| omp-sbtd | 0.1.0-rc.13 | 2026-08-27T08:10:19.246Z | 2026-08-27T16:10:19.246+08:00 | KPi `5b6e13b..ae5a413`；19 | compatibility decoupling / host contract / cloud §4；tarball 381 files、peer >=17.3.5 <18、policy v2、CHANGELOG | rc.13 随包标题仍 Unreleased；rc.14 随包及现有 EN 已回填 08-27；不把候选包当 Registry 身份 |
| omp-sbtd | 0.1.0-rc.14 | 2026-09-01T12:42:10.276Z | 2026-09-01T20:42:10.276+08:00 | KPi `ae5a413..3b55e93`；16；本仓 `a5e0220..a2f3681`；4（另有 root import `a5e0220`） | `f11abd2` v1.0.13 sync；tarball 412 files、CHANGELOG；迁仓后的路径与 map 更新 | root import 无父提交，不能伪造更早本仓起点；沿用现有 EN 正文 |
| omp-sbtd | 0.2.0-rc.1 | 2026-10-22T12:59:06.925Z | 2026-10-22T20:59:06.925+08:00 | 本仓 `a2f3681..f4ea2ac`；8 | 现有双语条目、migrate-kit/sync-upstream/omp18/release 提交 | 本次仅核日期及保留正文；提供的 tarball 集合不含 0.2.0，不声称重验此发布包 |
| dsh-sbtd | 0.1.0-rc.1 | 2026-09-04T09:21:51.920Z | 2026-09-04T17:21:51.920+08:00 | 本仓 `5a459c1..fcd11b1`；15 | `7253b29` T0 至 `fcd11b1` publish prep；tarball 41 files、plan/review、hooks、manuals 1.0.13 | 更早 `a5e0220`/`f11abd2` 已触及该路径，但可安装 stub 自 `7253b29` 起；本行起点是其父提交 |
| dsh-sbtd | 0.1.0-rc.2 | 2026-09-13T07:58:49.057Z | 2026-09-13T15:58:49.057+08:00 | 本仓 `fcd11b1..2cabe79`；15 | Registry gitHead `2cabe79`；`af01719` 发布前 bump；tarball 93 files、新增 tools/backends、README；T6–T15/FU3/FU4 diffs | main 的截至发布窗口为 `fcd11b1..1157123`（14）；`ae636e8` 是发布后 squash 回填，不作为发布前功能证据 |
| dsh-sbtd | 0.1.0-rc.3 | 2026-09-19T00:29:08.731Z | 2026-09-19T08:29:08.731+08:00 | 本仓 `2cabe79..838f454`；2 | Registry gitHead `838f454`；`46ac3e6` manuals 1.0.15 / lessons；tarball 93 files，变动集中在 lessons、manuals、README、package.json | 两提交含发布后 rc.2 回填 `ae636e8`；rc.3 bump `bbe1178` 晚于 npm，本次不冒充其为发布源 |
| dsh-sbtd | 0.2.0-rc.1 | 2026-10-18T20:43:02.349Z | 2026-10-19T04:43:02.349+08:00 | 本仓 `838f454..1fdf9e8`；6 | 现有双语条目与 PR-B/backend、PR-C/host、PR-E/release 提交 | 本次仅核日期及保留正文；提供的 tarball 集合不含 0.2.0，不声称重验此发布包 |

### 来源与差异处理

- npm 原始来源：编排方于 2026-10-23 只读采集的 `npm view @kunolu/omp-sbtd time --json` / `npm view @kunolu/dsh-sbtd time --json` 及各自 `versions --json`；本轮逐项解析比对，UTC→+08:00 转换与请求一致。下节原样保存 time JSON，不声称本轮重新运行了 npm view。
- tarball 来源：`~/.omp/logs/sbtd-changelog-backfill/tarballs/kunolu-<package>-<version>.tgz`。本轮用 Python `tarfile` 只读提取内存中的文件清单、package.json、README、MANIFEST 与 CHANGELOG，逐文件比较；没有安装或执行包代码，没有解包写入源仓。
- rc.1→rc.2：新增集合恰为 `package/README.md`，删除集合为空，既有文件中只 `package/package.json` 与 `package/SBOM.spdx.json` 字节改变；因此不把归档发布助手/测试全部写成随包 runtime 变更。
- RC6 归档 `KPi/.trellis/tasks/archive/2026-08/08-06-omp-sbtd-17-2-9-rc6-candidate/check.md` 记 source revision `1788b6d4cdaca6c33a8ed338bfc9b6e631017306`、四命令历史通过及 tarball SHA-256 `7860193e8a9d6355de1434a6d026e36d37c7ec9e7b917ef24592fc870a4b55e2`；本轮实物哈希相同。该归档身份不替代缺失的发布前 commit window，也不是本轮重跑宿主验收。
- rc.11 / rc.12 / rc.13 / rc.14 随包 CHANGELOG 均已检查。rc.14 随包从 rc.14 开始的各行与基线 EN 对应段逐行相同（EOF 换行不同）；本次仅修三个日期、intro 并追加 rc.1/2/6，历史正文包括 rc.11 的 candidate/blocked 措辞与 rc.10 migration notes 全保留。中文忠实镜像，而不擅自重写历史。
- KPi 可见历史从 `4abf891`（2026-07-26T19:42:41+08:00）跳至 `cdfe4e1`（2026-08-06T15:39:10+08:00）；`git tag --list` 为空。rc.1/2/6 的精确发布源或缺口内逐提交映射不可考，0 count 不等于无变化。
- KPi `6851674:plugins/omp-sbtd/package.json` 仍为 `0.1.0`；直到 `b81ee90`（2026-08-06T17:27:06+08:00）才在可见历史中为 `0.1.0-rc.2`。npm 发布包由发布流程带出对应 RC 版本，不能用滞后的仓库 version 字段倒推出 npm 时间。
- rc.10 的 npm 发布时间为 2026-08-14T11:41:18.965+08:00。实查 `9e1ba53`（2026-08-14T13:04:50+08:00）已将 package.json 写为 rc.10，晚于发布；提示中的 `e515f76`（2026-08-17T17:37:35+08:00）diff 实际保留 rc.10 version、增加包元数据与 SECURITY/CHANGELOG 文件，不是 version bump。两者均不能充当 rc.10 发布前变更依据；仅在本记录说明，不改写既有 CHANGELOG body。
- “import from KPi 2026-08-20 / `649a2d4`” 与证据冲突：两个仓库 `git cat-file -t 649a2d4` 均 exit 128；本仓首个 commit 为 `a5e022064b47452f55ff4fad3e5d8c825d671aa9`，`%cI` 为 2026-08-28T21:53:04+08:00，subject 为 `Sync omp-sbtd rc.13 and host-compat docs from KPi main.`。不补造不存在的 SHA 或 08-20 导入记录。
- omp `0.1.0-rc.3/.4/.5/.7/.8/.9` 不在 npm versions/time 中，不添加标题；归档 candidate task 不等于 npm 发布。
- dsh rc.2/.3 的 gitHead 来自本轮只读 [rc.2 Registry metadata](https://registry.npmjs.org/@kunolu%2Fdsh-sbtd/0.1.0-rc.2) / [rc.3 Registry metadata](https://registry.npmjs.org/@kunolu%2Fdsh-sbtd/0.1.0-rc.3)，分别为 `2cabe79528aa8a70cf379631e7c7debfb9a8746e` / `838f45463f1163ebb1e2d5b3b45b48a8caec79a4`。tarball 内 package.json 本身没有 gitHead 字段；不把 Registry 元数据说成随包字段。
- 原文件实际状态符合用户裁决：OMP EN 缺 rc.1/2/6、ZH 缺八个旧版；DSH 两种语言各缺三个旧版。按用户 2026-10-22 22:56 +08:00 在 SBTD 群内确认的范围执行，Lord 记录，无需扩大到 README/ROADMAP/PRD。

## npm time 原始输出

`npm view @kunolu/omp-sbtd time --json`（编排方于 2026-10-23 只读采集的 `npm-time-omp.json`，非本轮新查询）：

```json
{
  "created": "2026-07-28T06:19:21.627Z",
  "modified": "2026-10-22T12:59:33.688Z",
  "0.1.0-rc.1": "2026-07-28T06:19:21.956Z",
  "0.1.0-rc.2": "2026-07-28T10:03:22.561Z",
  "0.1.0-rc.6": "2026-08-06T06:01:05.665Z",
  "0.1.0-rc.10": "2026-08-14T03:41:18.965Z",
  "0.1.0-rc.11": "2026-08-18T04:56:08.338Z",
  "0.1.0-rc.12": "2026-08-20T07:44:12.574Z",
  "0.1.0-rc.13": "2026-08-27T08:10:19.246Z",
  "0.1.0-rc.14": "2026-09-01T12:42:10.276Z",
  "0.2.0-rc.1": "2026-10-22T12:59:06.925Z"
}
```

`npm view @kunolu/dsh-sbtd time --json`（编排方于 2026-10-23 只读采集的 `npm-time-dsh.json`，非本轮新查询）：

```json
{
  "created": "2026-09-04T09:21:51.495Z",
  "modified": "2026-10-18T20:43:02.541Z",
  "0.1.0-rc.1": "2026-09-04T09:21:51.920Z",
  "0.1.0-rc.2": "2026-09-13T07:58:49.057Z",
  "0.1.0-rc.3": "2026-09-19T00:29:08.731Z",
  "0.2.0-rc.1": "2026-10-18T20:43:02.349Z"
}
```

## 使用的模型（SNAPSHOT）

下表在 2026-10-23T12:47:25+08:00 从本轮 JSONL 只读采集，计数为 `type=message` / `message.role=assistant` 及其 content 的 `toolCall` 项。计数不含之后的记录、提交和交付；FINAL 由后续编排补充。

| agent/session id | provider/model / thinking | purpose | assistant messages / tool calls |
|---|---|---|---|
| main / `01a1670e-bd7f-7447-b9d9-4ae12fbc2556` | openai-codex/gpt-6-astra:high | 唯一 writer / 验证 controller | SNAPSHOT **28 / 63** |
| ping / `01a1670c-525a-7540-9b14-3d1b5df83785` | openai-codex/gpt-6-astra:high | ASTRA_OK reachability ping（编排方于 2026-10-23 执行 `omp -p`） | **1 / 0** |
| OmpHistory | cursor/composer-2.5；thinking 未记录 | 只读历史检索 | SNAPSHOT **2 / 78** |
| DshHistory | cursor/composer-2.5；thinking 未记录 | 只读历史检索；运行被停止，未交付结论 | SNAPSHOT **2 / 201** |

- 主 JSONL：`~/.omp/logs/sbtd-changelog-backfill/sessions/main/2026-10-23T04-39-41-695Z_01a1670e-bd7f-7447-b9d9-4ae12fbc2556.jsonl`；子会话为同 stem 目录的 `OmpHistory.jsonl` / `DshHistory.jsonl`。只记录模型/计数，不复制完整会话。
- Scout 没有可用 bash，OMP 返回的“tarball/Git 缺失”推断不成立，未采用；DSH 没有有效最终报告。所有提交窗口、计数、tarball 身份与内容均由主会话以真实 Git/Python 调用独立取证，scout 不充当独立验收通过。

## 文档验证与跳过

- 提交 1 `965dca5`：实际 diff 为 1 file、35 insertions / 3 deletions。内存 diff 检查确认删除行恰为旧 `status`、`updated_at`、`completed_at`；旧正文各行仍按原顺序存在；#116 title-gen 表与提供的 PR body 逐字相等。
- 2026-10-23T12:47:06+08:00：Python 一次性文档检查通过。对四个 CHANGELOG 用 markdown-it CommonMark + table 解析并实际渲染 HTML，OMP 两文件各 9 个 version sections、DSH 两文件各 4 个；EN/ZH 版本+日期列表完全相同，且等于 npm versions 按发布时间倒序、日期取 +08:00。
- 同一检查证明：基线 EN 全文经过唯一允许的 intro / 三个日期替换后，仍是当前 EN 的完整前缀；既有 EN body 零删除。index 所有 task 链接均解析到正常文件。
- 已查找 index generator：没有独立 index CLI；沿用现有 `sbtd_task_state.py` 的纯 `_index_rows` renderer，传入旧 index 的已知导航记录与新 task，生成结果仅多一行且顺序不变，再用 edit 写入。没有调用 TaskStore 的全库扫描、lifecycle 或 active-pointer 写入。
- `git diff --check` 已通过；用专用 grep 的 `^## \\[` 打印了四文件标题。后续提交边界与 clean tree 核验以交付时原生命令为准，不提前声称通过。
- 根 `package.json` 的 lint 为 `biome check .`，配置没有 Markdown 校验命令；本 worktree 的 `node_modules/.bin/biome` 不存在（可执行性预检 exit 1），不为纯文档任务安装依赖或运行无关构建。未运行 pnpm lint/build/typecheck/tests，不声称 PASS。
- project-validation 已调用；本任务只有 Markdown，功能测试、BDD、Web/Mobile、API Contract、runtime smoke、生产代码可读性/ponytail-review 与 release gate 均不适用。文档 smoke 为上述真实解析/渲染与契约检查。Graft skipped：无 runtime/code 影响且未挂载，不启动或配置；rtk not-needed：本次原生 Git 与内存校验用于精确文档证据。
- 所有验证是 developer-local，不冒充 CI/full-stack/发布。没有正式测试 runner 报告，Final Test Report / Run Summary MD not-needed；命令和结果保留在本任务及会话。没有创建需清理的临时脚本或解包目录。

### 提交前最终核验

- 2026-10-23T12:50:42+08:00：逐版本对比 EN/ZH bullet 数与 subsection 数，全部相同；人工逐段核对旧版翻译，没有丢弃历史 caveat、SHA、命令或迁移说明。两包现有 0.2.0-rc.1 正文均未改。
- 按本表各 `repo / range / package-path` 重新执行 `git rev-list --count`，全部等于表中 count；原始 npm time JSON 两份与编排方于 2026-10-23 只读采集的文件逐字一致。新增 task 的 schema_version / mode / mode_source / completed_at 当前字段解析通过，不等同全库 TaskStore lifecycle 通过。
- 两份 task 与 index 均经 markdown-it 实际渲染通过；四 CHANGELOG 的标题、日期、原文保护、index generator 与链接解析检查已通过。没有新增永久测试来断言文案。
- 原生取证命令：`git log -1 --format='%h' --until=<npm-time>` 选可见边界；`git log --format='%h %cI %s' <from>..<to> -- <package-path>`；`git rev-list --count <from>..<to> -- <package-path>`；`git show <sha>:<package-path>/package.json`；`git show e515f76 -- plugins/omp-sbtd/package.json`；`git diff fcd11b1 2cabe79 -- packages/dsh-sbtd/README.md`；`git show --stat 46ac3e6`；`git diff 2cabe79 838f454 -- packages/dsh-sbtd/src/tools/lessons.ts`。所有新记录日期均以 npm 的 +08:00 日期为准，不用 commit date 代替 publish date。
- 交付保持 checking，未执行远端写操作；回滚边界为本次两个 docs-only 本地提交，不涉及生产状态、包版本或已发布 tarball。

## 使用的模型（FINAL）

以下为本次任务提供的 session JSONL **FINAL** 计数（assistant messages / tool calls），取代上方 SNAPSHOT 的当前结论；历史 SNAPSHOT 原样保留。本轮不访问其他会话日志目录，不声称重新采集这些计数。

| run | model | assistant messages / tool calls |
|---|---|---|
| ping | openai-codex/gpt-6-astra:high | 1 / 0 |
| main | openai-codex/gpt-6-astra:high | 39 / 75（此前 SNAPSHOT 28 / 63） |
| OmpHistory (subagent) | cursor/composer-2.5 | 2 / 78 |
| DshHistory (subagent) | cursor/composer-2.5 | aborted，3 / 203（此前 SNAPSHOT 2 / 201） |
| fix1 | openai-codex/gpt-6-astra:high | 11 / 23 |

标题生成来源为 `~/.omp/logs/omp.2026-10-23.<pid>.log`，以下同为本次任务提供的最终统计：

- pid 79530（main）：7 次 title-generator 请求，没有生成标题；deepseek 返回 401，grok-4.7 / grok-4.6 回复计为 fallback，不计成功。
- pid 88190（fix1）：8 次请求，composer 成功 1 次；deepseek 返回 401，grok 计为 fallback。
- #117 的 Codex auto-review 因 quota 失败，没有产生 findings，未阻塞合并。

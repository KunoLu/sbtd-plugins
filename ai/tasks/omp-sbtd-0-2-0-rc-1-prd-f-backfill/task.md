---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-prd-f-backfill
workflow_mode: strict
mode_source: user
mode_note: 用户明确选择 strict；docs-only、主会话唯一 writer，仅指定四个路径与两个本地提交，不 push/PR/tag/publish/dist-tag。
status: "checking"
branch: docs/omp-sbtd-0.2.0-rc.1-pr-f-backfill
created_at: '2026-10-22T21:20:46+08:00'
updated_at: '2026-10-22T21:29:12+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 行 F：发布证据回填

## 目标 / 范围 / 非目标

- 按 PRD L60，首 commit 仅回填 PRD 行 E（#114、merge SHA、merge commit done 时间）、启动行 F，并最小更新行 E task.md；第二 commit 仅本记录与索引。
- 仅修改 `docs/prd/omp-sbtd-0.2.0-rc.1.md`、`ai/tasks/omp-sbtd-0-2-0-rc-1-pr-e-release/task.md`、本文件及 `ai/tasks/index.md`。记录发布证据、两项流程偏差与 smoke 未通过；不将发布事实等同于测试通过。
- 不修改 README/CHANGELOG/package/SBOM/代码/测试，不修验收文档 §4；不复制外部日志或截图，不读取 `.env`，不写本 worktree 外文件，不 push、开 PR、tag、发布或 dist-tag。行 F 仅在 Reviewy PR-tip CLEAN + merge 后可 done，本次不预填自身 PR/merge SHA/done 时间。
- 未完整调用 grill-with-docs：范围、先例与验收已由用户明确，无领域歧义。沿用行 R/E 已记录的 TaskStore 全库历史 schema blocker，不重跑确认；仅维护明确授权的共享文档，不写 active pointer，不声称 TaskStore lifecycle 或自动恢复已通过。父路径/文件无 symlink，四个文档路径未被 ignore，既有三文件已 tracked。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T21:20:46+08:00 | planned | in-progress | 用户授权 strict 行 F docs-only 回填；分支匹配、起点 clean | 基线 origin/main = f4ea2ac729a6fda86cd41425563d65c68afb3aa3；PRD L59–L62；用户指定两次提交 |
| 2026-10-22T21:29:12+08:00 | in-progress | checking | 两个本地提交及文档范围验证完成；本状态回填 amend 第二提交，保持两提交，不预报 Reviewy CLEAN/merge | 首提交 af84ae7；第二提交初版 a2af6d6；git diff --check origin/main..HEAD exit 0，diff stat 仅指定四路径，packages/ 零变化；PR 尚未打开 |

## Book Gate Plan

| Reviewer | 触发事实 / 判定 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill；仅回填锁定事实，无领域规则或上下文歧义 | before-dev | not-required |
| book-ddia-data-design | 无 schema/迁移/缓存/跨服务流设计；共享 task 是既有格式的文档记录 | before-dev | not-required |
| book-legacy-change-safety | 无既有行为 bug 修复或生产行为变更 | before-dev | not-required |
| book-refactoring-pass | 无生产代码编辑 | before-dev | not-required |
| book-release-readiness | docs-only 历史回填，无 runtime/deployment 变更；不执行发布、不声明 release-ready | after-validation / finish | not-required |

## 验证证据

- 2026-10-22T21:19:34+08:00 入口：实际分支匹配、HEAD 为 `f4ea2ac729a6fda86cd41425563d65c68afb3aa3`，`git status --short` 为空。
- 本会话只读 `git show -s --format=%cI f4ea2ac`：`2026-10-22T20:27:22+08:00`。`gh pr view 114`：MERGED，GitHub mergedAt `2026-10-22T12:27:23Z`，headRefOid `fa669e64d83bfa06602669ef89c02bb70f84d085`，reviews 为空。done 时间以 %cI 为准，不能用晚 1 秒的 mergedAt 替代。

### 来源边界

- 所有未另注时区的时间均为 2026-10-22 Asia/Shanghai（+08:00）。用户提供的「live」是 **orchestrator 在 21:15–21:17 的复查**，不是本会话执行；本会话只读复查窗口为 **21:20–21:23**。历史授权、Reviewy CLEAN、Lord 浏览器观测均明确归因，不伪装 GitHub review 或本会话实测。
- 本会话读取 git/gh 公共元数据、registry JSON、指定外部 tarball/日志/截图的校验和；CI artifact/run-log archive 只在内存解析，不解包落盘、不复制证据入库。仅提取日志安全事实和会话模型元数据，不打印秘密或完整会话。
- 本地文档验证为 developer-local / local-only，不是对行 F PR tip 的 CI 或 Reviewy CLEAN。行 E 的历史发布证据绑定 `f4ea2ac729a6fda86cd41425563d65c68afb3aa3`，不冒充行 F 运行时验证。

### 1. #114 合并、tag、D7 与 prerelease

- `gh pr view 114 --json state,mergeCommit,mergedAt,headRefOid,reviews` 与 `git show -s --format='%H %cI' f4ea2ac729a6fda86cd41425563d65c68afb3aa3`（本会话复查）：MERGED；merge SHA `f4ea2ac729a6fda86cd41425563d65c68afb3aa3`；%cI **20:27:22+08:00**，GitHub mergedAt **20:27:23+08:00（12:27:23Z）**。PRD L60 done 时间取前者。review tip `fa669e64d83bfa06602669ef89c02bb70f84d085`（`fa669e6`）；该 tip 的 **Reviewy CLEAN 来源为 orchestrator/Reviewy 陈述**，不是 GitHub review；API `reviews=[]`。
- `git for-each-ref --format='%(objecttype) %(objectname) %(*objectname) %(taggername) %(taggerdate:iso-strict)' refs/tags/omp-sbtd-v0.2.0-rc.1`、`git ls-remote origin refs/tags/omp-sbtd-v0.2.0-rc.1 'refs/tags/omp-sbtd-v0.2.0-rc.1^{}'`（本会话复查）：annotated/type `tag`；object `942fca1322fe6b3fc8441fe3a83d0e0198b850ab`；peeled `f4ea2ac729a6fda86cd41425563d65c68afb3aa3`；tagger `640`，tagger time **20:28:47+08:00**；远端 object/peeled 相同。
- D7：orchestrator 陈述 Reviewy 于 **20:29** 在 tag 上点击核验双语切换链接通过；orchestrator 21:15 `curl -L` 均 200。本会话 **21:21:56+08:00** 使用 `curl -L -sS -o /dev/null -w '%{http_code}'` 复查下列两个完整 URL，均 **HTTP 200**（不是再次浏览器点击）：
  - EN：<https://github.com/KunoLu/sbtd-plugins/blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README.md>
  - 中文：<https://github.com/KunoLu/sbtd-plugins/blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md>
- `gh release view omp-sbtd-v0.2.0-rc.1 --json isPrerelease,isDraft,name,createdAt,publishedAt,url`（本会话复查）：`isPrerelease=true`、`isDraft=false`，name `@kunolu/omp-sbtd 0.2.0-rc.1`；createdAt **12:28:47Z（20:28:47+08:00）**，publishedAt **2026-10-22T12:33:28Z（20:33:28+08:00）**；URL <https://github.com/KunoLu/sbtd-plugins/releases/tag/omp-sbtd-v0.2.0-rc.1>。

### 2. 受信 publish gate 与本地交叉检查

- 本会话 `gh run view 39780731295 --json workflowName,event,headBranch,headSha,createdAt,updatedAt,conclusion,jobs,url`：<https://github.com/KunoLu/sbtd-plugins/actions/runs/39780731295>；workflow `omp-section4-publish-gate`，event `workflow_dispatch`，headBranch `main`，headSha `f4ea2ac729a6fda86cd41425563d65c68afb3aa3`；**12:43:40Z–12:48:48Z（20:43:40–20:48:48+08:00）**，conclusion **success，5/5 jobs success**：
  1. Fail closed outside trusted main dispatch
  2. Pack the RC tarball exactly once
  3. Generate the npm-offline-v1 diagnostic lock and cache
  4. Offline install, four-command surface and diagnostic write-check
  5. Publish the omp-section4-publish-gate commit status
- 本会话通过 `gh api repos/KunoLu/sbtd-plugins/actions/runs/39780731295/artifacts` 定位 `omp-section4-command-surface`（id `12427186228`，未过期），再通过 artifact `/zip` 在内存读取：`section4-cell.json` 的 outcome **passed**，pluginTarballSha256 **`fea47dcb65af87d24e15698957b42a5e05e0ab66c5b3a2294b46eef709287344`**，`help` / `status` / `report` / `onboard plan` 四命令均 `contentValidated=true`；同 artifact 的 **`command-surface.json`** 记录 `hostIdentity.packageVersion=18.11.1`（该字段不在 section4-cell.json）。与本地 tarball SHA-256 相等。
- 日志来源：orchestrator 提供 `installerGeneration=npm-offline-v1`、`section-4-write-check=passed`；本会话 `gh api repos/KunoLu/sbtd-plugins/actions/runs/39780731295/logs` 内存 ZIP 复查两个 marker 均存在。此前单 job logs API 返回 exit 1，已改由完整 run archive 验证，不将失败调用写为通过。
- `gh api repos/KunoLu/sbtd-plugins/commits/f4ea2ac729a6fda86cd41425563d65c68afb3aa3/status`（本会话复查）：context `omp-section4-publish-gate`，state **success**，created_at **12:48:46Z（20:48:46+08:00）**，description `section4 success: tarball fea47dcb65af omp 18.11.1 installer npm-offline-v1`。
- 本地 `/workspace/sbtd-rel-accept/SUMMARY.md` 与 `write-check.log`（本会话安全摘取；hash 见下表）：使用 **omp 18.11.1 local host**，不是 main 的 18.12.5；四命令 **4/4 PASS**，write-check passed，无 Apply/approval。SUMMARY 的 NOTE 明确：**§4 trusted GitHub gate is the ONLY publish-authorizing evidence**。因此本地运行仅交叉检查；其先于 gate 的顺序属于下述偏差 1。

### 3. tarball、helper publish、registry 与 latest

| 项目 | 事实 / 证据来源 |
|---|---|
| 实际 tarball | `/workspace/sbtd-rel-pack/kunolu-omp-sbtd-0.2.0-rc.1.tgz`；orchestrator 21:15 `tar tzf … \| wc -l` = **471**；本会话 Python `tarfile` 内存读取亦为 **471 entries** |
| SHA-1 | **`b350be576bd0719120d7aa26ed84cc9dfa7e0746`**；本会话 `hashlib` 对 tarball 重算，与 registry `dist.shasum` 相等 |
| SHA-256 | **`fea47dcb65af87d24e15698957b42a5e05e0ab66c5b3a2294b46eef709287344`**；本会话重算，与 gate artifact 相等 |
| integrity | **`sha512-7qAcOaFOEZoC1ER/dH7K/GBPXr6wOTZ6lgzee0opUBxjswk1brb0+UiqzJtAHcTgSn+leXEBgFbk61pqwmq3mg==`**；本会话 SHA-512/base64 重算，与 registry `dist.integrity` 相等 |
| publish 前 | `/workspace/sbtd-rel-publish/pre.log`：**20:54:50**，`npm view …@0.2.0-rc.1` E404；当时 `latest=0.1.0-rc.2`、`next=0.1.0-rc.14`（orchestrator 日志摘录；本会话另确认 E404/exit 1） |
| helper 调用 | `docs/deploy/publish-omp-sbtd.sh` 从 main clone `/workspace/sbtd-plugins` 以 **`--tag next`** 运行；调用位置/参数来源为 orchestrator。本会话未执行 helper、未访问其 `.env` |
| helper 开始/结束 | `/workspace/sbtd-rel-publish/publish.log`：**`# start 2026-10-22 20:54:55 CST`**，npm notice shasum `b350be57…`、total files 471、`Publishing to https://registry.npmjs.org/ with tag next and public access`，**exit=0**，**20:54:58** 结束；本会话安全摘取起止/文件数/通道/exit |
| registry 时间 | registry document `time["0.2.0-rc.1"]` = **`2026-10-22T12:59:06.925Z`（20:59:06.925+08:00）**；orchestrator 21:15 live，本会话 **21:21:56+08:00** 通过 Python `urllib.request` GET `https://registry.npmjs.org/@kunolu%2fomp-sbtd` 独立复查；不混同 helper start 20:54:55 |
| 404 窗口 | `/workspace/sbtd-rel-publish/post.log`：**20:55:06** 及 **poll 12 / 20:59:14** 仍 E404（该 poll 的 next 已为 0.2.0-rc.1）；**20:59:21** direct registry 已见版本、shasum/integrity 匹配。来源为 orchestrator 日志摘录，本会话确认三时点/E404。helper exit 后约 **4 分钟**可见性窗口；npm 提示 “may take a few minutes to become available” |
| latest promotion | `/workspace/sbtd-rel-publish/disttag.log`：**20:59:33** 开始，`npm dist-tag add @kunolu/omp-sbtd@0.2.0-rc.1 latest`，输出 `+latest: @kunolu/omp-sbtd@0.2.0-rc.1`，exit=0，**20:59:34** 结束；本会话确认起止/输出/exit，调用方式与授权来源为 orchestrator，属于偏差 2 |
| 最终 dist-tags | `/workspace/sbtd-rel-publish/final.log` **20:59:49**、orchestrator **21:15** `npm view @kunolu/omp-sbtd dist-tags` 均为 **`{"latest":"0.2.0-rc.1","next":"0.2.0-rc.1"}`**；本会话 **21:21:56** registry JSON 相同 |
| 发布后包身份 | orchestrator **21:15** `npm view @kunolu/omp-sbtd@0.2.0-rc.1 dist.shasum dist.integrity` 与本地包相等；本会话上述 registry JSON/hashlib 独立复查相等，不重跑 publish/dist-tag |

### 4. D4 npmjs 页面、packed README 与不需修正的文档

- **orchestrator 转述 Lord 于 21:13 的浏览器检查**：<https://www.npmjs.com/package/@kunolu/omp-sbtd> 显示 `0.2.0-rc.1 • Public • Published 14 minutes ago`；sidebar Version `0.2.0-rc.1`；`EN · 中文` 指向上述两个 tag URL；新 README Install 文本为 “`@kunolu/omp-sbtd@0.2.0-rc.1` is published to npm dist-tags `next` and `latest`.” 本会话未重新操作 npmjs 浏览器。
- 截图 `/workspace/sbtd-rel-publish/npmjs-page-0.2.0-rc.1.png`，SHA-256 **`2b5f9128f89d01b6572858071a83b1f39bf809866c074df08231e58e986a62df`**（orchestrator 21:15 live、本会话独立重算）。orchestrator 已查看截图：仅能证明 header、EN·中文、Version 可见；**Install 句在折叠线下，不在截图内**，该句由 packed README L32 另证。截图只引用路径+hash，不提交。
- 本会话 `tarfile.extractfile("package/README.md")` 内存读取：SHA-256 **`761f261c62efcf588496b5b86c6020e91389f3e73e0ca314f450440c444dfd01`**，与 `git show f4ea2ac:packages/omp-sbtd/README.md` 字节相等，也等于 SBOM `./README.md` checksum（行 E 记录同值）。L2/L4 为上述 EN/中文 tag 链接，L32 为上述 Install 句。
- registry `readme` 元数据是空字符串 `''`（orchestrator final.log/21:15 live；本会话 registry JSON 独立确认），**不作为 npmjs README 缺失的证据**；本次采用页面观测与 packed README，不依赖当前 npm 未填充的字段。
- 本会话源码读取：根 `README.md` / `README_zh.md` **L23/L28/L67** 已写发布到 `next` 与 `latest`，包 README EN L32 / ZH L31 同样如此；与实测 dist-tags 相符，**根及包 README 无需修正**，保持字节不变。
- 本会话读取验收文档 **`docs/assets/omp/omp-plugin-host-acceptance.md` §4 L101** 为「仅 KunoLu/KPi」，实际 workflow **`.github/workflows/omp-section4-publish-gate.yml` L5/L51** 为 `KunoLu/sbtd-plugins`。已登记后续，本次不改这两个文件。

### 5. 外部日志定位与 SHA-256

以下为本会话对现有文件重算的 SHA-256；不将日志、截图或 tarball 复制进仓库，不保证其他机器可访问这些本地路径。

| 外部路径 | SHA-256 |
|---|---|
| `/workspace/sbtd-rel-publish/pre.log` | `f5ca7d8c3a8c1a1b7acd4c4c96fcb7d1ec5e1651066b0d94fe4e4e3066fee625` |
| `/workspace/sbtd-rel-publish/publish.log` | `6a1a9bf71402761f6b02751739dc61acf7a5bb9338260d9ce06365345ba47426` |
| `/workspace/sbtd-rel-publish/post.log` | `b8ea7d3f04b2045d6537a1a5c7f300e6d017b7492f7cb1a93bae1776139aba28` |
| `/workspace/sbtd-rel-publish/disttag.log` | `4b6a871d2de27470c94cff9f8df5448ecb806cc47db91c6392377d1cfe5bd2e4` |
| `/workspace/sbtd-rel-publish/final.log` | `b39ba4b697650177164a1e5ffd9c3a07faa633665a22d88ef7107fafb7012121` |
| `/workspace/sbtd-rel-accept/SUMMARY.md` | `c4ea837f4c3a9b4baef5c9a8094d5ed9392e95b3e5643bb03f59a1786d180205` |
| `/workspace/sbtd-rel-accept/write-check.log` | `9038bc8585214453fb0b0d1ff95f185139eaad03fd7ccc215b6af580e1dfec58` |

## 流程偏差

1. **受信 gate 顺序遗漏后补齐。** 行 E 原顺序先跳过受信 gate，先执行本地 exact-tarball 四命令验收；本地 4/4 PASS / write-check passed **仅交叉检查**，不能授权发布。随后在 **20:43:40–20:48:48** 补跑并通过 trusted GitHub gate，早于 **20:54:55** publish start。来源：orchestrator 顺序陈述、本地 SUMMARY NOTE、GitHub run、publish.log；不能倒写成原流程无遗漏。
2. **latest 写入在 helper 外。** `packages/omp-sbtd/README.md` L97 “the only approved Registry writer” 与 PRD 的唯一 helper 边界仍有效；**20:59:33** 的直接 `npm dist-tag add … latest` 不经 helper 执行，是流程偏差，不因成功或授权而改称合规。orchestrator 陈述：用户 **20:44** 授权 helper 通过 `load_dotenv_npm_token` 从 `.env` 加载 NPM_TOKEN；用户 **20:45** 授权 latest，Lord 批准，未使用 OTP；latest 使用同一加载函数得到的 token 写入临时 **0600 userconfig**，事后删除。以上为历史授权/凭据处理陈述，本会话未读取 token/`.env`，未重做或验证凭据生命周期。orchestrator 初扫未发现泄漏，**21:17** 对 `/workspace/sbtd-rel-publish/*.log` 与 `/workspace/sbtd-rel-accept/*.log` 的 npm token patterns / `_authToken` 重扫 **0 hits**；本会话 **21:22:30** 对 **17 个 .log** 做相同方向的只计数扫描（`npm_[A-Za-z0-9]{20,}` / `_authToken`），亦 **0 hits**，不打印匹配内容、不声称穷尽所有秘密形式。

## 已知失败

- **`p0-authorized-omp-rpc-harness`：not passed — environment cause（未通过—环境原因）**。`test/p0-authorized-omp-rpc-harness.test.ts` 的 smoke-only / exact-local-OMP **18.11.1** cell 因 Bun `--offline` cache 缺 **zod / @oh-my-pi/pi-coding-agent** manifests 而 FAILED，未到 RPC。来源：行 E task.md 的既有失败记录；用户 **20:27** 决定由 orchestrator 转述，本次按明确要求如实回填。
- **不是 PASS，不是豁免，不是 accepted skip**；发布成功、独立受信 gate success、本地四命令通过均不改变此 cell 的失败。行 E done 仅按用户指定的 #114 合并回填，不把历史失败抹掉；其旧 “post-merge steps (not yet done)” 与 release-readiness 文本保留为历史。
- 本会话不重跑该失败、不修 Bun cache、不改测试。下一次发布前的修复另见后续；未来条件 skip 不追溯改变本次结果。

## 后续

- 下次发布前单独 offline-cache chore：使 `p0-authorized-omp-rpc-harness` exact-local-OMP smoke **仅在 Bun offline cache 确实不可用时 skip 并打印原因**；同 chore 修正验收文档 §4 L101 的 `KunoLu/KPi` 与 workflow L5/L51 的 `KunoLu/sbtd-plugins` 不一致。本 PR 只登记，不实施。
- 行 F 的 PR 尚未打开；由后续责任方提交 Reviewy PR-tip review，**CLEAN + merge 后**才回填行 F 自身 PR/merge SHA/done 时间。当前不标 done、completed_at 保持 null，不承诺自动恢复；不自动 push/PR/删分支。

## 使用的模型

> 仅从 session jsonl 抽取元数据与计数；provider/model 来自 assistant messages，thinkingLevel 来自 `thinking_level_change`，resolvedModelIsFallback 来自 `model_change`。assistant 为 `type=message` 且 role assistant，tool calls 为这些消息中的 `toolCall`。主会话为 **2026-10-22T21:25:18+08:00 SNAPSHOT**，不是最终计数；最终数由 orchestrator 在 PR body 报告。

| agent/session id | provider/model | thinkingLevel | purpose | assistant messages / tool calls | resolvedModelIsFallback |
|---|---|---|---|---|---|
| pre-run ping / `01a163c2-b155-7113-994c-eac5da1aed28` | openai-codex / gpt-6-astra | high | orchestrator 连通性 ping（ASTRA_OK）；本会话从 jsonl 核对元数据/计数 | FINAL **1 / 0** | false |
| main / `01a163c4-29c3-701f-b28a-a060d9acb1a7` | openai-codex / gpt-6-astra | high | 唯一 writer、证据复查、文档验证与两个本地 commits | SNAPSHOT **14 / 37** | false |

- main jsonl：`~/.omp/logs/sbtd-pr-f/sessions/run1/2026-10-22T13-19-22-563Z_01a163c4-29c3-701f-b28a-a060d9acb1a7.jsonl`。
- ping jsonl：`~/.omp/logs/sbtd-pr-f/sessions/ping/2026-10-22T13-17-46-197Z_01a163c2-b155-7113-994c-eac5da1aed28.jsonl`。
- 未调用子代理、未 override 模型；不把 reviewer/scout/task 的预期配置当作本次实测，也不声称已完成行 F 独立 Reviewy CLEAN。

## 本次文档验证与提交

- 已读取 #109 首 commit `92113b5`、#114 首 commit `2634fd1` 与 dsh #100 记录，沿用最小 backfill 格式；不添加 PRD §6 修订日志。
- 首 commit **`af84ae7ee141acee75657e882724ba03b424c5ca`**：`docs(prd): backfill row E (#114 / f4ea2ac) with tag/publish evidence; start row F`，仅 PRD + 行 E task.md，**2 files changed, 8 insertions(+), 5 deletions(-)**。提交前 `git diff --check` exit 0；仅 `git add` 两个显式路径。
- 本会话内存文档检查通过：PRD E/F 各 **8 列**，任务正文/优先级/路径保持；PRD 表前内容（含 header/§0–2）与 §4–6 字节不变；仅新增一个证据注和一个后续行；行 E 相对 origin/main **恰好三个 frontmatter 字段 + 一条指定 done event**，历史正文不变。
- 第二提交初版 **`a2af6d6`**：`docs(omp-sbtd): row F — strict task record with verification evidence and models`，仅本记录 + index；之后将真实 checking 状态与已执行验证回填并 amend 此提交，不新增第三提交。最终 SHA 由交付回复及 orchestrator PR body 记录，避免自引用 SHA。
- **21:29:12+08:00 提交后检查**：`git diff --check origin/main..HEAD` exit 0；`git diff --stat origin/main..HEAD` 恰四个指定路径；`git diff --exit-code origin/main..HEAD -- packages/` exit 0、无输出；`git status --short` 为空。索引恰增加一行，位于 prd-d4-release-docs 后、prd-r7-p0-v4 前；YAML frontmatter、实际分支、+08:00 时间与所需章节检查通过。PRD 不在包内且 package 文件不变，pack/SBOM 不受本次文档变更影响。
- `project-validation` 已加载；full suite / focused tests / build / pack / SBOM 重生成 / lint / typecheck **skipped**：docs-only，用户禁止改代码/测试/包，PRD 位于 package 外，没有新运行时行为。本次无永久测试或 throwaway 文件；不是新 smoke PASS。
- `rtk`: not-needed（原生命令用于用户指定 git/只读证据核验）；BDD: skipped（无行为或 .feature 改动）；Cross-repo context / API Contract: not-needed；Mock Strategy: none；Graft / Web / Mobile: skipped（不改结构/UI，npmjs 页面来源明确为既有 Lord 观测）。无新正式测试报告，Final Test Report / Run Summary MD: not-needed；历史 CI/日志保留原来源，不重新包装为当前 PR-head 认证。

# OMP Plugin 兼容认证与 ledger 运行手册

状态：已按 2026-08-26 第一次成功闭环核对。只记录最终成功路径。  
仓库：`KunoLu/KPi`  
目标 Plugin：`@kunolu/omp-sbtd`  
本手册不发布 npm、不移动 dist-tag、不把 `eligible` 写成 `certified`。

---

## 0. 和其它手册的分工

| 手册 | 管什么 | 不管什么 |
|---|---|---|
| 本文件 | 受信任 CI 三 profile 认证、subject 绑定、ledger bot PR、ledger-validate、合入公开 ledger | npm pack / publish、本地 TUI 四命令、消费者安装 |
| [`omp-plugin-host-acceptance.md`](./omp-plugin-host-acceptance.md) | RC / stable 精确 tarball、隔离四命令验收、`next` 发布、消费者安装 | 三 profile `certified`、Host Contract / `omp-extension-v1` 完整探测 |
| [`omp-plugin-compatibility-decoupling-plan.md`](./omp-plugin-compatibility-decoupling-plan.md) | 方案与派生规则 | 可执行 HITL 步骤 |

本地四命令通过只允许把精确 OMP 标为公开 `supported`。`certified` 只能由本手册的受信 ledger 派生。

**Host Contract 不写进 `omp-plugin-host-acceptance.md`。** 那份文档记录的是发布路径上的本地四命令（Command Surface 基线），不是认证矩阵里的 Runtime Capability / Host Contract profile。Host Contract 成功跑通之前，只在本文件第 8 节留位。

---

## 1. 成功闭环在证明什么

对一个**已经发布**的 Plugin tarball 和一个 **peer range 内**的精确 OMP 版本：

1. 在受保护的 `refs/heads/main` 上跑 `omp-compatibility-certification`。
2. 三个 profile 各自留下 outcome（通过、带诊断通过、blocked 或 failed）。
3. `actions/attest-build-provenance` 签署的是 cell `subjects/*` 文件，不是 attestation bundle JSON。
4. bot 只推 `omp-compatibility/<runId>` 分支并开 PR；不推 `main`。
5. 发布负责人从 `main` 手动派发 `omp-compatibility-ledger-validate`。
6. validator 从不 checkout / 执行 PR head；用 GitHub API 取字节，用 `gh attestation verify --bundle <bundle> <subject-file>` 验每一个新 subject。
7. 校验通过只允许合入 ledger / catalog / evidence。Plugin 版本、tarball、SBOM、dist-tag 不变。

第一次成功合入的公开状态是 **`eligible`**（三个必需 profile 均为 `blocked`，无 fail）。这是合法派生，不是 `certified`。

---

## 2. 每次开跑前必须已经在 `main` 上的前置

不要在缺这些提交的 `main` 上派发。当前成功路径依赖：

| 前置 | 作用 |
|---|---|
| 认证 workflow 只允许 `KunoLu/KPi` + `refs/heads/main` + `workflow_dispatch` / `schedule` | 非受信 ref 直接 fail closed |
| `create-ledger-pr` 在 commit 前设置 `github-actions[bot]` 身份 | ubuntu-latest 空 ident 会让 `git commit` 失败 |
| 仓库设置 **Allow GitHub Actions to create and approve pull requests**（`can_approve_pull_request_reviews=true`） | 否则 `gh pr create` 被拒，账本留在自动化分支上开不出 PR |
| `finalize-cell` 把每个 attested subject 写到 `validation/p0/evidence/<sha256>`（无后缀） | validator 必须拿到真实 subject 字节 |
| `collect` 拷贝整个 cell evidence 目录 | 大文件 subject 必须进 ledger-update 产物 |
| validator 对 **main 上没有的** bundle：按 `subjectDigests` 取文件，`gh attestation verify <subject> --bundle <bundle> --repo KunoLu/KPi --cert-identity https://github.com/KunoLu/KPi/.github/workflows/omp-compatibility-certification.yml@refs/heads/main` | 不能把 bundle JSON 当 subject；`--signer-workflow` 只是子串匹配，不能当唯一钉 |
| 大于 1MiB 的 subject 用 `Accept: application/vnd.github.raw` 拉取，并 `sha256sum` 对账 digest | Contents JSON 的 `.content` 在 >1MiB 时为空 |
| 环境 `omp-compatibility-certification` 有部署保护（需发布负责人审批） | cell 才能签 attestation |
| 环境 `omp-compatibility-ledger-status` 配有 `OMP_COMPATIBILITY_STATUS_APP_ID` / `OMP_COMPATIBILITY_STATUS_APP_PRIVATE_KEY` | 没有 Status App 就不写 commit status，合入保持 blocked |

保护环境审批是 **deployment 审批**，不是代码 review，也不是 `certified`。

### 2.1 保护环境审批（HITL）怎么做

本手册有三处必须等人审环境，控件相同，环境名不同：

| 时机 | 环境名 | 次数 |
|---|---|---|
| 第 4 节 cell 开始前 | `omp-compatibility-certification` | 每个认证 run 一次 |
| 第 6.2 节写 pending status 前 | `omp-compatibility-ledger-status` | 每个 validate run 一次 |
| 第 6.4 节写 final status 前 | `omp-compatibility-ledger-status` | 同一 validate run **再一次** |

审批者必须是该环境的 required reviewer。这是 deployment 审批，不是 PR review，也不是 `certified`。

**Reject 与 Approve 是两个按钮。只点 Approve and deploy。** 点 Reject 会让 Waiting 的 job 失败，只能重派 workflow。

成功路径只有 **A（网页）** 和 **B（ego-browser）**。没有 ego-browser 时用 A。`gh api` pending_deployments 与 Playwright 都未在本闭环跑通，不得当操作步骤；见 2.1.3 与第 8 节占位。


#### 2.1.1 A. GitHub 网页（所有人都能用，基线）

1. 打开该次 run：`https://github.com/KunoLu/KPi/actions/runs/$RUN_ID`
2. 等到目标 job 为 Waiting，页上出现 **Review deployments**。
3. 点 **Review deployments**。
4. 勾选本次环境名（上表）。
5. 只点 **Approve and deploy**。
6. 页上出现 “The deployments have been approved.” 后，用 `gh api .../jobs` 确认该 job 从 `waiting` 变为 `in_progress`。

没有 ego-browser 时只用本节。


#### 2.1.2 B. ego-browser（本机已安装时的 Agent 辅助）

2026-08-26 成功闭环用 ego-browser 点与 A **相同**的 GitHub 控件。它复用操作者已经登录 GitHub 的会话，不另开一套登录。没有安装时不要用本节，改用 A。


已核实的操作顺序（每次点击前重新 `snapshotText`，不要复用过期 ref）：

1. `useOrCreateTaskSpace('kpi omp compatibility HITL')`。同一认证任务复用该 space。
2. 先用 `gh api .../jobs` 确认目标 job 已是 `waiting`，再 `openOrReuseTab` 打开  
   `https://github.com/KunoLu/KPi/actions/runs/$RUN_ID`。
3. `snapshotText()`，找到文案为 **Review deployments** 的按钮并 `click`。
4. 再 `snapshotText()`。对话框里有环境 checkbox、**Reject**、**Approve and deploy**。
5. 勾选本次环境。只 `click` 文案为 **Approve and deploy** 的按钮；先确认它的 ref **不是** Reject。
6. 新 snapshot 含 “The deployments have been approved.”，且 `gh api .../jobs` 里该 job 变为 `in_progress`。

整轮结束后单独一条 heredoc：`completeTaskSpace('kpi omp compatibility HITL', { keep: false })`。

不要把未在 Waiting run 上执行过的一键脚本写进成功路径。ref 每次页面重绘都会变。


#### 2.1.3 C. `gh api` pending_deployments（未跑通，不是步骤）

GitHub 有 pending-deployments REST，理论上可用 reviewer 的 `gh` 批准、不点浏览器。**本闭环没有用过。** 无 ego 时的成功路径是 A（网页），不是 C。命令留到第 8.7 节，成功执行后再写。

#### 2.1.4 D. Playwright：评估结论（不是 B 的替代品）

Playwright **可以**点与 A 相同的 GitHub 控件，但 **不能**默认代替 ego-browser。

| | A 网页 | B ego-browser | Playwright 默认 |
|---|---|---|---|
| GitHub 登录 | 操作者自己的已登录浏览器 | 复用同一登录会话 | 新开干净浏览器，没有登录态 |
| 2FA / SSO | 已完成 | 已完成 | 要再登录，脚本过不了 |
| Approve vs Reject | 手点 Approve and deploy | 按按钮 **文本** 区分 ref | 同样必须按文本区分 |
| 本手册是否已成功跑通 | 是（与 B 同一套控件） | 是（2026-08-26） | 否 |

因此：

- 没有 ego-browser 时用 **A**。不要把「装 Playwright」或未跑通的 pending-deployments API 当成接入前提。
- 只有已经接到 **已登录 GitHub** 的浏览器时，Playwright 才有意义（CDP 连本机 Chrome，或带操作者 profile 的持久 `userDataDir`）。不要把 `storageState` / cookie 写进仓库、手册或日志。
- 即使接上了，仍必须走 A 的控件顺序。本手册 **不提供** Playwright 脚本。有人用已登录 Playwright 完整跑通后，写入第 8.6 节。



---

## 3. 成功路径：派发认证

### 3.1 确认派发点

必须从当前受保护 `main` 派发，不要用 feature 分支。

```bash
git fetch origin main
git rev-parse origin/main
gh api repos/KunoLu/KPi/commits/main --jq .sha
```

两个 SHA 必须一致。下面记为 `$MAIN_SHA`。

### 3.2 派发

复用已发布 tarball、不增加新 OMP 版本时，不要填 `newRuntime`：

```bash
gh workflow run omp-compatibility-certification \
  --repo KunoLu/KPi \
  --ref main
```

只要给某个 **精确、稳定、in-range** 的新 OMP 加一格（例如 `17.9.2`），才加：

```bash
gh workflow run omp-compatibility-certification \
  --repo KunoLu/KPi \
  --ref main \
  -f newRuntime=17.9.2
```

prerelease Runtime 不能进公开矩阵。本手册第 8 节在新版本第一次成功前不写该参数的验收记录。

### 3.3 拿到 run URL 和 run ID

```bash
gh run list --repo KunoLu/KPi \
  --workflow omp-compatibility-certification \
  --limit 1 \
  --json databaseId,status,event,headSha,url
```

核对：

- `event` = `workflow_dispatch`（或已启用的 `schedule`）
- `headSha` = `$MAIN_SHA`
- 记下 `databaseId`，下面称 `$CERT_RUN_ID`

打开：

`https://github.com/KunoLu/KPi/actions/runs/$CERT_RUN_ID`

---

## 4. 成功路径：审批认证环境

### 4.1 等到 Waiting

成功顺序：

1. `Fail closed outside trusted main` → success  
2. `Admit published targets and plan the matrix` → success  
3. `Three-profile cell certification and attestation (…) ` → **Waiting**（环境 `omp-compatibility-certification`）

```bash
gh api repos/KunoLu/KPi/actions/runs/$CERT_RUN_ID/jobs \
  --jq '.jobs[] | {name,status,conclusion}'
```

### 4.2 审批

按 **§2.1** 批准环境 `omp-compatibility-certification`（每个认证 run 一次）。有 ego-browser 用 2.1.2；没有则用 2.1.1（网页）。不要用未登录的 Playwright，也不要用未跑通的 pending-deployments API。

这是环境 HITL，不是把结果标成 `certified`。



### 4.3 等到 bot PR

审批后成功顺序：

4. Three-profile cell → success（会签 `subjects/*`）  
5. `Merge attested cells and emit the ledger update` → success，且 `ledgerChanged=true`  
6. `Open the controlled ledger bot PR` → success  

整 run `conclusion=success`。

若 collect 判定重复、没有新 entry，则没有 update 产物、不开 PR。那是「无新账本」成功，不是失败；本手册后续步骤在这种情况下停止。

---

## 5. 成功路径：核对应收 ledger PR

### 5.1 找到 PR

```bash
gh pr list --repo KunoLu/KPi --state open \
  --json number,title,headRefName,headRefOid,url
```

成功形态：

- title：`omp-compatibility ledger update (run $CERT_RUN_ID)`
- head：`omp-compatibility/$CERT_RUN_ID`
- base：`main`
- 同仓，不是 fork

记下 `$PR_NUMBER` 和完整 40 位 `$PR_HEAD_SHA`。

### 5.2 核对作者与提交

```bash
gh pr view $PR_NUMBER --repo KunoLu/KPi \
  --json author,commits,files,headRefOid,baseRefName
```

成功时：

- 作者是 `github-actions[bot]`
- 提交说明：`chore(compatibility): trusted ledger update from run $CERT_RUN_ID`
- 只改 `plugins/omp-sbtd/validation/p0/`

### 5.3 核对应收文件

PR 必须同时有：

1. `plugins/omp-sbtd/validation/p0/compatibility-ledger.v1.json`
2. 如本轮 admission 追加了 published target：`compatibility-targets.v1.json`
3. `validation/p0/evidence/<bundleSha256>.json`（attestation bundle）
4. 每个 `subjectDigests` 值对应的 **无后缀** `validation/p0/evidence/<sha256>`  
   至少包括：`pluginTarball`、`pluginManifest`、`ompArtifact`、`commandSet`、`hostEventScenarioSet`  
   某 profile 若产生了 evidence，还会有 `<digest>.json`

`ompArtifact` 经常大于 1MiB。没有无后缀 blob、只有 bundle JSON 的 PR 不能进 validate。

### 5.4 读取派生状态（不要口算）

```bash
gh api "repos/KunoLu/KPi/contents/plugins/omp-sbtd/validation/p0/compatibility-ledger.v1.json?ref=$PR_HEAD_SHA" \
  --jq .content | base64 -d | python3 -c '
import json,sys
doc=json.load(sys.stdin)
for e in doc.get("entries",[]):
    print("overall", e.get("overallOutcome"))
    print("plugin", e.get("pluginVersion"), "omp", e.get("ompVersion"))
    print("bundle", e.get("provenance",{}).get("attestationBundleLocator"))
    print("subjects", e.get("provenance",{}).get("subjectDigests"))
    for name, profile in (e.get("profiles") or {}).items():
        print(name, profile.get("outcome"), profile.get("blockedReason"), profile.get("evidenceTrust"))
'
```

第一次成功合入记录：

- `overallOutcome` = `eligible`
- Plugin `0.1.0-rc.12` × OMP `17.3.5`
- 三个 profile `outcome=blocked`，`evidenceTrust=missing`
- 不是 `certified`，也不是 `incompatible`

`eligible` 可以合入。`certified` 必须等第 8 节 Host Contract / 三 profile 全绿之后另写。

---

## 6. 成功路径：受信任 ledger-validate

### 6.1 从 `main` 派发

必须带三个输入，缺一不可：

```bash
gh workflow run omp-compatibility-ledger-validate \
  --repo KunoLu/KPi \
  --ref main \
  -f prNumber=$PR_NUMBER \
  -f expectedHeadSha=$PR_HEAD_SHA \
  -f certificationRunId=$CERT_RUN_ID
```

`$PR_HEAD_SHA` 必须是 PR 此刻的完整 head。head 若在派发后被 force-push，validate 会 fail closed。

```bash
gh run list --repo KunoLu/KPi \
  --workflow omp-compatibility-ledger-validate \
  --limit 1 \
  --json databaseId,status,url,headSha
```

记下 `$VALIDATE_RUN_ID`。打开该 run。

### 6.2 第一次环境审批（pending status）

成功顺序：

1. `Verify bot PR identity (read-only)` → success  
2. `Write pending status (Status App only)` → **Waiting**（环境 `omp-compatibility-ledger-status`）

按 **§2.1** 批准环境 `omp-compatibility-ledger-status`。有 ego-browser 用 2.1.2；没有则用 2.1.1（网页）。


成功后 pending job 会向 `$PR_HEAD_SHA` 写 context `omp-compatibility-ledger-validate` = `pending`。


### 6.3 等待内容校验

`Validate ledger content (read-only, never executes PR head)` 必须 **success**。

该 job 会：

- 只通过 API 读 PR-head 的 ledger / catalog / evidence  
- 用 raw Contents 拉取每个新 subject（含 >1MiB）  
- `sha256sum` 必须等于 ledger digest  
- `gh attestation verify` 使用第 2 节的 `--bundle` + `--cert-identity`

不要把这个 success 说成 Plugin 已 `certified`。它只证明：**这份 ledger 更新的 attestation 与 subject 字节受信**。

### 6.4 第二次环境审批（final status）

内容校验结束后，`Write the final status (Status App only)` 会再次 Waiting，**还是**环境 `omp-compatibility-ledger-status`。

再按 **§2.1** 批一次（ego 或网页）。两次缺一不可。



成功时整 run `conclusion=success`，PR 上 context `omp-compatibility-ledger-validate` = `SUCCESS`。

```bash
gh run view $VALIDATE_RUN_ID --repo KunoLu/KPi --json status,conclusion,url
gh pr view $PR_NUMBER --repo KunoLu/KPi \
  --json mergeable,statusCheckRollup,url
```

---

## 7. 成功路径：合入 ledger

### 7.1 合入条件

同时满足才合：

- validate run success  
- status `omp-compatibility-ledger-validate` = SUCCESS  
- PR 仍指向当初的 `$PR_HEAD_SHA`  
- 发布负责人明确这是 **ledger 合入**，不是 npm 发布，也不是 `certified`

`eligible` / `partially-verified` / `certified` 都可以是合法合入（按派生规则）。第一次成功是 `eligible`。

### 7.2 合入

solo-owner 仓库在 `REVIEW_REQUIRED` 时由发布负责人 admin merge。不要 squash 掉 attestation 与 evidence 的对应关系以外的约束；当前成功记录使用 merge commit。

```bash
gh pr merge $PR_NUMBER --repo KunoLu/KPi --merge --admin
```

合入后：

```bash
git fetch origin main
git log -1 --oneline origin/main
```

`main` 上应出现 ledger / evidence。Plugin tarball 与 version 不变。

### 7.3 被替代的旧 ledger PR

若仍有更早、缺 subject 字节、未能通过现行 validator 的 bot PR，关闭并注明被本 run 替代。不要合那些 PR。

---

## 8. 后续步骤（成功执行后再写入）

下面都还没有一份「已成功执行」的操作记录。有成功 run 之前只留标题和写入条件，不要把计划或失败草稿写成步骤。

### 8.1 Host Contract / Runtime Capability 完整探测 → 第一次 `certified`

写入条件：受信认证 run 里 `runtimeCapabilityProbe`、`commandSurface`、`hostEventSurface` 均为 `passed` 或允许的 `passed-with-diagnostics`，`allProfileEvidenceTrust=verified`，`assessmentProvenance=verified`，ledger-validate success，且合入后公开派生为 `certified`。

写入内容应包括：Host 如何满足 `omp-extension-v1`、cell 不再因 SUBJECT_STALE / 缺 extension 而 blocked、三个 profile 的 evidence locator、`certified` entry 的 digest。

**不写入** `omp-plugin-host-acceptance.md`。那份文档的第 4 节四命令是发布 Gate，不能替代本小节。

### 8.2 新的 in-range OMP 精确版本，复用已发布 tarball

写入条件：用第 3.2 节 `newRuntime=` 成功认证某个新的稳定 17.x，且只更新 ledger、不发新 Plugin。

### 8.3 受信任 append-only revocation

写入条件：已有公开 `certified`（或其它当前状态）被受信 revocation successor 派生为 `revoked`，且历史 entry 仍在。

### 8.4 加宽 peer 的新 Plugin tarball（例如 rc.13）

发布、四命令、`next` tag 全部写在 [`omp-plugin-host-acceptance.md`](./omp-plugin-host-acceptance.md)。本手册只在该 tarball **已经 published** 之后，补「对新 tarball 跑第 3–7 节」的成功记录。未发布候选不要在这里写安装或 `supported`。

### 8.5 OMP 18 / out-of-range

现有 `<18` tarball 对 18 必须保持 `out-of-range`。只有加宽 peer 的新 tarball 认证通过并按 8.4 发布后，才另写一节。

### 8.6 已登录 Playwright 审批环境

写入条件：用 Playwright 接到**已登录 GitHub** 的浏览器，按 §2.1.1 的控件顺序完整批准至少一次认证环境和一次 ledger-status，且未点 Reject。把可重复脚本写入本节。未满足前不要把 Playwright 当默认替代。

### 8.7 `gh api` pending_deployments 审批环境

写入条件：用环境 reviewer 本人的 `gh`，对 Waiting run 调用 pending-deployments 列出环境 id 并以 `state=approved` 批准，且认证与 ledger-status 各至少成功一次。把命令写入本节。未满足前成功路径不得使用该 API。

---


## 9. 第一次成功执行记录（2026-08-26）

只记录最终成功闭环，供对照。以后复跑以第 3–7 节为准，不要复制过期 SHA 当输入。

| 项 | 值 |
|---|---|
| 认证 run | [`32970295741`](https://github.com/KunoLu/KPi/actions/runs/32970295741) |
| 认证时 `main` | `d5ec4e913676bfa6b2b976dd2378cbd63a790bea`（#13 subject 绑定已在） |
| 校验时 `main` | `c7ff9f54bd86fa19cbc5320fe30057435dd5ed80`（#15 raw fetch 已在） |
| 校验 run | [`32971768467`](https://github.com/KunoLu/KPi/actions/runs/32971768467) success |
| ledger PR | [#14](https://github.com/KunoLu/KPi/pull/14) head `09532391bec39bed0f38916e78d7a5b345504f8c` |
| 合入 | `3f9813a02df35150c88320ebccccad994e305641` |
| 单元 | `@kunolu/omp-sbtd@0.1.0-rc.12` × OMP `17.3.5` |
| 公开派生 | `eligible`（三 profile blocked / evidence missing） |
| 被替代未合入 | #12（缺 subject 字节） |
| 环境审批 | ego-browser 点 GitHub Review deployments → Approve and deploy（task space `kpi omp compatibility HITL`）；未使用 Playwright；未使用 pending-deployments API |
| npm | 未 pack、未 publish、未动 dist-tag |
| `certified` | 否 |

---

## 10. 操作检查清单

- [ ] `origin/main` 含第 2 节全部前置
- [ ] 从 `--ref main` 派发 `omp-compatibility-certification`
- [ ] 按 §2.1 审批 `omp-compatibility-certification`（Approve，不是 Reject；有 ego 用 2.1.2，否则网页 2.1.1）
- [ ] 认证 run success，且出现 `omp-compatibility/<runId>` bot PR
- [ ] PR 含 bundle JSON **和** 无后缀 subject blob（含可能 >1MiB 的 `ompArtifact`）
- [ ] 已读取 `overallOutcome`，未口算成 `certified`
- [ ] 从 `main` 派发 validate，三个输入与 PR head / 认证 run 一致
- [ ] 按 §2.1 审批 ledger-status 两次（pending + final）
- [ ] validate success，status context SUCCESS
- [ ] 合入后只增加 ledger/evidence，Plugin 身份不变
- [ ] 第 8 节未成功的项目仍是占位，未写成步骤


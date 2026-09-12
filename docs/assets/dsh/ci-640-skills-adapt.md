# 适配新 `640-skills` / 发 `dsh-sbtd` 新版前校验

适用包：`@kunolu/dsh-sbtd@0.1.0-rc.1`。manuals **钉死** `KunoLu/640-skills` **`1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`**。该 SHA 与某次本机 `640-skills` tip **无关**；本机 dirty / 更新的 clone 不能当 pin。

宿主钉仍是 `peerDependencies["@deepseek-ai/dsh"] = 0.1.1-rc.2`。现有 Actions 全是 `omp-*`。拟议独立门：`dsh-manuals-pin` 与（发版前）`dsh-host-compat`。禁止改 `omp-compatibility-*`。**本 PR 未入库** `.github/workflows/dsh-*.yml`（OAuth 缺 `workflow` scope）；未入库前不要 dispatch 这些名字，跑本页命令。

## 触发条件

出现任一情况即跑：

1. 准备把 manuals 从 `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630` 迁到新的 `640-skills` tag / commit。
2. 准备发 `@kunolu/dsh-sbtd` 新版本（bump `0.1.0-rc.1` 之后）。
3. `packages/dsh-sbtd/scripts/sync-manuals.sh`、`manuals/MANIFEST.json` 或 whitelist 有改动。
4. 拟议手动 `workflow_dispatch`：`.github/workflows/dsh-manuals-pin.yml`（**pending / 本 PR 未入库**）。未入库前跑 MANIFEST 断言 + t4 + `sync-manuals.sh`。

未触发：只评估上游 `dsh` 宿主、不动 manuals（走 [ci-dsh-host-compat.md](./ci-dsh-host-compat.md)）。

## 自动化门禁清单

| 门 | 命令 / Actions | 级别 | 期望 |
|---|---|---|---|
| MANIFEST SHA | 读 `packages/dsh-sbtd/manuals/MANIFEST.json` | **REQUIRED** | `source=KunoLu/640-skills`，`version=1.0.13`，`sourceRevision=f8aa0d7225a26c5e00b81d2f1b05121108e63630`（迁 pin 前必须仍是这组；迁 pin 的 PR 才改这三处并同步脚本常量） |
| sync-manuals | `packages/dsh-sbtd/scripts/sync-manuals.sh [SOURCE]` | **REQUIRED，失败即红** | SOURCE 的 `HEAD` 必须等于 pin SHA，否则 stderr `SHA mismatch: got … expected f8aa0d7225a26c5e00b81d2f1b05121108e63630` 且非 0。缺源、拷贝失败、checksum 失败同样非 0 |
| t4 单测 | `node --test packages/dsh-sbtd/test/t4-manuals.test.mjs packages/dsh-sbtd/test/t4-sync-exit.test.mjs` | **REQUIRED** | MANIFEST 与 dest sha256 一致；whitelist 目录一致；错误 SOURCE 非 0 |
| 全量单测 | `pnpm --filter @kunolu/dsh-sbtd test` | **REQUIRED（发新版前）** | `tsc` + 全部 `test/*.test.mjs`，含 FU4 `fu4-host-schema.test.mjs`（clarify/spec/tickets `output.schema` × `@deepseek-ai/dsh@0.1.1-rc.2`） |
| pack 含 `dist/` | 同宿主指南 | **REQUIRED（发新版前）** | tarball 含 `package/dist/`（T16 坑） |
| Actions | 拟议名 `dsh-manuals-pin` | **pending** | **本 PR 未入库**。意图：静态 MANIFEST + t4 + 对 pin SHA clone 后跑 `sync-manuals.sh`，工作树 `manuals/` 必须仍干净。不依赖 `@deepseek-ai/dsh` registry。有 `workflow` scope 后再推 YAML |

脚本常量必须与 MANIFEST 一致：

```text
PINNED_REVISION=f8aa0d7225a26c5e00b81d2f1b05121108e63630
PINNED_VERSION=1.0.13
SOURCE_ID=KunoLu/640-skills
```

本地（SOURCE 必须已经是 pin SHA，不要拿本机 tip）：

```bash
# 用本机 640-skills 且 HEAD 不是 pin → 必须红
packages/dsh-sbtd/scripts/sync-manuals.sh /path/to/wrong-tip   # 期望非 0

# 正确：省略参数让脚本自己 clone 到 pin，或传入已 checkout 该 SHA 的目录
packages/dsh-sbtd/scripts/sync-manuals.sh
git diff --exit-code -- packages/dsh-sbtd/manuals
```

迁新 tag 时：先改 `sync-manuals.sh` 的 `PINNED_*`，再跑脚本生成新 MANIFEST，再改 t4 测试里的 PIN 常量。不要手改 `manuals/**` 正文。

## 人工最少清单

发 **dsh-sbtd 新版** 前：只抽检 `dsh web` 审批弹窗（T16 step3 类）。不要把 plugin list、`/sbtd`、validate skip、e2e blocked 做成人工项。

逐步（与宿主指南相同，避免漏 `dist/` / 同版本 add）：

1. `pnpm --filter @kunolu/dsh-sbtd test` 绿；pack 含 `package/dist/`。
2. `dsh plugin --profile web remove @kunolu/dsh-sbtd`（同版本已装必须先 remove）。
3. `dsh plugin --profile web add <本轮 tarball>`。
4. `dsh web`，无 plan，编辑 `packages/.../src/...`（不要用 `frontend/src`）。
5. 期望弹窗 `kind=ask`，原因「尚未 sbtd_plan，请先调用 sbtd_plan。」

只迁 manuals、不发插件版：人工弹窗 **不必** 跑；自动化 MANIFEST + sync 红就必须停。

## PASS / FAIL 判定

**PASS**

- MANIFEST 三元组与脚本常量一致（未迁 pin 时必须仍是 `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`）。
- `sync-manuals.sh` 退出 0，且 `manuals/` 无意外 diff。
- t4 测试绿。
- 发新版前：全量 `test`（含 FU4）绿 + pack 含 `dist/` + 人工弹窗抽检通过。

**FAIL**

- 用本机 tip 当 pin，或 MANIFEST SHA 与脚本不一致。
- `sync-manuals.sh` 非 0（缺源 / SHA mismatch / copy fail / checksum fail）——失败即红。
- 手改 manuals 正文导致 dest sha256 ≠ MANIFEST。
- pack 无 `dist/`。
- 同版本未 remove 就 add，把「没变化」当成安装成功。

## 发版 / 不发版决策树

```
只是 640-skills 上游有新 tag，当前插件仍钉 1.0.13？
 ├─ 不迁 pin → 不发版。文档里记下「已知更新未跟」即可。
 └─ 要迁 pin → 适配 PR：改 PINNED_* + 跑 sync + 更新 t4 PIN。
      manuals 正文 / skill 契约是否改变插件行为？
       ├─ 否（checksum 换了但工具契约兼容）→ 可不 bump 功能语义；是否发 manuals-only 版本由发布人决定，默认可不发。
       └─ 是（skill 门禁/文案导致宿主行为不兼容）→ 适配代码 PR + bump 发版。先红单测不许发。

准备发 dsh-sbtd 新版？
 ├─ REQUIRED（MANIFEST+sync+全量单测+pack dist）有红 → 不发版。
 ├─ 仅宿主兼容、manuals 未变 → 走宿主决策树：兼容可不发，只更矩阵/文档/peerRange。
 └─ 全绿 + 人工弹窗抽检通过 → 才允许讨论 npm dist-tag（本仓库本次任务禁止 npm publish）。

advisory 宿主矩阵绿？
 └─ 不是唯一合主线门。omp-* 与 dsh-* 独立；矩阵不能替代 sync-manuals 红灯。
```

## 故障排查

| 现象 | 先查 |
|---|---|
| `SHA mismatch: got <本机 HEAD>, expected f8aa0d7…` | SOURCE 不是 pin。不要「先 pull 再 sync」。 |
| checksum-fail | 手改了 `manuals/` 或 sync 中途被打断。删改回，重新跑脚本。 |
| CI clone `640-skills` 失败 | YAML 入库后对该仓不可见时保持 `workflow_dispatch`；现在本机 `sync-manuals.sh`。不要把 omp workflow 当备用。 |
| t4 过、全量 test 不过 | FU4 / 宿主 registry 问题，转到宿主指南；不要放宽 MANIFEST。 |
| pack 无 dist | 发版前没 `tsc`。`files` 必须含 `dist/`。 |
| `frontend/src` 抽检无弹窗 | 不是生产路径。改用 `packages/**/src` 或仓库根下 `src/`。 |
| 想把 manuals 门挂到 `omp-compatibility-*` | 禁止。拟议独立文件是 `dsh-manuals-pin.yml`（本 PR **未入库**）。 |

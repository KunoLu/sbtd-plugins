# OMP Plugin RC 发布、稳定升级、安装与清理运行手册

## 1. 目的与适用范围

本手册是 `@kunolu/omp-sbtd` 从精确 tarball 到 npm Registry、再到消费者安装的唯一发布路径。

当前 RC 的精确 OMP 目标是 **`17.3.5`**。`@kunolu/omp-sbtd@0.1.0-rc.12` 已完成第 4 节全收（TUI 前 SHA-256 基线 + `section-4-write-check=passed`，2026-08-20）并发布到 `next`。可将 `17.3.5` 标为公开 `supported`（精确 peer + 本 RC 四命令）。不得写成 exact-host certified：该四命令结果只保留为 Command Surface 基线，rc.12 的兼容认证状态从 `eligible` 开始，不会被既有四命令结果自动提升为 `certified`。真实 `~/.omp` 不是第 4 节验收项。`17.2.9` 及更早结果是历史证据。

`@kunolu/omp-sbtd@0.1.0-rc.13` 已由受信 `omp-section4-publish-gate`（run `33052112414`，digest `b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185`）通过第 4 节并 HITL 发布到 `next`。tarball-bound peer 为 `>=17.3.5 <18`，dev/lock 保持精确 `17.3.5`。可将 `17.3.5` 标为对该 RC 的公开 `supported`。不得标 `certified`；catalog 准入后无受信 profile 通过，公开兼容状态从 `eligible` 开始。候选 envelope tarball `61610988…f9c7` 不是 Registry 身份，不得当作已发布物。更早退役 tarball 的本地 §4 结果不能转移。

本手册使用以下术语：

- **RC 候选**：一个不可变的 prerelease `.tgz`，由包名/版本和 SHA-256 标识。
- **四命令验收**：受信 `omp-section4-publish-gate` workflow 对精确 tarball SHA-256 digest 的非交互四命令运行时验收（见第 4 节）。本机 TUI 四命令只是可选对照，不单独授权发布。
- **Stable promotion**：从一个已发布 RC 创建 stable tarball 的独立产品决定；它不是只改 npm tag。
- **P0 conformance evaluator**：`scripts/p0` 的技术、包、兼容性和 Value Study 工具。它保留为内部质量与研究工具，不是 npm RC 或 stable 发布授权。
- **published（已发布）**：Registry 上不可变的精确版本身份（版本号 + tarball 摘要）。npm tag（`next`、`latest`）只是发现输入，tag 移动不改变已发布身份。
- **installable（可安装）**：由该精确 tarball 声明的 peer 依赖决定的安装资格。已发布 rc.12 的 peer 精确为 `17.3.5`；已发布 rc.13 声明 `>=17.3.5 <18`（OMP 18 out-of-range）。可安装不等于已认证。

- **certified（已认证）**：只由受信任的 Runtime Capability、Command Surface、Host Event Surface 三个 profile 证据与可信 provenance 派生的公开兼容状态；缺失受信证据的已发布 in-range target 从 `eligible` 开始。认证状态整体按固定优先级 `out-of-range` → `revoked` → `incompatible` → `certified` → `partially-verified` → `eligible` 唯一派生。认证不是、也永不成为 npm 发布授权输入。

Plugin SemVer 独立于 OMP SemVer。支持 OMP `17.3.0` 不要求 Plugin 使用同样的版本号，也不自动触发发布。

### 1.1 与兼容认证 runbook 的分工

本章只覆盖 RC / stable **发布**与第 4 节四命令验收。仓库内受信任 CI 三 profile 认证、subject 绑定、ledger bot PR、环境审批与合入公开 ledger，见 [`omp-plugin-compatibility-certification-runbook.md`](./omp-plugin-compatibility-certification-runbook.md)。

第 4 节四命令通过可以把精确 OMP 标为公开 `supported`，并作为 Command Surface 基线保留；不能派生 `certified`，也不是 Host Contract / `omp-extension-v1` Runtime Capability 完整探测。后者成功执行后写入认证 runbook 第 8.1 节，不写入本章。


## 2. 不可变身份、隔离与保密

每个发布候选必须记录并仅使用：

1. 冻结源码 revision；
2. `@kunolu/omp-sbtd@<version>`；
3. 精确 `.tgz` 的 SHA-256；
4. 四命令验收的消毒结论；
5. 发布后的 Registry metadata 和下载 tarball 身份复核结论。

任何 payload、包版本或 tarball 字节变化都会形成新候选；不得覆盖、重打或修改已发布版本。

不得在参数、报告、提交、聊天记录或仓库中写入 token、OAuth URL、Cookie、账户资料、Registry 凭据、profile 内容、原始 OMP transcript、Provider 响应、model output 或 PII。

四命令验收只允许：

```text
/sbtd help
/sbtd status
/sbtd report
/sbtd onboard plan
```

不要执行 `/sbtd on`、`/sbtd off`、`/sbtd onboard init`、`/sbtd onboard reset` 或 `/sbtd onboard init-projects`。`/sbtd onboard plan` 可以显示拟议的 `action: "write"`，但不得 Apply。

不得删除 `~/.omp`、默认 profile、Session 历史、全局 AGENTS、既有项目、Plugin 源码或 `dist/`。不要删除或打印仓库 `.env`。

## 3. RC 发布门槛

一个 RC 可以发布，当且仅当：

- tarball 是 `@kunolu/omp-sbtd` 的 SemVer prerelease；
- tarball SHA-256 已记录，且本轮只使用该 tarball；
- 该精确 tarball 的 SHA-256 digest 已在受信 `omp-section4-publish-gate` workflow 通过第 4 节四命令验收（本机 TUI 对照不单独授权发布）；
- npm Registry 明确表示该精确版本不存在；
- 发布仅使用 `next`，绝不使用 `latest` 或其他 tag。

以下项目不是 RC 发布前置条件：外部 host/profile harness、真实宿主认证、Runtime Capability / Command Surface / Host Event Surface 三个兼容认证 profile 的任何结果、28.4 Host、Value Study、独立 Judge、P0 EvidenceStore 的 `rc-eligible`/`ready`、迁移方案里的 **CI 晋升**、或额外 Release Readiness 记录。

这些工具仍可在产品质量、兼容性研究或后续调查中使用；它们不得阻断符合本节条件的 RC npm 发布。三个 profile 的通过、缺失、阻断或失败只派生独立的公开兼容认证状态（见第 1 节术语），不参与 npm 发布授权，也不要求重新发布已通过的 tarball。CI 未接入只表示 portable projection **未晋升**，不是手册第 3 节的第六条发布条件。

### 3.1 准备精确 RC tarball

在冻结 revision 上创建 tarball。发布脚本会再次验证包名、prerelease 版本、`next` tag 和 Registry 可用性。

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
PACK_ROOT="$REPO_ROOT/.tmp/kpi-p0/rc-pack"
mkdir -p "$PACK_ROOT"

pnpm --filter @kunolu/omp-sbtd pack --pack-destination "$PACK_ROOT"
set -- "$PACK_ROOT"/*.tgz
[ "$#" -eq 1 ] && [ -f "$1" ] || {
  printf '需要且只能有一个 RC .tgz\n' >&2
  exit 1
}
TARBALL="$(realpath "$1")"
shasum -a 256 "$TARBALL"
```

不要在候选准入后重建 tarball。若打包字节或版本改变，废弃该候选并重新执行本手册。

## 4. 精确 tarball 四命令验收（受信 Gate）

这是 RC 和 stable 的唯一运行时发布验收。它验证包可由钉死的 OMP `17.3.5` 加载并注册四个只读命令；不宣称 Windows、其他 OMP 版本、Provider、模型或写入操作已经验证。四命令通过前不得把 `17.3.5` 标为公开 `supported`。

唯一有效的第 4 节证据是受信 `omp-section4-publish-gate` GitHub Actions workflow 对**该精确 tarball SHA-256 digest** 的通过：

- 仅 `workflow_dispatch`，仅 `KunoLu/KPi` + `refs/heads/main`；其他仓库、ref 或事件 fail closed。
- workflow 从不可变 main commit **恰好 pack 一次**，全部后续 job 只消费这一份 artifact 并复核 digest；本机 `.tmp` 包不是云端输入。
- `lock-and-cache` job 用 npm 生成诊断 `package-lock.json`（`integrity` 为 npm 写入的 SRI，禁止手写内容 SHA-256）并物化 content-addressed cache；`pluginTarballSha256` 独立于 lock SRI 记录。
- `section4` job 只用共享 npm-offline-v1 安装器（`npm ci --offline --ignore-scripts --no-audit`）安装 subject——禁止 bun、禁止无 lock 的 `npm install --offline`——随后通过共享 command-surface cell driver 对钉死的 OMP `17.3.5` `dist/cli.js` 非交互执行四命令，并以 Host 前后 SHA-256 清单做诊断写入对照（`section-4-write-check=passed`）。
- Host 无法 provision 或四命令未通过时，workflow 以明确 blockedReason fail closed；任何 job 都不许伪造通过。
- commit status `omp-section4-publish-gate` 绑定 commit SHA + tarball digest + 钉死 OMP + `installerGeneration`。
- 该 workflow **没有** publish job；发布仍是第 5 节的人工 HITL 流程，且只能发布 digest 通过的同一份 tarball 字节。

认证流水线的 Command Surface（或任何其他 CI 结果）**不是**第 4 节替代品，不参与 npm 发布授权。本机 TUI（第 4.1 节）只是可选对照，不能代替受信 Gate。本 Gate 也不宣称 OMP 18 兼容：18 属于新 Plugin 身份 + 加宽 peer 之后的另一条矩阵。

不要对从 `.tgz` 解出的目录执行 `omp plugin link`。该命令只创建 link/manifest，不解析 `package.json` 生产依赖；`omp plugin list` 和 `omp plugin doctor` 也不会导入扩展，因而不能证明 `/sbtd` 已注册。

### 4.1 本机 TUI 可选对照

本机 TUI 对照不复用受信 Gate 的结论；它只是发布负责人的本地交叉检查。在一次性隔离目录中，用与受信 Gate 同一 npm-offline-v1 安装器契约安装 subject：tarball 置于固定相对路径 `plugin.tgz`，诊断 `package-lock.json` 由 npm 生成（SRI 禁止手写内容 SHA-256），安装只跑 `npm ci --offline --ignore-scripts --no-audit`；禁止 bun，禁止无 lock 的 `npm install --offline`。

```bash
DIAGNOSTIC_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/kpi-omp-package-diagnostic.XXXXXX")"
PLUGIN_ROOT="$DIAGNOSTIC_ROOT/plugins"
PROJECT_ROOT="$DIAGNOSTIC_ROOT/project"
INSTALLER_ROOT="$DIAGNOSTIC_ROOT/installer"
test -f "$TARBALL"
mkdir -p "$PLUGIN_ROOT" "$PROJECT_ROOT"
REPO_ROOT="$(git rev-parse --show-toplevel)"
(
  cd "$REPO_ROOT/plugins/omp-sbtd"
  pnpm exec tsx scripts/p0/install-subject-plugin.ts lock-and-cache \
    --tarball "$TARBALL" --work-dir "$INSTALLER_ROOT"
  pnpm exec tsx scripts/p0/install-subject-plugin.ts install \
    --tarball "$TARBALL" --run-dir "$PLUGIN_ROOT" \
    --cache-dir "$INSTALLER_ROOT/cache" \
    --lock-file "$INSTALLER_ROOT/package-lock.json"
)
EXT="$PLUGIN_ROOT/node_modules/@kunolu/omp-sbtd/dist/extension.js"
test -f "$EXT"
```

启动 TUI **之前**必须在诊断根**之外**保存带 SHA-256 的文件清单。只有路径、没有哈希、没有对照的清单不能发现就地改写，不能只凭口述充当本机对照证据。

```bash
AUDIT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kpi-omp-section4-audit.XXXXXX")"
python3 - "$DIAGNOSTIC_ROOT" "$AUDIT_DIR/pre-tui.manifest" <<'PY'
import hashlib, os, sys
from pathlib import Path
root = Path(sys.argv[1])
out = Path(sys.argv[2])
rows = []
for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
    dirnames.sort()
    for name in sorted(filenames):
        path = Path(dirpath) / name
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows.append(f"link {rel}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"file {digest} {rel}")
out.write_text("\n".join(sorted(rows)) + "\n")
PY
test -s "$AUDIT_DIR/pre-tui.manifest"
```

在**操作者自己的终端**用下面的隔离环境启动 TUI。`HOME` / XDG / `PI_CODING_AGENT_DIR` 已指进诊断根，写入证明只覆盖该进程可见的诊断根；不要快照、读取或哈希真实 `~/.omp`（§2 禁止保留 profile）。监督仓库的 Agent/Orca 会话不要代跑这条 TUI，以免它改写真实 profile。

```bash
HOME="$DIAGNOSTIC_ROOT/home" \
XDG_CACHE_HOME="$DIAGNOSTIC_ROOT/cache" \
XDG_CONFIG_HOME="$DIAGNOSTIC_ROOT/config" \
XDG_DATA_HOME="$DIAGNOSTIC_ROOT/data" \
PI_CODING_AGENT_DIR="$DIAGNOSTIC_ROOT/agent" \
omp --cwd "$PROJECT_ROOT" --extension "$EXT"
```

在启动的 OMP TUI 中只输入四条命令。全部出现并完成时，确认：

- 没有 Provider request；
- 没有 approval；
- 没有意外文件写入（见下方对照脚本）；
- 没有 `Failed to load extension`；
- 只保留 OMP 版本、tarball SHA-256、四项通过/阻断状态和非敏感失败码的消毒摘要。

退出 OMP 后，在删除诊断根之前对照基线。`plugins/`、`installer/` 与 `project/` 的既有文件不得被删除，哈希必须不变；`project/` 必须仍为空。**新增**常规文件只允许相对路径前缀为 `home/`、`agent/`、`cache/`、`config/`、`data/`。对照脚本通过即本机对照的「无意外文件写入」成立。不要把真实 `~/.omp` 列入通过/阻断条件。

```bash
python3 - "$DIAGNOSTIC_ROOT" "$AUDIT_DIR/pre-tui.manifest" "$AUDIT_DIR/post-tui.manifest" <<'PY'
import hashlib, os, sys
from pathlib import Path
root = Path(sys.argv[1])
pre = Path(sys.argv[2]).read_text().splitlines()
post_path = Path(sys.argv[3])
allowed_new = ("home/", "agent/", "cache/", "config/", "data/")
rows = []
for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
    dirnames.sort()
    for name in sorted(filenames):
        path = Path(dirpath) / name
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows.append(f"link {rel}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"file {digest} {rel}")
post = sorted(rows)
post_path.write_text("\n".join(post) + "\n")
pre_map = {}
for line in pre:
    kind, rest = line.split(" ", 1)
    if kind == "file":
        digest, rel = rest.split(" ", 1)
        pre_map[rel] = digest
    else:
        pre_map[rest] = kind
post_rels = set()
for line in post:
    kind, rest = line.split(" ", 1)
    if kind == "file":
        digest, rel = rest.split(" ", 1)
    else:
        digest, rel = kind, rest
    post_rels.add(rel)
    if rel in pre_map:
        if pre_map[rel] != digest:
            raise SystemExit(f"in-place change: {rel}")
    elif not rel.startswith(allowed_new):
        raise SystemExit(f"unexpected new path: {rel}")
for rel in pre_map:
    if rel not in post_rels:
        raise SystemExit(f"missing baseline path: {rel}")
project = root / "project"
if project.is_dir() and any(project.iterdir()):
    raise SystemExit("project/ is not empty")
print("section-4-write-check=passed")
PY
rm -rf -- "$DIAGNOSTIC_ROOT"
rm -rf -- "$AUDIT_DIR"
unset DIAGNOSTIC_ROOT PLUGIN_ROOT PROJECT_ROOT EXT AUDIT_DIR
```

不要把 profile、原始 transcript、模型输出或诊断目录纳入候选证据。对照失败时不发布；修复后必须生成新的 tarball 并重新走受信 Gate。

## 5. 发布 RC 到 `next`

只在第 4 节通过后发布同一个绝对 tarball：

```bash
docs/deploy/publish-omp-sbtd.sh "$TARBALL" --tag next
```

脚本只接受 `@kunolu/omp-sbtd` prerelease tarball 和 `next`。它从仓库根 `.env` 的非空 `NPM_TOKEN=` 或继承的非空 `NPM_TOKEN` 取得凭据，凭据不作为参数、不被打印，也不写入报告。npm 权限和 2FA 由发布负责人控制。

发布前，脚本查询 Registry 的精确版本。只有明确 `E404` 才表示可用；网络、认证、Registry 错误或任何未知结果均阻断。发布后结果不明时，不得重试；先执行第 6 节的只读查询。

## 6. 发布后 Registry 身份复核

发布不是完成条件。读取 metadata，再下载精确版本：

```bash
npm view "@kunolu/omp-sbtd@$PLUGIN_VERSION" dist --json --registry=https://registry.npmjs.org/
mkdir -p "$CANDIDATE_ROOT/registry-download"
npm pack "@kunolu/omp-sbtd@$PLUGIN_VERSION" \
  --pack-destination "$CANDIDATE_ROOT/registry-download"
```

`npm pack` 必须产生唯一 `.tgz`，否则为 `blocked`。令其路径为 `$REGISTRY_TARBALL`，比较：

```bash
shasum -a 256 "$REGISTRY_TARBALL"
shasum -a 1 "$REGISTRY_TARBALL"
printf 'sha512-'
openssl dgst -sha512 -binary "$REGISTRY_TARBALL" | openssl base64 -A
printf '\n'
```

下载文件 SHA-256 必须等于本地 `$TARBALL` SHA-256；SHA-1 必须等于 metadata `dist.shasum`；`sha512-...` 必须等于 `dist.integrity`。只保留消毒后的 Registry、version、tag、三个摘要和结论。

下载身份不匹配、零个/多个 tarball 或 Registry 查询失败时，停止；不能覆盖、重发或 retag。修复只能发布新 RC。

## 7. Stable promotion

Stable 是独立产品决定，必须来自一个已发布的目标 RC，而不是从旧 RC 累积证据。

发布负责人必须记录一个不含凭据、profile、原始用户数据或模型输出的 stable-promotion 摘要，确认：

1. 目标 RC 已发布至少七个自然日；
2. 至少一位生产用户已使用该精确 RC；
3. 没有未解决的 blocking 或 high-severity 生产问题；
4. stable tarball 已重新完成第 4 节四命令验收（受信 Gate）；
5. stable 版本和 Registry tag 已按单独发布 runbook 明确批准。

任何新 RC 都开始新的七日观察期。P0 Value Study、外部 host harness 和 RC-to-stable 字节等价不是 stable promotion 前置条件。

## 8. 消费者安装与卸载

消费者先核对 OMP 版本。公开支持目标是 **`17.3.5`**。`0.1.0-rc.12` 已按本章第 4 节全收，故该版本可标公开 `supported`（见 §1）。不得写成 exact-host certified。

```bash
omp --version
omp plugin install @kunolu/omp-sbtd@<published-version>
omp plugin list
omp plugin doctor
```

需要 project scope 时使用：

```bash
omp plugin install --scope project @kunolu/omp-sbtd@<published-version>
omp plugin list
```

开启新的 OMP Session，并执行：

```text
/sbtd help
```

消费者验证安装发现与命令注册，不替代第 4 节的发布前验收。卸载前从 `omp plugin list` 复制准确的已安装标识和作用域；例如：

```bash
omp plugin uninstall --scope project @kunolu/omp-sbtd@<published-version>
omp plugin list
```

只有确认不影响其他项目时才使用 `--scope user`。未知标识或作用域时不要卸载。

## 9. 可选诊断与 P0 conformance

`omp --extension` 可帮助开发者调试工作区编译工件，但不安装 Registry tarball，不能替代第 4 节：

```bash
DIAGNOSTIC_PROJECT="$(mktemp -d "${TMPDIR:-/tmp}/kpi-omp-extension-diagnostic.XXXXXX")"
EXT="$(realpath plugins/omp-sbtd/dist/extension.js)"
test -f "$EXT"
omp --cwd "$DIAGNOSTIC_PROJECT" --extension "$EXT"
```

Docker package-install smoke、`check-compatibility`、P0 candidate evidence、Value Study 和 independent Judge 都可提供额外质量信息，但不是 RC 或 stable 发布门槛。它们不得将开发工件、旧 tarball、host/profile 结果或实验性 Runtime 结果伪装成当前精确候选的四命令验收。

## 10. 失败、回退与清理

- 发现 tarball、版本、Registry 身份或四命令验收不匹配：停止并建立新 RC；不覆盖、不重发、不移动既有 tag。
- 发布前回退：还原本地源码和丢弃本轮一次性诊断目录即可。
- 发布后回退：发布一个新的纠正 RC；npm 版本不可变。
- 保留历史 evidence 作为其原始 source snapshot 的历史事实，但不得把它转写为当前候选证明。
- 清理只针对本轮通过绝对路径验证的 `.tmp`、第 4 节诊断/审计目录，或第 12 节自造诊断根 `$HOME/kpi-omp-host`；绝不删除全局 Bun `omp`、`~/.omp`、默认 OMP 状态、候选 tarball 或既有 evidence。

## 11. RC 发布检查清单

- [ ] 只有一个精确 prerelease tarball，且已记录 SHA-256。
- [ ] 已在隔离目录中从该 tarball 解析依赖并完成四个只读命令。
- [ ] 诊断根外 SHA-256 基线对照脚本通过；无 Provider、approval、意外写入。
- [ ] tarball 是 `@kunolu/omp-sbtd` prerelease；没有使用 `latest`。
- [ ] 发布脚本确认 Registry 的精确版本明确 `E404`。
- [ ] 发布只执行一次；未知结果先只读查询，不重试。
- [ ] 已复核 metadata、下载 tarball SHA-256、SHA-1 和 integrity。
- [ ] 报告不含凭据、profile、原始 transcript、模型输出或 PII。

## 12. 已撤回：会话内自造 `KPI_OMP_HARNESS_PATH` 不得用于认证

本节记录一次被撤回的 4 步配方，供后续 Agent 指引时对照，**不是**可执行的 M4 / 28.4 / RC 授权步骤。

`KPI_OMP_HARNESS_PATH` **不是** `command -v omp`，也不是全局 Bun 安装的 `omp`。P0 adapter（`createAuthorizedHostCommandAdapter`）只把 `PATH` 和可选的 `KPI_OMP_COMPAT_AGENT_DIR` 传给子进程。因此：

- 不能把该变量指到 `plugins/omp-sbtd/scripts/p0/authorized-omp-rpc-harness.ts`；父进程里的 `export KPI_OMP_RUNTIME_*` 到不了子进程。
- 不能复制 `~/.bun/bin/omp` 到版本化目录（Bun 模块解析会坏）。
- 不能用 symlink 充当 `$RUNTIME_ROOT/<version>/bin/omp`（harness 拒绝 symlink）。
- 聊天里的「授权」、按 Agent 配方现做包装器、再重启 Orca 探测，都不是独立授权 Host（`LESSON-20260812`）。

第 9 节的 P0 harness 仍是可选研究工具，**不是** RC / stable 发布门槛，也**不能**把自造包装器升格为 Agent Plugins 迁移方案第 28.4 节 exact-host 证据。

### 12.1 曾误传的 4 步与更正后效力

| 步 | 曾误传的内容 | 更正后效力 |
|---|---|---|
| 1 | 建 `$HOME/kpi-omp-host/runtime/17.3.5/bin/omp` 普通文件，`exec` 已安装的 `omp` | 仅本机诊断。不是 M4 Host。 |
| 2 | 把认证 tarball 解到 `$HOME/kpi-omp-host/plugin-…` | 仅本机诊断。**禁止** `rm -rf` 已有候选目录；若再做诊断，用带 tarball SHA-256 后缀的新目录，目录已存在则停止。 |
| 3 | 写 `$HOME/kpi-omp-host/kpi-omp-harness`，在包装器内写入 Runtime/model/process/plugin 身份后再 `exec` 仓库 harness | 仅本机诊断。会话内现做的包装器是自造 Host，不是事先存在的父进程授权包装器。 |
| 4 | `export KPI_OMP_HARNESS_PATH=…` 并重启 Orca/Agent 让会话探测 | **撤回。不要执行。** 不得把自造包装器注入 supervising 会话，不得探测为 authorized，不得把 28.4 Host 从 `not-run`/`blocked` 改成 passed。 |

独立授权包装器必须由发布负责人那套认证设施独立提供，不能靠本会话或下一会话现做。本手册不教如何制造它。没有该包装器时：第 4 节仍可按本章做 RC 验收。迁移方案第 28.4 节 Host 项为可选项，不阻断 M4 / M5 / 后续开发；未跑不得写成 exact-host certified。

### 12.2 本轮自造诊断根清理

若本机已按撤回配方创建了 `$HOME/kpi-omp-host`，默认删除这一棵树。不要删全局 Bun `omp`，不要删 `~/.omp`。

```bash
test -d "$HOME/kpi-omp-host"
rm -rf -- "$HOME/kpi-omp-host"
```

若操作者明确选择保留，只能标为**本机诊断目录**，不得写入仓库、不得当作 M4 / 28.4 / RC 资产，后续 Agent 不得探测或升格。

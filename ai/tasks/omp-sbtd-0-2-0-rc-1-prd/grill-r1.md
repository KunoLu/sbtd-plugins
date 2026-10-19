# Grill Round 1 — omp-sbtd 0.2.0-rc.1

Round 1 已全部锁定（Asia/Shanghai）：Q6 A（用户 2026-10-19 11:39）；Q1 A、Q2 A、Q3 A、Q5 A、Q7 A（11:43）；Q4 用户 11:44 选定 `>=18 <19`（替代原推荐 B）。已锁定决策（D1–D6、任务序列、任务 A CLEAN 门、回填/分支规则）不重问。

已核对、不再问：上游钉 v2.0.2 `1d82494`；先迁移后同步；D1 目标布局（sync 脚本、transform 与 overlays 进 `packages/omp-sbtd/scripts/` 与 `packages/omp-sbtd/upstream/`，钉与 manifest 进插件，`packages/sbtd-workflow-kit` 删除，sourceId 不变）；只发 `next`，`latest`（`0.1.0-rc.2`）不动；annotated tag + 双语 prerelease；任务 A 纯搬移（revision、transformVersion `p0-v3`、sourceId 均不变）；插件目录中文 README 文件名 `README_zh.md`（D6，同根先例，不用 `README.zh.md`）；每个任务 strict；每 PR 首 commit 回填上一行。

术语对齐：本轮「迁移」指 D1 的 kit 投影/生成逻辑搬进 `packages/omp-sbtd` 并删除 `packages/sbtd-workflow-kit`；「同步」指任务 B 把上游钉从 `f8aa0d7…`（v1.0.13）升到 `1d82494…`（v2.0.2）。两者不是同一件事，顺序已锁（D2）。

---

**Q1** v2.0.2 的 5 个 Python 依赖的预检与失败行为？实测上游 `1d82494:sbtd-workflow-onboard/requirements.txt`：`jsonschema>=4.20,<5`、`PyYAML>=6.0.3,<7`、`markdown-it-py>=4,<5`、`tomlkit>=0.13.2,<1`、`cryptography>=43,<50`。上游 v2.0.2 实测 fail-closed（本机 `/workspace/640-skills` clone 核对 `1d82494`）：`sbtd_migration.py:589-596` import cryptography 失败即 `_fail("validator-unavailable", …)` 中止（`:140-148` 依赖版本枚举缺失同样 validator-unavailable）；`sbtd_upgrade.py:1272-1284` `_require_isolated_dependencies()` 在隔离解释器（`python -I -B`）里 import 全部 5 依赖（yaml、jsonschema、markdown_it、tomlkit、cryptography），失败即 `_fail("isolated-dependencies-unavailable", …)`，plan/execute 等 4 个入口（:1298、:1388、:2369、:2558）都先过这道闸。上游 `assets/` 自带 `routing-approval.pub` 与 `runtime-lineage.pub` 两个签名公钥：任何验签路径缺 cryptography 必须拒绝运行，永不跳过验证。现行嵌入 kit 只带 `scripts/onboard.py`（stdlib），由 `src/onboard/python-runtime.ts` exec 系统 Python；上游 `1d82494` 的 `onboard.py` 及其直接依赖（`graft_runtime`、`onboard_arguments`）实测仍为纯 stdlib，不需要这 5 个包。

- A. 对齐上游 fail-closed：需要 5 依赖的入口执行前做隔离预检（同上游 `_require_isolated_dependencies` 方式），预检失败即拒绝运行——结构化报错（缺失包清单 + 手动安装命令），不自动 pip install、不降级 skipped；验签路径缺 cryptography 一律拒跑，永不跳过验证。允许降级为 skipped 的普通入口逐个列出：**无**。（`onboard.py` 及其 stdlib 依赖链不 import 5 依赖，属正常运行，不算降级。）
- B. 预检失败全部结构化降级为 skipped + 缺失包清单 + 手动安装命令，不拒跑（即本文件修订前的旧推荐；与上游 fail-closed 冲突，验签路径会被静默跳过）。
- C. onboard 时自动在项目级 `.venv` 里 `pip install -r requirements.txt`（钉版本 + 哈希校验），失败再拒跑。
- D. npm 包内 vendor 打包 5 个依赖的 wheel，安装时离线解包。

推荐 A。理由：上游 v2.0.2 实测就是 fail-closed（上述行号），插件降级成 skipped 会弱于上游语义；上游自带两个签名公钥，skip 验签等于静默放弃供应链验证，不可接受；A 仍不自动写用户环境，行为与上游一致、可预期；B 的「不拒载」在验签场景直接违反上游不变量；C 引入静默网络安装与对用户项目的写入；D 让 tarball 携带平台相关 wheel，SBOM 与 pack 清单急剧膨胀。

> 锁定：✅ 已锁定 **A**（用户 2026-10-19 11:43，Asia/Shanghai）。

---

**Q2** v2.0.2 新增的 33 个 scripts 与 `assets/` 的清点/收录策略？实测 diff（f8aa0d7→1d82494，`sbtd-workflow-onboard/`）：`scripts/` 从 1 个 `onboard.py` 增至 33 个 `.py`（32 个新增，含 `sbtd_upgrade*`、`sbtd_migration*`、`sbtd_cleanup*`、`sbtd_graft_*`、`sbtd_task_*` 等，互相 import）；新增顶层 `assets/` 9 文件（`graft-build-policy.json`、`graft-hook-entry.mjs`、`graft-instructions.txt`、`migration-legacy-ownership.json`、`migration-local-ignore.txt`、`migration-paused-agents.txt`、`routing-approval.pub`、`runtime-lineage.json`、`runtime-lineage.pub`），外加 `onboard-contracts.schema.json`、`upgrade.schema.json`、`requirements.txt` 与 `templates/skills/sbtd-task/` 8 文件。现行 `omp-distribution-map.yaml` 是逐文件决策（207 include / 174 omit / 11 replace），没有目录级规则。

- A. 沿用逐文件决策：`scripts/` 33 个 `.py` 全 include（互相 import，部分收录会让 onboard 运行时才 ImportError）；`assets/`、两个 schema json、`requirements.txt` 逐文件审，按「OMP 投影是否有消费方」逐个 include/omit 并写 reason；`sbtd-task` 模板 8 文件随模板树收录。
- B. 开目录级规则：`scripts/` 与 `assets/` 整目录 include，map 只写 omit 例外。
- C. 只 include 现行投影已消费的路径（`onboard.py` 及其直接 import），其余 scripts/assets 一律 omit，等消费方出现再补。

推荐 A。理由：B 给 distribution map 引入第二套约定（现行全部是显式逐文件，check-generated 按文件比对）；C 会把 `sbtd_upgrade_cli.py` 这类入口与其 30 个协作模块切开，onboard 在用户使用时才炸，违背「同步后可用」；A 与任务 B 锁定的「逐文件决定是否收录」一致，且 33 脚本作为一个 Python 包整体收录是可验证的最小单元。

> 锁定：✅ 已锁定 **A**（用户 2026-10-19 11:43，Asia/Shanghai）。

---

**Q3** D1 已锁定粗布局（sync 脚本、transform 与 overlays 进 `packages/omp-sbtd/scripts/` 与 `packages/omp-sbtd/upstream/`，钉与 manifest 进插件，删除 kit 包），剩下的细节只有：`scripts/` 与 `upstream/` 内部的确切子布局，以及 `docs/spec/sbtd-workflow-kit/` 去哪？现状：构建管线是 `pnpm --filter @kunolu/sbtd-workflow-kit check-generated && node scripts/embed-kit.mjs`，embed 通过 `import.meta.resolve("@kunolu/sbtd-workflow-kit/generated-omp/manifest.json")` 找投影产物再拷进 `packages/omp-sbtd/kit/`；kit 包内有 `src/`（sync-upstream、omp-projection、agent-plugin-projection、check-generated、generate）、`vendor/`、`omp-distribution-map.yaml`、`overlays/`、`omp-overlays/`、`upstream.lock.json`、`features/`、`test/`；`packages/omp-sbtd/scripts/p0/cli.ts` 有 4 处 `kitRoot: packages/sbtd-workflow-kit`。`docs/spec/sbtd-workflow-kit/{backend,frontend}` 与既有 `docs/spec/omp-sbtd/{backend,frontend}` 结构同名。

- A. `scripts/` 放薄入口（sync-upstream、check-generated、generate 等 CLI 包装，与既有 `scripts/embed-kit.mjs`、`scripts/p0/` 并列）；投影/生成实现与供应链资产全部进 `upstream/`：`upstream/src/`、`upstream/vendor/`、`upstream/omp-distribution-map.yaml`、`upstream/overlays/`、`upstream/omp-overlays/`、`upstream/upstream.lock.json`、`upstream/features/`、`upstream/test/`；投影产物仍先出 `generated-omp/` 再经 embed-kit 拷入 `kit/`（发布物布局不变）。`docs/spec/sbtd-workflow-kit/{backend,frontend}` 移到 `docs/spec/omp-sbtd/kit/{backend,frontend}`，避免与既有 backend/frontend 撞名。
- B. `scripts/` 容纳全部投影实现（`scripts/kitgen/` 子目录），`upstream/` 只放 vendor + lock + map + overlays；spec 落点同 A。
- C. 布局同 A，但 `docs/spec/sbtd-workflow-kit/` 原样保留目录名不动，只改仓内引用。
- D. `scripts/` 只放 sync 入口，check-generated/generate 也搬进 `upstream/` 内并以 `upstream/` 为 cwd；spec 移到 `docs/spec/omp-sbtd/upstream/{backend,frontend}`。

推荐 A。理由：任务 A 锁定「Move only」加字节级 CLEAN 门，薄入口重导出 + `upstream/` 整体承接是让 `npm pack --dry-run` 清单与逐文件 sha256 不变的最短路径；`upstream/` 单目录完整承接 kit 包内容（src/vendor/map/overlays/lock/features/test），与 D1「版本钉与 manifest 记录进插件」一一对应；B 在 `scripts/` 下再开 `kitgen/` 层，与 D1 的两目录粗布局不符；C 留下一个指向已删除包的 spec 目录名，正是任务 A 锁定要求同步更新的路径；D 改掉 check-generated 的 cwd 约定，CLEAN 门等价性更难证明。

> 锁定：✅ 已锁定 **A**（用户 2026-10-19 11:43，Asia/Shanghai）。

---

**Q4** omp 宿主的 peer 与 engines 范围？现状（`packages/omp-sbtd/package.json` 实测）：peerDependencies `@oh-my-pi/pi-coding-agent: >=17.3.5 <18`，devDep 精确钉 `17.3.5`，**无 `engines` 字段**（已核验）。npm 实测宿主 latest `18.12.2`；**云宿主/本机 `omp --version` 实测 `omp/18.11.1`，在现行 peer range 之外**——即实际运行环境已超出声明范围。dsh-sbtd 0.2.0-rc.1 的先例是 peer 与 `engines.dsh` 写同一范围 + 两行 REQUIRED 兼容矩阵；omp 宿主是否读 `engines` 标记**待核验**（本仓与 omp 文档未见先例）。

- A. 本 RC 不动宿主范围：peer 保持 `>=17.3.5 <18`、devDep 钉 `17.3.5`、不加 engines。后果如实列出：18.x 上安装出现 peer 警告（npm 严格 peer 时可 ERESOLVE）；除 17.3.5 外没有任何实测证据，而云宿主已在 18.11.1 上运行——声明范围把真实运行环境排除在外。
- B. peer 扩到 `>=17.3.5 <19`，devDep 仍钉下限 `17.3.5`，本 RC 以 18.11.1 真实宿主 smoke（插件加载、工具/hooks 注册、onboard 冒烟）为证据，不过则退回 A。
- C. peer 直接升到 `>=18 <19`，devDep 钉 `18.12.2`，放弃 17.x。
- D. 范围不动，但补 `engines` 字段声明 omp 宿主版本（字段名与宿主支持待核验）。

推荐 B。理由：云宿主实测已在 18.11.1，A 等于声明不支持正在使用的宿主且只有 17.3.5 一个点的证据；B 用真实宿主 smoke 提供 18.x 证据，成本远小于完整兼容矩阵，失败有明确的 A 退路；C 无理由放弃已验证的 17.3.5 下限；D 的字段语义待核验，加了可能是死声明。

> 锁定：✅ 已锁定（用户 2026-10-19 11:44，Asia/Shanghai，**替代原推荐 B**）：peerDependencies `@oh-my-pi/pi-coding-agent` 升为 `>=18 <19`（17.x 不再支持）；devDependency 精确钉 `18.11.1`（对齐真实宿主 smoke 版本）；omp 18.11.1 真实宿主 smoke 为 **HARD GATE，无退路**——任务 C 验收项、任务 E（发布）前置，失败则修到通过，不退回 A。原推荐 B 的 `>=17.3.5 <19` 与「失败退回 A」作废；B 选项文本仅保留评审历史。

---

**Q5** ROADMAP 归档文件名？独立 chore（不在主序列）：`git mv docs/prd/ROADMAP.md docs/legacy-archive/` 并同步更新 conformance-matrix 的 53 条 `source.path`。实测 ROADMAP.md 头部：「KPi 实施路线图（ROADMAP）／文档版本 0.7-draft／文档日期 2026-07-21」。归档命名先例：`docs/legacy-archive/dsh-sbtd-todo-through-2026-09-19.md`（描述性前缀 + 日期）。

- A. `docs/legacy-archive/kpi-roadmap-0.7-draft-2026-07-21.md`（现提案）：内容自描述（版本 + 文档日期），53 条 source.path 同步改。
- B. `docs/legacy-archive/ROADMAP.md`：只搬不改名。
- C. `docs/legacy-archive/kpi-roadmap-through-2026-10-19.md`：用归档日。
- D. `docs/legacy-archive/prd/ROADMAP.md`：保留原相对路径层级。

推荐 A。理由：0.7-draft 与 2026-07-21 取自文档自身头部，读者不看 git log 也能定位内容年代；B 在 legacy-archive 平铺命名空间下太裸，且丢掉版本信息；C 的归档日会被误读为内容日期（与 dsh-sbtd-todo 先例中「through-日期 = 内容截止日」的语义冲突，该文件内容并不 through 2026-10-19）；D 为一个文件新建一层目录，与现有平铺先例不一致。

> 锁定：✅ 已锁定 **A**（用户 2026-10-19 11:43，Asia/Shanghai）。

---

**Q6** 双语 README 的语言切换链接指向哪，`README_zh.md` 进不进 npm 包？事实（已核验）：npm 只展示包内 `README.md`（npm 自动收录，不占 `files`）；两个包的 `files` 均实测不含 `README_zh.md`（omp-sbtd `package.json:26-39`，dsh-sbtd `package.json:16-22`）；omp-sbtd 的 p0 release validator 在 `scripts/p0/release-validator.ts` 的 `inventoryDeclaredPackageContent`（约 5363-5375 行）硬编码发布物清单（含 `README.md`），新增打包文件须同步该清单与 SBOM；npm 上已发布版本的 README 不可变，而 `blob/main` 链接目标随 main 漂移；release tag `omp-sbtd-v0.2.0-rc.1` 在写 README 时尚不存在。

- A. 绝对链接钉 release tag（omp-sbtd：`https://github.com/KunoLu/sbtd-plugins/blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md`；dsh 侧行 G 钉 `blob/dsh-sbtd-v0.2.0-rc.2/...`），`README_zh.md` **不进包**：`package.json` files 与 p0 发布物清单均不动，任务 A 字节级 CLEAN 门不受影响。代价：写 README 时 tag 不存在，链接必须在打 tag 后、publish 前点击核验（已列入任务 E 步骤）。
- B. 钉 tag 链接 + 同时把 `README_zh.md` 打进包：须改 `package.json` files 与 p0 硬编码发布物清单，SBOM 面随之变化。
- C. 链接指 `blob/main`：链接永远可打开，但已发布 npm 版本的 README 不可变，目标内容随 main 漂移，与发布版本不再一一对应。
- D. 相对链接（`./README_zh.md`）+ 进包：npm 页面对未入包文件的相对链接无法解析，必须进包（代价同 B），且 GitHub 仓库页与 npm 页的解析基准不同。

推荐 A（已锁定，见下）。理由：npm 只渲染 `README.md`，中文读者经顶部链接跳 GitHub 即可，无需进包；不进包使 files、p0 清单、任务 A CLEAN 门三者零变化，是本 RC 最小 diff；B/D 进包要同时改 p0 硬编码清单与 SBOM 面；C 用可漂移目标换链接永活，违背行 R「EN/ZH 内容对应、版本钉正确」的验收；A 的「写时 tag 不存在」由任务 E 的「打 tag 后、publish 前点击核验」闭环。

> 锁定：✅ 已锁定 **A**（用户 2026-10-19 11:39，Asia/Shanghai）。

---

**Q7** dsh-sbtd 是否做双语 README + 仅文档 `0.2.0-rc.2` 发布（即 `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 G，已登记为「推荐，待用户确认」）？现状：`packages/dsh-sbtd/README.md` 为中文单语；`@kunolu/dsh-sbtd@0.2.0-rc.1` 已发布（dist-tags `next=0.2.0-rc.1`，`latest=0.1.0-rc.1`）。

- A. 做：独立 PR 把 `packages/dsh-sbtd/README.md` 改 EN 默认 + 新增 `README_zh.md`（D6 命名；顶部互相切换链接，钉 `blob/dsh-sbtd-v0.2.0-rc.2/...`，同 Q6 推荐 A），随后独立发布 docs-only `0.2.0-rc.2`（annotated tag `dsh-sbtd-v0.2.0-rc.2`、双语 prerelease、`npm publish --tag next`、`latest` 不动）；独立 PR、独立 release。
- B. 只做双语 README 的 PR，不发 `0.2.0-rc.2`；npm 页面保持已发布的单语 README，直到下一个功能版。
- C. 不做，dsh-sbtd 保持中文单语 README。

推荐 A（已锁定，见下）。理由：npm 上已发布版本的 README 不可变，B 只合 PR 不发版则 npm 页面长期停留在单语，与仓库状态不一致；A 的独立 PR + 独立 release 与本仓「每任务一 PR」规则一致，docs-only 补丁发布不动 `latest`、不动代码面；C 与根 README 双语、omp-sbtd 双语（D6 + 行 R）的整体方向不一致。

> 锁定：✅ 已锁定 **A（做）**（用户 2026-10-19 11:43，Asia/Shanghai）：dsh-sbtd 行 G 转 planned，独立 PR、独立 release；不进入 omp-sbtd 任务表。

**Round 1 选定：** Q6 A（11:39）· Q1 A · Q2 A · Q3 A · Q5 A · Q7 A（11:43）· Q4 用户 11:44 选定 `>=18 <19`（替代原推荐 B：devDep 精确钉 `18.11.1`；omp 18.11.1 真实宿主 smoke 为无退路硬门，失败修到通过）。

---

## DDD draft（Round 1 已锁定，待独立复审）

> 状态：draft，已反映 Round 1 锁定（PRD D7–D13）。grill Round 1 已全部锁定（用户 2026-10-19 11:39/11:43/11:44，Asia/Shanghai）；待按 book-ddd-distilled-modeling 输出独立 Boundary Review（Reviewy），经用户确认后才转 confirmed。

### 限界上下文

1. **omp 宿主**：拥有扩展加载（`omp.extensions`/`pi.extensions`）、peer 解析、工具/hooks 注册；版本范围是本插件的对外声明，不是本 RC 的适配对象。本 RC 声明范围按 D11 升为 `>=18 <19`（17.x 放弃；唯一实测点 18.11.1，真实宿主 smoke 为无退路硬门）。
2. **omp-sbtd 插件**：拥有运行时 zod 校验（`src/kit/manifest.ts`、`src/environment/accepted-skip.ts`）、onboard Python runtime、p0 验证脚本、嵌入 `kit/` 与 `skills/` 的只读消费；随包发布 `requirements.txt`，Python 依赖按 D8 fail-closed 预检（缺依赖即拒跑，不自动 pip install；验签缺 cryptography 拒跑）。
3. **kit 投影管线**（迁移后并入 omp-sbtd）：拥有 sync-upstream、omp/agent-plugin projection、check-generated；唯一 writer 是生成管线，`kit/` 产物只读嵌入。
4. **640-skills 上游供应链**：上游仓库拥有内容；`upstream.lock.json`（sourceId / resolvedRevision / transformVersion）与 distribution map（include/omit/replace-with-overlay）是供应链契约。
5. **p0 验证与 conformance**：conformance-matrix 拥有 source.path → evidence 的映射；ROADMAP 归档与包路径迁移都必须经它证明。
6. **npm 发布通道**：dist-tag `next`/`latest` 分离；`latest=0.1.0-rc.2` 是不可变基线。

### 关键术语

| 术语 | 含义 | 不得混用 |
|---|---|---|
| 迁移（migration） | D1：投影/生成逻辑搬进 omp-sbtd 并删除 `packages/sbtd-workflow-kit`；纯搬移，字节级 CLEAN 门 | 上游同步（sync） |
| 同步（sync） | 任务 B：上游钉 f8aa0d7（v1.0.13）→ 1d82494（v2.0.2），逐文件决定收录 | 迁移 |
| sourceId | `sbtd-workflow-kit-upstream`，供应链身份，迁移与同步均不变 | 包名 `@kunolu/sbtd-workflow-kit`（被删除） |
| distribution map 决策 | 逐文件 include/omit/replace-with-overlay + reason | 目录级规则（本 RC 不引入） |
| CLEAN 门 | 嵌入 `kit/`、`skills/`、manifest 哈希、pack 清单与逐文件 sha256 对 `4f7388c` 构建完全一致 | 「测试绿」子集 |
| fail-closed 预检（D8） | 需要 5 依赖的入口执行前隔离预检；缺依赖即结构化拒跑（缺失清单 + 手动安装命令）；验签缺 cryptography 一律拒跑；可降级 skipped 的普通入口当前为无 | 自动 pip install / 静默 skipped |
| README 切换链接（D7） | 钉 release tag 的绝对链接（`blob/omp-sbtd-v0.2.0-rc.1/...`），打 tag 后、publish 前点击核验；`README_zh.md` 不进 npm 包，files 与 p0 清单不变 | `blob/main` 漂移链接 / 进包改 files 与 p0 清单 |
| 宿主 smoke 硬门（D11） | omp 18.11.1 真实宿主 smoke（插件加载、工具/hooks 注册、onboard 冒烟）PASS 是任务 C 验收项、任务 E 前置；失败修到通过 | 退回旧 peer range 的退路（不存在） |
| 回填 | 每个 PR 首 commit 回填上一行的 PR/merge SHA/done 时间（+08:00） | 当行自填 |

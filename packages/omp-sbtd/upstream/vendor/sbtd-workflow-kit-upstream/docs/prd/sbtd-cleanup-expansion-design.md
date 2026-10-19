# SBTD 迁移后旧资产清理扩展设计

任务：`ai/tasks/sbtd-cleanup-expansion/task.md`，strict，分支 `sbtd-cleanup-expansion`。这是实现设计，不是实际 PC 清理授权或发布证明。

## 1. 用户要求与裁决

- migration apply、部署及 verify 成功后，Agent 主动列出真实清理候选并询问是否执行。回答是授权展示的范围；回答否不写清理目标，并说明以后可说「sbtd cleanup」「清理工作流」或明确同向意图。
- 这两个提示词是 Skill 路由，不是新全局 `sbtd` 二进制，也不是自动删除授权。Agent 读取 CLI 返回的标识，用户不必手抄 hash。
- 清理项目 `.trellis` 必须在项目根运行真实 `tl uninstall`；用户已了解风险并坚持该方式。不自动安装旧 CLI，不直接删除 `.trellis`，不绕过 vendor dirty/HOME 拒绝门。
- 其他目标：两个全局 Trellis Skill 目录、项目 `.gitnexus` 整目录、Codex/Claude/Kimi/OMP 全局 GitNexus MCP 条目、项目 AGENTS 的两类旧标记块。
- 两个 Skill 按常规目录、常规 `SKILL.md` 和 frontmatter name 识别，不要求来自 SBTD v1.0.15 的固定 checksum。plan 仍记录当前 checksum，用于删除前漂移检查。
- 延迟清理优先复用有效批次证据；确实没有证据时走新鲜检测。已知冲突、失败、篡改证据不能被 fallback 绕过。
- 一次确认覆盖展示的全部 GitNexus 候选；明确提醒全局 MCP 的移除会影响同一配置根下其他项目。CLI/npm 包、`~/.gitnexus` 全局数据、备份、无关 server 不在清理范围。

## 2. 三个职责

### 目标检测：`sbtd_cleanup_targets.py`

- 只检查明确项目根和已知全局配置位置，不递归搜用户的其他项目。
- 目录名不是 Skill 所有权证明；拒绝 symlink、无效 YAML、重复字段、错 identity。
- AGENTS 用 CommonMark 识别真正的 HTML comment，而不是代码块或句中示例。仅认精确的 `<!-- TRELLIS:START -->` / `<!-- TRELLIS:END -->` 与 `<!-- gitnexus:start -->` / `<!-- gitnexus:end -->`。
- 各类标记至多一个独立有序对；残缺、重复、嵌套/交错阻断。只删除两条标记行和其间内容；块外空行、自定义规则和 `graft:start/end` 围栏逐字节保留。
- JSON 严格拒绝重复键、非 object 和非法常量；TOML 经 tomlkit 解析。损坏的现有配置是 blocked，而不是“没有 GitNexus”。JSON 修改按现有项目约定规范化重排；TOML 保留相邻结构和注释。
- GitNexus server 按标准 key 或明确 CLI/package 命令识别，多个同文件候选合并为一次文件编辑。只移除展示过的 server，保留其他 server 的数据。

| host | 检测位置 |
|---|---|
| Codex | 默认 `~/.codex/config.toml` 以及显式 `$CODEX_HOME/config.toml` |
| Claude | `~/.claude.json`、`~/.claude/mcp.json`，以及显式 `CLAUDE_CONFIG_DIR/mcp.json` |
| Kimi | `~/.kimi-code/mcp.json`、其 `config.toml` 的 MCP 表、`~/.kimi/mcp.json` |
| OMP | `~/.omp/agent/mcp.json`、profiles 下各 `agent/mcp.json`、显式 `PI_CODING_AGENT_DIR/mcp.json`，以及现有 `active_omp_paths` 按 `PI_CONFIG_DIR` 和有效 profile 解析的配置 |

存在才读取；同一目录项的路径拼写别名去重，不合并不同硬链接目录项（原子替换只改变一个目录项）；不打印 server env、凭据或配置正文。

### Vendor 适配：`sbtd_trellis_uninstall.py`

- 在当前可验证的 Trellis CLI 实现上读取纯卸载 planner，和 `tl uninstall --dry-run` 相互核对。
- prepare 列出 `.trellis`、所有平台文件删除、结构配置 scrub、空目录修剪的完整 before/expected-after。工具 package 身份及能力可验证才支持；这与旧 SBTD 1.0.x 版本号无关。
- execute 在项目根运行实际绝对路径 `tl uninstall -y`。执行前重验 root、工具、完整计划和所有 before 状态，并备份全部 footprint。
- 非零退出可能已经部分改动，不能保证目录未变。逐资源测量 after，保存备份引用与真实失败；不回退直接删目录。
- 卸载自身会处理部分 AGENTS 标记，因此 fresh 引擎先备份所有候选原文，再根据 vendor after 更新同一文件的预期状态，最终基于原文完成两类标记删除，保留块外数据。

### 新鲜清理：`sbtd_cleanup_legacy.py`

```text
onboard.py cleanup-legacy --phase plan --projects-root <绝对项目根[,绝对项目根]> --backup-root <既有私有备份目录> [--global-skills-dir <Skills根>] --json
onboard.py cleanup-legacy --phase apply --plan <私有计划文件> --confirm-cleanup <plan_id> [--cleanup-receipt <前次回执>] --json
```

- plan 不修改清理目标；只在获授权的私有 evidence 目录写计划文件。计划包含精确路径、kind、当前 state、vendor footprint、blocked 原因。
- 项目根必须 canonical、非 symlink、非 HOME/文件系统根、相互不嵌套；vault 与项目/清理目标不能互相包含；所有候选路径也必须互不相同、互不嵌套，plan 与 apply 均在任何目标写入前检查。
- 新鲜计划/回执是独立的版本 1 私有 JSON，不伪装现有 `onboard-contracts.schema.json` 的 migration/recovery 文档。
- SHA 标识用于绑定展示与确认，**不是鉴权**。apply 必须重新验证限定的路径/kind/身份、HOME、配置发现、全部 before 状态；重算 hash 后偷换任意文件仍拒绝。
- Skills 根遵循现有解析器优先级：显式 `--global-skills-dir`、`AGENT_SKILLS_DIR`、受信已安装目录、平台默认值。仅 plan 接受覆盖参数；apply 始终读取封存根并重新检测身份及前态，不受新的 Skills 环境选择重定向。
- 有 blocked 项时不得写目标；先解决再生成计划。状态：planned / nothing-to-clean / cleaned 为 0，blocked 为 2，执行失败为 3。
- 删除前备份所有候选，逐资源执行，首个失败后停止；失败也保存实际累计回执。回执保存失败单独报告，不能宣称没有写过。
- 重试核对 plan_id、回执 digest、候选绑定、实际 backup 和 after；仅跳过已经证明成功且现状未漂移的资源。部分结果不明必须人工核对，不自动重放。
- fresh 回执当前不输入既有 migration recovery CLI。私有逐资源备份及 before/after 支持受控人工恢复，不能宣称已经提供自动 fresh recovery。

## 3. 与批次迁移整合

- 保留 migration plan/apply/verify/cleanup 四阶段和已密封历史文档。普通 init/reset/install-graft 不自动清理。
- 批次 Skill 退役从历史固定 checksum 改为身份证明与当前 before-state，消费者/恢复输入仍复验保留原件。
- 批次 `.trellis` 清理由同一 vendor 适配器执行，不再调用直接目录删除；vendor footprint 超出批次已授权资源时 fail closed，重新展示合法清理计划，不修改旧 manifest 扩权。
- 批次不增加新的 GitNexus/AGENTS selector。新增目标经 fresh plan 完成。Agent 展示批次与追加清理清单后取得合并确认；批次执行导致 fresh before 状态改变时必须重新规划、展示剩余清单并使用当前 plan_id。同一已确认流程内，若清单仅减少由绑定回执证明已完成的项、其余目标和效果不变，沿用原同意而不重复询问。新增目标或改变效果须重新确认；未知消失、用户改动、失败或冲突证据仍须停止调和。
- Bash/PowerShell 根安装器直接转发 `cleanup-legacy`，不进入普通安装菜单。

## 4. 行为验收与验证边界

| 场景 | 可观察结果 | 自动化边界 |
|---|---|---|
| migration verified 后确认/拒绝 | 主动展示；是才执行；否说明两个重触发词 | Skill 路由契约；不能以词串测试冒称真实 host 对话通过 |
| 其他 1.0.x Skill | 正确 identity 可删除；同名错 identity/符号链接保留 | 检测与批次 plan/verify/cleanup 测试 |
| 项目旧图、MCP、标记块 | 仅展示目标删除；邻居/Graft/块外保留 | fresh plan/apply 及真实 CLI 隔离 smoke |
| `tl uninstall` | 实际 vendor 命令、完整备份、副作用匹配 | vendor 适配测试和本机真实 CLI 隔离 smoke；fake runner 只证明指定异常分支 |
| 缺确认、篡改、路径逃逸、漂移 | 非零、目标零写入 | plan/apply 拒绝回归 |
| 中途失败、重试 | 回执包含真实 partial；不隐式重放成功资源 | 累计回执/备份验证 |

本仓禁止新 `.feature`；本表为持久行为规格，Python tests 为执行边界。真实 HOME 和用户提供的 keyboy-play 示例只用于只读核对，未授权清理。Native Windows/Linux 和真实交互式 host 验收需分别报告，不能用 macOS 本地测试替代。

## 5. 本轮审核修复契约

| 审核项 | 保持的不变量 | 回归行为 |
|---|---|---|
| R1：逻辑 Skills 根 | 物理共享根可合并，但实际选定 Skills 根的逻辑权限不得被宽 HOME 根替代；每个退役目录必须为它的直接子目录 | 同名同 frontmatter 的未选用户目录在重封操作后仍拒绝；合法默认/自定义根与原件续作保留 |
| R2：原先缺失路径 | vendor 启动前既检查现存资源，也检查封存的缺失路径仍不存在 | 备份期间在非待修剪父目录下出现受管路径时，文件保留且 vendor 不启动 |
| R3：已成功副作用续作 | 只有已成功、逐路径后态与封存预期一致且原件备份可验证的 vendor 结果能改变后续候选的预期当前状态 | vendor 成功修改 AGENTS 后，后续目录删除原地失败；修正失败原因后带同 plan 回执可继续，最终仍从原件计算标记删除结果；用户后续编辑/伪造结果拒绝 |
| R4：授权减项 | 同一已确认流程内，已证明完成的项移出剩余列表不产生新权限，也不消耗第二次确认 | 展示合并清单 `{A,B}` 并确认后，绑定回执证明 A 完成；剩余 `{B}` 的目标/效果不变则沿用同意并使用新 plan_id；新增 C、改变 B 效果或缺完成证明则停下核对/确认 |

R4 属于 Skill 路由契约，由独立审查核对相同/减项/扩权/未知消失四个分支；不新增只测文案词串的永久测试，也不把静态检查冒称真实宿主对话。R1–R3 以隔离资源的行为回归和 CLI smoke 验证。

## 6. 第二轮审核修复行为

| 场景 | 操作 | 可观察结果 |
|---|---|---|
| 选定 `.gitnexus` 内包含也被选为退役对象的 Skill | 计划清理，或执行旧版已封存的父子重叠计划 | 在任何删除前拒绝；父目录、Skill 与其他候选原文保留，不靠执行排序掩盖冲突 |
| 有效 OMP 配置使用相对 `PI_CONFIG_DIR=custom-omp`，可带 `OMP_PROFILE=work` | 计划、确认、执行 MCP 清理 | 展示对应有效配置中的 GitNexus；只移除其条目，邻居保留；默认位置仍受原检测规则保护 |
| 非标准 Skills 根只由安装参数选择，环境变量指向另一个合法根 | plan 显式指定 `--global-skills-dir`，随后执行封存计划 | 显式参数优先；计划展示该根下退役 Skill，apply 只清理封存根，环境根与默认根不动；apply 不接受重新指定根 |

上述场景以现有检测、plan/apply 和实际 CLI 为验证接口；不新增 mock 数据协议或自动恢复命令。第一轮与本轮失败/通过证据分别保存，不沿用旧全量结果。

## 7. Prepared 卸载资源路径绑定

封存摘要用于内容绑定，不是任意路径的权限证明。执行时每个资源的 `relative` 必须符合 vendor 的严格相对路径规则，`path` 必须逐字等于受检项目根拼接该 `relative` 的 canonical 路径；不接受项目内其他文件、项目外诱饵或含 `..`/重复分隔符的拼写别名。受检 root 与 fresh planner 的 relative/kind/expected-after 核对共同绑定实际操作对象；备份和测量不能绕到另一份文件。

| 场景 | 操作 | 可观察结果 |
|---|---|---|
| 把封存资源路径改成项目内或项目外诱饵，并同步 before、重算摘要 | 执行清理 | 备份与 vendor 卸载前拒绝；实际项目原文、诱饵和 vault 均不变，不能报告成功 |
| 将相对路径改成父级逃逸、绝对路径或非 canonical 拼写并重封 | 执行清理 | 严格路径门拒绝；不以词法归一化放宽授权 |
| 使用正常生成的既有计划 | 执行、失败后核对或按既有规则重试 | 正常完整备份、vendor 运行与逐资源结果保持；不更改 JSON 版本、摘要算法、回执或恢复合同 |

回归接口为公开 prepare/execute；vendor 异常分支使用既有 fixture，正常与拒绝路径另做实际已安装 vendor 的隔离场景，不触碰真实用户项目。

## 8. Windows 恢复删除的私有暂存目录复用

同一次受管目录删除按父目录分组文件并复用空私有holder，避免文件与子目录名称交错时反复创建holder。每个文件仍重新证明holder私有权限、目录身份、路径安全和当前内容；权限结果不跨文件或调用缓存。Windows权限证明改用下节进程内安全API，不再为每次证明启动PowerShell。不同父目录分别创建holder，单文件操作保持独立生命周期，不用跨卷搬移优化。

| 场景 | Given / When / Then |
|---|---|
| 正常目录恢复 | Given已绑定的受管目录与完整原件；When原生Windows执行安装副本恢复；Then完成逐文件删除/还原并保留回执/备份，现有900秒测试期限与完整安装载荷不放宽 |
| 后续文件被用户修改或新增 | Given首个文件已捕获；When用户修改后续文件或新增内容；Then后续删除拒绝且用户字节保留，不按初始目录快照盲删 |
| 私有holder被替换或污染 | Given本次创建的holder已用于首个文件；When目录身份改变、权限变宽或出现未知original/其他内容；Then拒绝下一次捕获，不覆盖未知对象，保留可恢复材料 |
| 捕获后原名竞争 | Given文件已捕获到私有位置；When原名出现新的用户对象；Then不覆盖竞争者，原捕获对象保留并报告真实部分结果 |

公开验证接口仍为`remove_reference`、`install_reference`及upgrade/recovery CLI；不新增持久schema、后台清理器或ACL缓存。目录对象仅在身份仍匹配且为空时移除，未知或非空内容不得递归删除。

## 9. 进程内 Windows ACL 证明与验证范围

Windows使用Win32安全API读取打开目录的安全描述符；句柄不跟随重解析点，并与打开前lstat身份核对。属主必须为当前进程用户，DACL每条ACE均须为授予该用户、SYSTEM或Administrators的标准允许项；NULL/无效DACL、未知ACE形式或无法读取一律拒绝。空但有效DACL禁止所有显式访问，不等于NULL DACL。继承开启本身不拒绝，以实际继承的ACE内容判断。仅缓存函数绑定，不缓存身份或ACL决定。

仅在本次创建目录分支设置当前用户属主和受保护的可继承FullControl DACL；既有目录只读核验。创建及后续ACL安装仍依赖可信、单controller的父目录命名空间：句柄证明不使mkdir和ACL设置成为原子操作，也不消除在初始身份采样之前换目录的既有竞态。不新增线程模拟身份支持或全新权限策略。

| 场景 | Given / When / Then |
|---|---|
| 新建与重复核验 | Given受控父目录；When创建私有目录或staging并复核；Then无需PowerShell子进程，基本主体/规则判定与原脚本对照一致 |
| 非受信主体与拒绝项 | GivenEveryone/Users授权或Deny ACE；When检查；Then拒绝，且create=True不得修补既有对象 |
| 错误属主 | Given成功建立外部属主夹具；When检查；Then拒绝；夹具建立失败不得静默跳过后仍声称已验 |
| 空与NULL DACL | Given有效空DACL或NULL DACL；When检查；Then前者符合deny-all私密边界，后者拒绝；测试后用原句柄恢复权限 |
| 无法读取 | Given安全描述符读取返回错误；When公开私有目录入口检查；Thenprivacy-unproven，不把缺少证据当通过 |

CI按fixture单元与实测逐例权重分片，Windows四片、Linux三片、macOS保持单job。分片并集须等于各平台原选用集合，fixture不得分散执行；缺权重新例仍运行并显式列出。权重刷新拒绝无修订身份、歧义attempt、失败/缺失/重复或不一致分片。覆盖重叠只是冗余筛选，不能替代断言/状态/平台语义审查；具体Windows排除清单须用户审阅后生效，替代见证必须实际通过。


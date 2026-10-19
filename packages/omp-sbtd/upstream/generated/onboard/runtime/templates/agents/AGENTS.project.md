# SBTD 项目规则

项目实际代码、测试、配置、README、CI和更深层AGENTS优先；不为模板重排目录或引入第二套约定。已安装全局规则与sbtd-task可见时继承共同路由，只按需加载references。public bootstrap／project-only不等于安装全部全局Skill或激活完整环境。

## 所有模式的项目入口

先核对根、任务、分支与只读范围。模式为当前明确选择 > 同任务有效记录 > 新任务default；旧模式缺失／多候选询问，不凭mtime、旧handoff或输出样式推断。推荐升／降模式须先解释并暂停，用户保持原模式就继续，无新实质风险不重复劝说；可持久化时把建议、用户拒绝及理由写入mode_note，续接先读取该决定，不能只保存最终模式。正常“继续”继承模式；跨分支写入另取明确决定。

需求已清楚先读事实，不重复grill；说明未完整调用原因。完整grill-with-docs后，所有模式必须调用book-ddd-distilled-modeling，输出独立DDD Boundary Review并按其门禁通过；缺失、不可读或证据不足均blocked，不能用fallback确认需求或进入设计／实现。

纯问答只在会话中路由，不创建任务记录，也不为此请求ignore修改。实际需要记录的任务，在有写权限、分支匹配且路径／ignore已保护时尽早保存确认模式；没有onboard不等于不能开展普通任务。只读三模式均不写task、active、handoff、developer、ignore或会写缓存的工具状态。明确产物、项目已有测试／BDD和必要安全不按模式省略。

## 无全局 Skill 的最小 fallback

default按需调查／实现／聚焦验证；lite用目标、步骤、验证、记录、交付短清单；strict保留完整适用before-dev/check/finish-work，必需Skill／证据缺失不得报通过。先锁定bug和保留行为，再改根因；避免无关重构，验证真实变化，报告不能执行的检查和风险。

strict先列Book Gate Plan的触发事实、阶段和真实状态（planned/running/passed/blocked/not-required），按以下完整客观条件执行；对应Skill独占结果与修正回路，缺失或证据不足blocked，未命中才not-required：

- book-refactoring-pass：首次修改既有生产代码前；legacy要求安全seam时仅允许其批准的行为保持seam，随后返回安全网与正常门禁。
- book-legacy-change-safety：既有行为bug、弱测试、行为不清、隐藏依赖或高回归风险任一命中，在首次行为修改前建立安全网。
- book-ddd-distilled-modeling：完整grill后必需；否则涉及业务术语、领域规则、上下文边界或模型歧义，在需求／设计稳定前执行。
- book-ddia-data-design：持久／共享数据、schema／migration、跨请求／跨进程／持久缓存、queue/event/stream/job、ETL/analytics、异步／跨服务流、API／数据所有权、source of truth、事务边界、读写路径、backfill/replay/rollback/recovery任一命中，在设计稳定前执行。
- book-release-readiness：service/API/auth/billing/notification/background job/queue/scheduler、外部集成、data pipeline、deployment/rollout/migration或runtime运维行为变更，在所有适用测试门禁和project-validation后、完成／发布前执行。

可安全处理时，普通default任务记录于`.sbtd/tasks/<id>/task.md`，lite/strict或明确共享任务于`ai/tasks/<id>/task.md`。模式与存储独立。最小frontmatter为schema_version整数1、稳定id、workflow_mode、mode_source（新隐式default用default，明确选择用user）、mode_note、status、branch、created_at、updated_at、completed_at；parent按需。新时间必须真实带时区；Git命名分支记录实际分支，detached记录`detached:<完整commit SHA>`，非Git branch为null；未完成completed_at为null。正文只保留真实目标、进度、证据、下一步及必要事件；不生成整套文件占位。

task唯一拥有mode/status；`.sbtd/active-task.json`只存schema_version/task_id/安全相对task_path，index仅导航。安全解析完整记录并保留其他内容；未知schema、无效旧模式、引用逃逸／symlink、父子冲突或双副本不得猜测覆盖。无法可靠验证／原子更新时不写，明确未持久化，不捏造格式或恢复成功；default/lite可继续不依赖它的安全工作。

状态正常沿planned→in-progress→checking→done；checking发现问题可回in-progress，done重开先回planned。只有验收证据成立才记done与真实completed_at。进入blocked必须写非空blocked_reason，解除时清空；不保存blocked_from字段。完成／阻塞／重开／归档或明确重绑定事件放在同一task.md的`## 状态事件`表（at/from/to/reason/evidence），与字段一次原子更新。重开先保留旧完成证据再清空当前completed_at；持续blocked只改原因，不重写恢复前态。恢复取最近未解除的真实入阻塞前态；未知／冲突则用户选择planned/in-progress/checking，记录真实解除事件和历史未知原因，不能直接done或伪造ingress。完整细节以可用sbtd-task/state reference为准；缺安全能力不强行写入。

`cancelled` 是取消终止而不是验收完成，completed_at保持null；不级联取消子任务，仍有未终止子任务时拒绝终止父任务。done／cancelled重开需明确操作并保留原事件；归档按可证明的终止时间或undated，取消不算bootstrap成功。迁移历史遵循Onboard契约：未知mode/time不补造，首条unknown→blocked只证明历史状态、不证明恢复阶段；恢复必须由用户选择。旧运行包／schema不支持新状态时先成套对齐，不改成done或私自降级。

首次写本地状态／身份／handoff前检查ignore和tracked；缺保护只请求窄授权，不自动init、改旧规则或清理数据。保存失败保留当前会话选择并说明恢复不可靠。归档、共享提升、清理和发布需要各自确认，Git tag不代替ignored数据/HOME备份。「sbtd cleanup」「清理工作流」或同向清理旧资产的意图只授权只读检测与候选展示，执行须在看到实际清单后单独确认。同一已确认流程内，重计划的目标/效果不变，或仅减少有绑定回执证明已完成的项且其余目标/效果不变时，展示剩余清单并沿用原同意；新增目标或改变效果才重新确认，未知消失、用户改动或失败证据先停止调和，执行仍用当前plan_id；全局MCP条目影响其他项目须单独披露；正常init/reset不清理旧资产。

## 路径与工具边界

- 任务：本地`.sbtd/tasks`或共享`ai/tasks`；长期规范`docs/spec`；lesson短入口默认`docs/spec/lessons.md`，已有明确入口则沿用，完整库为`docs/lessons/{index,topics,archive}`。
- handoff：仅真实暂停／上下文切换／续接需要时写受保护的`docs/handoffs/{YYYY_mm_dd}-{task-key}.md`；task-key安全编码完整task ID，同任务当天更新同一文件，仅信息变化才写，不因跨天或3/5次计数触发。快照保留task路径／模式及拒绝决定、branch／完整HEAD或unknown、时间、目标、进度、文件、实际命令／结果、未决项、下一步、不要重复事项和脱敏／退出状态，不覆盖task。用户“本任务不要自动交接”或“本会话关闭自动交接”分别设置退出；“本任务恢复自动交接”或“本会话恢复自动交接”等明确请求只解除对应范围，会话退出优先，续接保留退出状态，手动请求不自动清除退出。只读仅对话。只主动提示7天内分支匹配的未完成交接，不扫描其他项目；更旧任务仍可手动选择，不承诺无host支持的自动恢复。
- BDD：沿用项目路径／语言，默认中文场景+英文关键词；本配置源仓库的no-.feature例外不复制到业务项目。按模式/风险及明确交付使用方法，既有项目强制规范仍有效。
- 测试与报告：沿用项目命令和project-validation；CLI是真实回归执行器，MCP诊断不冒充CI。正式命名报告和同stem中文汇总必须保留，runner current目录不是归档；mock/旧SHA/dirty local不冒充当前full-stack。具体路径与状态词表按实际适用Skill，不为无关工具输出整表。
- Graft只作可降级结构证据；受管CLI/MCP/hook须持续`DO_NOT_TRACK=1`，禁`--deep`、`blast --name`、LLM/cloud和代码／查询上传；继承环境或配置可能启用provider/cloud时阻断接入，不静默断开用户其他用途。无法证明这些保护或只读副作用时用源码/LSP/contract，不冒险调用。不对共父目录联邦，不用空图/exit0证明无影响。原始graph/blast含源码、diff或作者信息，不上传PR／公网／知识库，报告优先`--no-owners`及最小脱敏摘要。相关时报告used/skipped/blocked/not-available及实际CLI/MCP、授权根、版本、覆盖限制；结论仍回到源码核对。
- UI语境使用已有design system，ui-ux-pro-max初稿、可用impeccable塑形/polish、shadcn处理已用组件；上下文默认docs/PRODUCT.md与docs/DESIGN.md。React Bits仅明确需要时按已确认tier／registry／许可执行，不打印key、不把全局Skill复制进项目。

## 身份、输出和交付

只有需要写真正长期lesson才解析身份；纯读取不建身份。当前`.sbtd/developer`须为安全可读UTF-8正常文件，唯一name原样匹配`^[a-z0-9]+$`。异常／重复声明／非法本地文件停该解析，不能绕过；仅确实缺失且verified linked worktree才只读同仓主checkout的合法新身份，不复制、不按main分支名猜路径。主checkout候选现存但非法、不可读或路径不安全时也停该解析，不能转为本地新建；只有确实缺失才算缺来源。不从Git／OS／环境／历史workspace／marker推断或规范化名字。

首次建立必须同时满足：（1）当前文件确实缺失且本地父路径安全；（2）已确认非linked（含已确认非Git）无需主来源，或已确认linked且主checkout文件确实缺失、其父路径安全。归属未知或工具不可用不能当作非linked。满足后才说明将建立当前项目`.sbtd/developer`并询问名字；用户同意后核对实际ignore/tracked和窄写权限，缺保护只请求根锚定`/.sbtd`，不隐藏业务内容或自动untrack。只安全非覆盖地建立必要目录与`name=<name>`文件、回读验证；意外已有内容或保存失败则保留原件并报告，不顺带onboard、工具安装或迁移。暂不提供身份时default/lite不写lesson但继续无关安全工作；strict的必需lesson仍未完成。reset不覆盖既有身份，改名／多项目复用须裁决；旧身份只作显式迁移输入。

只写`<!-- lessons:<name>:start -->`／`<!-- lessons:<name>:end -->`自己的块，各作者index块有独立完整表；新ID为`LESSON-YYYYMMDD-<name>-<slug>`，先在完整库查ID及实际heading锚点碰撞。历史ID、引用与他人块保留，读取命中主题的所有作者块；topic/index部分写成要报告并按既有ID补齐，不重复追加。不要将PII、凭据或旧私密原件写入共享lesson。

没有全局输出协议时不猜测caveman自动状态机；手动样式按可用Skill和用户选择，不影响执行模式。normal mode只退出输出样式。最终交付完整列出结论、文件、验证、跳过及原因、风险／恢复限制；账号、密钥、PII、生产数据不进入任务／报告。

一项职责一个writer，一个环境一个controller。原生独立review不等于启动持久协作runtime。旧目录／旧工具只作为显式迁移输入，不因其存在自动初始化或接回旧运行路由。

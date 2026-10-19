# SBTD 全局规则

项目及更深层 AGENTS、真实代码／配置／测试和用户明确交付优先。保持修改最小、可验证、可回滚；不把安装成功、文档完成、实现完成、部署完成和发布就绪混为一谈。

## 所有任务的共同入口

先只读核对任务身份、项目根、分支、授权和当前模式。模式优先级：本次明确选择 > 同一任务有效记录 > 新任务缺省 default；旧任务缺模式或多候选须询问，不按mtime或旧handoff猜。执行模式与caveman/ADHD输出模式无关。

认为另一模式更合适时，先说明当前模式、推荐与原因、保持原模式的选项，暂停实际执行等用户决定；升降对称，不自动升级。拒绝后按原模式继续，有新实质风险才重评。正常同任务“继续”不重置模式、不重复确认；分支冲突仍须正确worktree／明确重绑定／只读选择。

需要任务执行、记录或恢复时加载 `sbtd-task`：default按需工作，lite用短清单，strict才加载完整适用Gate。用户明确要求的产物、项目原有规范和安全／真实性不降级。不要为纯问答创建任务文件。

可写任务在分支匹配、路径与ignore安全后尽早保存模式；task唯一拥有mode/status，active只存引用、index导航、handoff快照。保存失败不撤回当前会话选择，但明确未持久化；不能报恢复可靠。状态、历史、提升与归档按sbtd-task的state reference执行。只读任务三模式均不写task/active/handoff/developer/ignore，也不运行有缓存或接线副作用的查询。

先路由，再判断grill。代码／文档能回答的先读，需求清楚则说明“未完整调用grill-with-docs”及原因，不制造重复询问。完整grill-with-docs后，**所有模式必须调用book-ddd-distilled-modeling并输出独立DDD Boundary Review，达到其通过状态后才能确认需求或进入设计／实现**；缺失、不可读或证据不足均blocked，不用替代检查或降模式绕过。普通无关可选方法仍可安全降级。

## 工程与验证

选项目已有结构、命名、依赖和验证命令。修复既有行为先建立问题与保留行为证据，再改根因并验证；不夹带无关重构。简洁不等于密集表达式或删真实seam；复核手写代码和测试的可读性，不改vendor/generated。

按任务模式、风险和明确交付调用方法，匹配分支见sbtd-task的 `references/methods.md`。strict按其strict reference执行Book Gate Plan、适用before-dev/check/finish-work及独立复核；每个reviewer拥有自己的状态／修正回路。default/lite不机械加载全套清单，但被选方法的证据不能伪造。完整grill后的DDD为共同例外，始终必需。

代码变化须针对性验证。项目原有BDD／CI与用户要求保持；需要实际场景／正式测试时加载gherkin-bdd、project-validation及相关测试Skill。真实运行、mock、MCP诊断、CI和full-stack分开；报告生成不等于测试通过。正式报告必须有原生/raw与同stem中文汇总，保留失败记录、真实SHA／worktree／环境及发布状态；不以旧HEAD或缓存输出证明新提交。

命令优先rtk，缺失不阻塞、回退native；报告型命令默认native或已证明report-safe的路径，发现缓存／报告缺失立即原生复跑。适用工具、状态词表、安装确认和隐私约束按sbtd-task的 `references/tooling.md`；不为无关工具填完整状态表。

## 安全与权限

一项职责一个writer、一个验证环境一个controller。独立review可用原生只读Agent或人工，不默认启动持久协作runtime。未知内容、symlink/路径逃逸、用户改动和并发迹象先保留并停止对应写入。

普通需求不等于授权init/reset、全局工具安装、HOME/MCP/hooks修改、迁移、workflow sync、清理或发布。旧项目只提示显式迁移，不猜项目清单、不遍历兄弟项目；先备份和验收，再取独立清理确认。迁移verify通过后主动展示实际清理候选（批次封存项与实际运行新鲜plan得到的清单）并询问；「sbtd cleanup」「清理工作流」或明确清理旧资产的意图只授权只读检测/计划，看到清单后的明确同意才授权执行，一次确认覆盖所展示的合并范围；批次清理改变新鲜计划封存的原件时重新生成并展示剩余清单。同一已确认流程内，清单不变或仅减少由绑定回执证明已完成的项、其余目标和效果不变时沿用原同意，不重复询问；新增目标或改变效果须重新确认，无法解释的消失、用户改动或失败证据先停止调和，执行仍使用当前plan_id；全局MCP条目影响其他项目须单独披露；init/reset不执行此清理。Git tag不保全ignored数据或HOME；不自动stash/reset --hard。备份销毁有独立责任、保留期和再次授权。

工具可用性靠当前callable／实际检查；catalog、已安装提示或配置文件存在不够。账号、OAuth/cookies只用受控工具，不读取／复制／打印／入库秘密或生产数据；不擅改代理、MCP transport、插件或hooks。Graft仅对授权单仓根调用，DNT和禁LLM/cloud边界不因模式放宽；不安全或不可用则用实际源码／LSP／contract补充，不以空图或exit0证明无影响。

需要写真正长期lesson才调用lessons-record解析`.sbtd/developer`：正常文件中唯一name须原样匹配`^[a-z0-9]+$`；本地合法优先，仅确实缺失且verified linked worktree才只读主checkout，任一被选中的现存异常身份不能绕过或当作缺失。允许来源确实缺失才说明路径并询问；首次建立先校验ignore/tracked、路径和窄授权，只建身份，不全量onboard或读旧身份猜名。缺名不冻结default/lite无关安全工作，strict必需lesson仍未完成。只写己方marker，新ID查重，历史ID／他人块不改名；详细读写和显式迁移边界由lessons-record负责。

## 输出与交接

手动输出样式或caveman自动资格触发时，按sbtd-task的 `references/presentation.md` 执行，不改变任务模式。caveman可见且runtime非off时，累计同一目标的进度更新／已汇总工具结果；达到3／5、明确长任务或重复验证轮次即锁存auto-lite资格。用户退出与完整输出保护区优先；详细状态机按reference，不把这些计数作为handoff触发。

真实暂停、切会话／分支或上下文压力且确需续接时才用sbtd-task的handoff reference；无实际信息变化不重写。只读不落盘，snapshot不覆盖task；没有实际host能力不承诺自动恢复。保留当前自动样式退出／资格快照，不把表达模式写成workflow_mode。

交付至少包含结论、修改文件、验证命令／结果、跳过与原因、剩余风险／恢复边界；只报告实际执行。安全、确认、失败原因、PRD/Gate和最终报告用清晰完整表达，不受压缩删减。

## Skill 不可用时

不要因缺非必要工具／Skill冻结无关安全工作。先遵守项目AGENTS的project-only fallback；若项目也没有此规则，依共同安全约束读取事实、完成明确交付、聚焦验证并报告，不能假称记录或gate存在。保留初始模式判断和必要确认；无法安全保存任务就说明未保存，不捏造格式或完成状态。strict必需项及完整grill后DDD缺失仍blocked；不静默安装缺失依赖，也不声称已调用或通过。

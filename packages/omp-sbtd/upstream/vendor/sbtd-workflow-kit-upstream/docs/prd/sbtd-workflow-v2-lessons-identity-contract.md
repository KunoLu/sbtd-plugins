# P0-06 lessons 身份与历史保留契约

## 范围与交付

依据主 [PRD](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md) §8.3、§8.4、§11.6，交付 AC-06/25 的规则子项，不提前声称 P1 文件系统／worktree 执行已完成。

- [完整入口正式源](../../sbtd-workflow-onboard/templates/skills/lessons-record/SKILL.md)：按需身份、唯一短入口、marker/ID、写入与部分失败、按需读取。
- [显式身份迁移分支](../../sbtd-workflow-onboard/templates/skills/lessons-record/references/identity-migration.md)：只在授权该项目迁移后读取；旧输入不再作为日常身份fallback。
- LICENSE/NOTICE从现有自有Skill原样保留；P0-06以非discovery候选交付，P0-07才切换正式入口。
- [全局](../../sbtd-workflow-onboard/templates/agents/AGENTS.global.md)和[项目](../../sbtd-workflow-onboard/templates/agents/AGENTS.project.md)规则同步关键身份保护；无全局Skill的项目仍知道合法值、优先级、首次授权与历史不变量。

按 [D-IMP-08](sbtd-workflow-v2-implementation-decisions.md)，P0-07与其他路由同批替换正式lessons-record完整目录并删除候选，上述链接跟随canonical路径。P0-06交付时未改变实际安装内容，其Gate／验证事实保持为历史快照；源目录切换不代表用户数据迁移或身份运行实现已通过。

## Book Gate Plan 与 DDIA 结论

| Skill | 选择／触发事实 | 阶段 | Gate state |
|---|---|---|---|
| book-ddia-data-design | required：身份持久事实源、读写优先级、部分写入与迁移边界 | 规则设计稳定前 | passed |
| book-ddd-distilled-modeling | on-demand：沿用已确认split name、任务／身份／历史作者概念，无新领域歧义，未完整grill | 不触发 | not-required |
| book-legacy-change-safety | on-demand：仅非生效规则候选，不修改现有生产行为或修复运行bug | 不触发 | not-required |
| book-refactoring-pass | on-demand：无既有生产代码编辑 | 不触发 | not-required |
| book-release-readiness | on-demand：无当前运行或部署改变 | 不触发 | not-required |

DDIA Data Design Review：confirmed。当前合法文件拥有本地身份；缺失且linked才只读真实主checkout，不复制；异常是冲突，不是fallback条件。首次建立需要名字、保护和窄权限，写后回读；失败保留原件。topic/index不是跨文件事务，重试按已存在ID和己方marker补齐，不重复追加。迁移私有原件与共享安全投影分离，不改历史ID或把新身份成功误报为整项目迁移成功。

未完整调用grill-with-docs：PRD已经明确所有权、优先级、名字限制和授权边界，无须重复访谈。TDD本项不新增：没有新运行代码，不能用文本断言或另写一个测试专用resolver冒充行为证明；P1-19/P1-12负责真实红／绿与负例执行。

## 分支验收矩阵

下列是协议review检查面，不是已经执行的host／迁移结果。

| Case | 条件 | 规则要求 |
|---|---|---|
| LI-01 | 本地合法，主checkout可能有不同身份 | 本地优先，不越过它选择其他来源 |
| LI-02 | 本地确实缺失，linked worktree，主checkout合法 | 验证同仓后只读使用，不复制 |
| LI-03 | 当前文件确实缺失，并且（已确认非linked无需主来源，或已确认linked且主checkout文件也确实缺失） | 问用户，不从Git／OS／环境／历史目录或marker猜名字；现存异常不属此分支 |
| LI-04 | 本地非法但主checkout合法 | 停该解析，不绕过本地异常 |
| LI-05 | 本地缺失，主checkout异常 | 保留异常，不退回旧身份 |
| LI-06 | 未onboard、首次必要lesson、允许的身份文件均确实缺失、用户给合法名字 | 说明路径、保护检查与窄授权，只建必要身份并回读 |
| LI-07 | Alice、a_b、带分隔符或其他非法值 | 拒绝并询问，不小写化／去标点／音译 |
| LI-08 | 只读或仅读取lesson | 身份／ignore／lesson零写入 |
| LI-09 | reset、改名或多项目复用名字 | 保留现有值；不同名或跨项目复用先裁决 |
| LI-10 | 保留目录含业务内容、tracked、symlink、同名目录或创建竞态 | 不隐藏、不untrack、不覆盖，停对应写入 |
| LI-11 | 授权迁移，旧合法、新文件确实缺失，并且（已确认非linked，或linked主checkout新文件也确实缺失） | 原名建立并验证，不立即删旧文件；主文件异常则阻断该操作 |
| LI-12 | 旧合法、新合法同名 | 已有一致身份，不重复写 |
| LI-13 | 旧合法、新合法异名 | 保留两边，用户裁决 |
| LI-14 | 旧名非法、新文件确实缺失，并且（已确认非linked，或linked主checkout新文件也确实缺失） | 问合规新名，不规范化旧名或宣称原名迁移；本地缺失但主新身份合法时另按LI-16，异常另按LI-05 |
| LI-15 | 旧文件缺失、本地新身份合法 | 使用本地新身份，不读取主checkout覆盖它，不生成占位名 |
| LI-16 | 当前缺失且主checkout有合法新身份，当前有旧身份 | 只读主新身份，不迁／复制本地旧身份 |
| LI-17 | 新ID与旧格式ID或实际heading锚点碰撞 | 换slug，不改历史ID，不靠marker隔离假设唯一 |
| LI-18 | topic成功、index失败，或并发内容变化 | 报告部分完成，按己方既有ID补齐；冲突不强盖 |
| LI-19 | 用户暂不给名字或保护授权 | default/lite暂不写但继续无关安全工作；strict必需项未完成 |
| LI-20 | 历史原件／marker／ID含不宜公开内容 | 原件私有保全，共享投影过隐私门；不安全就阻断投影 |
| LI-21 | 唯一name不成立、文件损坏／不可读或路径类型不明 | 视为冲突而非缺失，不自动选其他身份 |
| LI-22 | 旧名非法、新身份合法 | 保留新值，旧异常交显式迁移计划裁决，不推断旧新映射 |
| LI-23 | 旧／本地新文件均确实缺失，并且（已确认非linked，或linked主checkout新文件也确实缺失） | 询问新名；本地缺失但主新身份合法另按LI-02，现存异常另按LI-05，不生成占位名 |
| LI-24 | 本地身份缺失，但Git／worktree归属因工具不可用或元数据歧义未能确认 | 停身份新建／旧名复制，不假定非linked或主文件缺失；其他安全工作按模式继续 |

## 保留与最小化

保留原有marker语法、带名字的新ID格式、全库ID/anchor查重、各作者独立index表、读所有作者块、150–200行短入口建议和仅append-only范围的可选union。旧运行时命令只在明确迁移说明中作为禁止执行的旧输入边界出现；普通入口不要求旧目录或初始化器。

具体工具、执行代码和迁移receipt不在此另起实现。整个候选作为一个完整Skill安装；条件迁移说明放reference，普通写lesson不加载它。现有外部stable镜像不改。

## 验证与文档维护

本项做临时最终包名复制／入口解析／内部链接／license摘要验证、现行资产未改变检查、PRD依赖与案例唯一性检查、现有unit回归及独立review。unit只证明现有套件未回归，不证明候选被真实Agent执行；实际创建／竞态／Git worktree与迁移负例仍由P1负责。

README.md、README.html和版本化automation prompt暂不改：现有安装、运行、同步和检测入口未变化，不能把候选描述成已激活产品。P0-07与后续实际改动仍须同步受影响入口。CHANGELOG未发布文档节记录本次规则准备。未执行workflow sync、live automation修改、HOME写入、身份创建或真实lesson历史迁移。

## 首轮 review 修正与 DDIA 复核

P006ReviewOne的六项发现均涉及缺失／异常和主checkout优先级：迁移表三处创建条件、project-only首次建立条件及LI-14/15。全部改为“文件确实缺失”，并明确现存非法／不可读／不安全的允许来源先进入冲突；合法主新身份先于任何旧名决定。同步收紧全局入口及LI-03/06/11，避免同类歧义留在其他路径。

DDIA复核由needs-design-change回到confirmed：只在已证明缺失的分支建立身份；valid/absent/conflict不互相替代，旧名决定在当前身份链之后。事实源、授权、部分写入、原件保留及P1执行验证所有者不变。此段记录规则修正，不宣称六个运行bug已用unit重现。

原LI-15的两个互斥结果拆为LI-15（本地新身份已合法）和LI-23（允许来源均确实缺失），避免主checkout条件错误覆盖已经合法的本地身份；该轮矩阵为23项，历史22项报告保持原样。

## 第二轮 review 修正

P006ReviewTwo指出独立Skill的未知worktree路径和主PRD的旧简写仍不精确。已同步独立入口、迁移reference、项目fallback与主PRD §8.3／§11.6／AC-25／D-24–26，记录D-IMP-09；新增LI-24后当前矩阵为24项。未知归属只阻断依赖该事实的身份建立，不覆盖已合法的本地身份或冻结无关工作。

DDIA再次复核confirmed：当前链优先、缺失／异常／未知三类分支明确；单文件身份与跨文件lesson部分完成模型、幂等和私有原件保留未改；报错需指明缺失事实，P1仍负责真实Git/worktree及创建路径执行证明。

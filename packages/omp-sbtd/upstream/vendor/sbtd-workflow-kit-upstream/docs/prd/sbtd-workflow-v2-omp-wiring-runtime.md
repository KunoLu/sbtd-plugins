# P1-05：OMP接线、CLI分析与部署证据

## 基线、范围与时序

- 基线main `bf6b3272afcc41f34bf2897e1dea7af7957e91c7`；分支`p1-05-omp-wiring`。P1-04实现PR #41、补救 #42、状态 #43已闭环，明确归属临时文件和相关分支已清理；P1累计8项。
- 本项为第9项；P1-06第10项完整闭环后暂停评估全部findings并等待用户确认，不能自动进入P1-13。P2/P3按原级延期，不扩大本轮修复。
- 不写真实HOME配置、Codex hooks或OMP hooks，不执行真实项目迁移、sync/live automation、ENTRYPOINT版本更新、cleanup/recovery。私有验证extension仅用于实际OMP SDK查询，不作为产品extension交付。

## Book Gate与澄清

- 未完整调用grill-with-docs：产品边界已由主PRD给定，路径／继承／能力问题通过固定源码和隔离实验澄清，无新业务模型。
- Legacy characterized：原生基线899 tests/488.044s通过，6 skip；实际OMP 18.2.5完成8个继承／profile场景，启用场景通过真正native MCP查询。
- Refactoring proceed/normal：共享部署模块改为host-neutral命名、迁移全部调用方，不保留旧module alias；复用P1-04守卫／候选／累计证据执行，不复制迁移引擎。
- DDD on-demand/not-required：未完整grill，无新业务术语或上下文歧义。
- DDIA confirmed：读依赖与写资源分开声明，host／模式明确绑定；共享配置一次备份／一次资源结果，漂移先拒绝，不扩大源配置写权限。
- Review 后收紧：等价继承按 OMP 完整连接身份判定；active `mcp.json` 与 `.mcp.json`、server denylist 与 settings `disabledExtensions` 均纳入阻断；provider disable 对所有级别生效；agent `.env`、legacy settings、overlay 和 project provider settings fail-closed。
- Release planned：实际host、CLI分析、迁移生产者、Codex回归、安装副本和最终head证明完成后再判断ready。

## 已确认原生事实

- 本机编译版OMP实际`--version`为`omp/18.2.5`，binary SHA-256为`9602f93f94bd1ee5d69f9c7b8c373dbed47abe59f5a39315ef2f0fd3c517f743`。源码依据固定`can1357/oh-my-pi v18.2.5`，Context7当前文档仅作导航，不覆盖tag源码。
- native MCP项目`.omp/mcp.json`／`.mcp.json`先于active user agent目录两种文件；native优先级100、Claude80、Codex70。按name与连接等价去重，disabled server仍占据同name；disabledExtensions与disabledProviders是不同门。
- 用户级外部源是opt-in（`enabledProviders`），不是仅有`~/.codex/config.toml`就继承；project源不受此用户级门限制。Codex源读取`~/.codex`而不是active CODEX_HOME，project同名disabled优先。Claude优先`.claude.json`／其config目录mcp.json，project先于user；转换时不保留cwd。原生manager实测支持上述差异。
- active profile由OMP_PROFILE优先于PI_PROFILE；named profile使用独立agent目录并忽略PI_CODING_AGENT_DIR。default profile才使用该override。PI_CONFIG_DIR、profile命名限制和继承profile-derived override须按固定源码处理；不把XDG data/state/cache位置当作MCP config位置。
- 无模型可用时RPC启动失败；私有`auth: none`且不可达loopback provider允许只执行本地命令。通过私有extension内官方`createAgentSession`与实际MCPManager完成发现、握手、tools/list、`graft_repo_map`查询，无模型请求、无mock MCP。
- 8场景：native、Codex opt-out、Codex opt-in、native覆盖等价连接、project禁用Codex、named profile、agent-dir override、Claude opt-in；有效场景6工具／1server，禁用场景0server，配置源字节未变，host EOF退出0。

## 设计与契约调整

1. 共享执行器移为`scripts/sbtd_graft_deployment.py`，Codex候选继续归自己的模块；OMP来源分析／JSON候选独立成内聚模块。正常check/plan/init/reset/init-projects沿用既有入口和状态语义。
2. OMP写入仅active user MCP配置；读取继承来源和启用／禁用设置以避免重复，未知动态或冲突内容明确阻断，不执行配置中的命令去猜结果。既有全局AGENTS镜像规则保持，不等同于跨host MCP接线。
3. manifest新增nullable `deployment`描述（mode、platform、只读inputs）；无部署为null。inputs为file/absent快照，只证明依赖、不授予写权限；可写目标由原有operation闭包拥有。此前Codex按selector推断mode不足以表达OMP继承及选择，故在同一未发布契约中明确绑定并迁移所有生产／fixture调用者。原生report schema不变。
4. migration plan的既有host维度扩展为可明确选择deployment platform；普通init的scope／host必须与manifest匹配。legacy `projects[].platforms`仍是旧资源库存，不混作新的运行host选择。
5. 全局OMP配置资源始终在full部署闭包中声明；已继承启用的等价受管连接时不重复写条目，记录当前实际不变状态。无配置且无需新定义时保留absent，不为满足回执制造空文件；只读来源漂移时停止。
6. CLI分析进入既有受管launcher的闭集子入口，覆盖PRD的ask/map/skeleton/callers/check/grep/blast；原生无`diff`子命令，diff基线仍由真实Git提供。禁止global provider／cloud／deep／name／export／任意argv透传；所有分析保持no-refresh和图守卫，输出是结构线索而非业务验收。
7. Codex既有行为保持，包括hooks独立授权、精确旧hook冲突、非可用Graft的正常降级；不借OMP工作修复先前延期的ignore/noop、共享root合并、exit-code或文案P2。

## 验证计划

- 保行为module改名先定点回归；OMP候选和schema用真正边界红绿，而非源码文本／mock回显。
- readonly正常check/plan不启动host、不新增HOME/cache；default、profile、override、继承／禁用／冲突均有实际文件前后态证明。
- 正常与迁移部署分别验证模板后接线、幂等、无Codex/OMP hooks、输入漂移拒绝、完整／partial证据及显式retry；完整source refs与installed manifests在清理前保留。
- 真实OMP SDK新会话使用受控无凭据环境，检查有效source、initialize/tools/list与真实query；与Graft CLI结构分析和全量单测分别报告，不冒称模型／Windows或完整v2发布。

## 固定来源

- https://github.com/can1357/oh-my-pi/tree/v18.2.5
- `packages/utils/src/dirs.ts`、`src/capability/index.ts`、`src/capability/mcp.ts`、`src/discovery/{builtin,codex,claude}.ts`、`src/mcp/config.ts`、`src/sdk.ts`及`docs/{mcp-config,config-usage,rpc,models}.md`。

# npm 全局 Graft 0.22.0 统一

## 本轮授权与目标

用户明确要求：升级 npm 默认全局 Graft 到0.22.0，本机已配置环境统一使用该全局安装，更新此前四个项目的配置及图，评估独立安装目录并清理确无必要的副本，最后确认 v2.0.2 tag／Release准备。沿用strict并重开同一任务；不创建tag／Release、不提交／推送，也不将条件清理要求当成未展示目录或备份销毁授权。

本轮没有新的领域歧义，未完整调用grill-with-docs。部署source仍是此前已验收的Onboard；不修改生产源码或业务实现。DDIA／迁移边界沿用单writer、前态与完整原件、provider先于consumer、逐项目非原子执行、失败保留。Release Readiness待旧活动连接退出及清理边界关闭，不把新配置成功当成所有旧进程已切换。

## 已完成

- 实际npm默认全局前缀为 `~/.nvm/versions/node/v24.15.0`，不是独立前缀。受管 `install-graft --yes` 已替换其中的0.21.1；原全局包和命令入口已保全。npm全局清单、native启动和身份验证均为0.22.0，遥测保持关闭且未改写。
- 普通Codex、既有单一Orca Codex域、OMP的受管MCP已通过原生upgrade plan/apply/verify统一到全局包canonical `dist/cli.js`；launcher继续使用已安装Onboard。provider先完成，再按新前态计划consumer；其他MCP配置语义保持。
- zsh入口去除继承的专用Graft目录，移除交互配置中的旧专用PATH覆盖，不额外固定其他Node工具选择。原生zsh语法及普通／交互／登录模式均通过；唯一可解析Graft可执行目标为npm全局包的官方bin。
- 已从既有四项目任务恢复精确范围，不扫描兄弟项目或其他账户。四项目各执行两个受管操作：Graft围栏和本地图。规则正文／分支／HEAD均保留，tracked变化仅为AGENTS中的Graft块，stamp均为0.22.0；业务代码未改。
- 三个宿主域 × 当前配置仓库及四个项目，共15次新配置MCP进程验证全部通过：0.22.0、六个工具、实际文件API命中、结构freshness OK、退出0，图在查询前后不变。未构建deep概念层，未启用LLM/cloud。
- `NpmGlobalCutoverReview` 对上述配置、新进程及四项目证据复核，无patch级缺陷；明确旧活动会话仍未统一。
- `DedicatedCleanupReview` 复核归档和清理边界，无安全finding；目录删除仍需实际清单确认且无活动依赖。未授权结束进程。

精确项目路径、配置域及原生证据仅保存在本轮私有批次：`~/.local/share/sbtd/cutovers/20261015-211351-graft-npm-global-bupzmkzh/`。不要将该批次上传或加入Git。

## 独立运行时的必要性评估

必须保留已安装Onboard守卫及 `runtime/python`。它们提供身份、DNT、路径和逐请求防护，不是多余的Graft版本。

三个独立Graft目录已不再被新配置／新shell引用，且均已完整归档并按文件hash、mode和symlink目标验证：

| 目录 | 归档条目 | 清理结果 |
| --- | --- | --- |
| `runtime/graft-0.21.1` | 7406 | 用户确认及重载后复验无引用／占用，已删除 |
| `runtime/graft-0.22.0` | 9042 | 内容与归档一致，已删除 |
| `runtime/graft-0.22.0-managed` | 9081 | 用户确认及重载后复验无引用／占用，已删除 |

归档位于本批 `vault/dedicated-runtime-archives/`；原有备份／回执也保留。归档证明可恢复，不等于删除授权，不等于已执行回滚。删除前须重新核对路径类型、内容和进程依赖；不删除runtime父目录、不结束用户进程、不清理历史备份。

## 重载后清理闭环

- 用户确认「批准三个，重载后删除」，随后明确会话已重载。实际复查 `pgrep/ps` 无旧目录进程引用，三个 `lsof +D` 均无打开文件；已知宿主和项目配置无旧路径引用。
- 删除前再次验证每个目录身份、完整manifest、归档SHA256；仅删除授权的三个目录，逐项保存intent与结果。归档删除后SHA256仍匹配，受管Python、Onboard和其他备份均保留，未结束任何进程。
- Orca配置文件存在与上次快照不同的其他变动；当前Graft绑定正确且无旧目录引用，因此保留原样，没有回写历史配置。
- 删除后再次运行三种zsh启动、npm全局清单及三宿主配置×五仓库的15次MCP检查，全部通过；本会话挂载的MCP实际file_api与freshness也成功。三个目录均不存在，旧目录进程引用仍为空。
- 新证据：同一私有批次的 `cleanup-ready-20261015-224222.json`、`cleanup-execution-20261015-224309.json`、`cleanup-execution-20261015-224309-verification.json` 及同stem中文汇总。本机统一与清理已收口；发布动作仍等待单独确认。

## v2.0.2 发布前置

`ReleasePrepReview` 的只读评估：双语未发布条目和源码验收记录已具备；正式发布仍blocked。当前feature分支基线是 `3e13f97b28fa29bcfb1c17d5f1e60b445228ce45` 加未提交变更，直接tag HEAD会漏掉Graft升级。公开查询未发现v2.0.2 tag／Release和对应feature PR，但正式发布前仍需重新核对。

本地收口后须向用户确认是否授权提交／推送／PR、最终main合并及精确SHA的Linux/macOS/Windows CI，再进入tag／Release。历史2142项本地验收或旧main CI不能代替新发布提交的CI。当前未执行这些远程写入。

## 维护判断和证据边界

本轮为本机部署及生成围栏更新，没有新增产品能力：README.md、README.zh.md、CHANGELOG.md、CHANGELOG.zh.md及版本化automation prompt无需改；不操作live automation。四项目业务测试未运行，因为业务实现未改；实际配置、构图、MCP和shell路径已验证。原生报告保存完整命令/stdout/stderr/exit及同stem中文汇总，rtk=skipped-for-report；developer-local、dirty、local-only。

初次参考定位scout未交付有效结果，未将其算成审查通过；父执行者完成了限定范围的实际引用检查。计划检查中的selector名称假设错误只影响临时验证器，已改按实际operation kind／target核对；没有绕过native计划。编辑工具的通用shell语法警告已用真实zsh解析及三种启动模式证明不适用，未把它当成zsh运行失败。

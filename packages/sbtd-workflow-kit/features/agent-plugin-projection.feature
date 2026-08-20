Feature: Agent Plugin 可移植 Skill 投影
  Workflow Kit 维护者需要审计 bundled Skill，并只生成可移植、可复现、可校验的 Agent Plugin 投影。

  Rule: 候选先审计后投影

    Scenario: 审计全部 portable 候选
      Given canonical Kit 已由固定 upstream revision 生成
      When 生成 Agent Plugin Skill 投影
      Then 迁移清单中的 13 个 portable 候选各有六类审计结论
      And 明确排除的 OMP 专属 Skill 不进入候选集合

    Scenario: 审计失败的 Skill 不进入投影
      Given portable 候选正文引用 OMP 专属运行时路径
      When 生成 Agent Plugin Skill 投影
      Then 该 Skill 的 disposition 为 onboard-owned
      And 输出 skills 目录不包含该 Skill

    Scenario: 审计阻塞不发布部分投影
      Given 已存在完整的 Agent Plugin Skill 投影
      And 任一 portable 候选的来源无法完成审计
      When 再次生成 Agent Plugin Skill 投影
      Then 该候选的六类审计结论均为 blocked
      And 既有完整投影保持不变

    Scenario: 脚本语法无效时不认证候选
      Given portable 候选包含无法解析的 Python 脚本
      When 生成 Agent Plugin Skill 投影
      Then reference-script 审计失败
      And 该候选不进入投影

    Scenario: 脚本依赖未声明时不认证候选
      Given portable 候选的 Python 脚本导入未声明的第三方模块
      When 生成 Agent Plugin Skill 投影
      Then runtime-dependency 审计失败
      And 该候选不进入投影

    Scenario: certified Skill 投影可复现
      Given portable 候选通过全部六类审计
      When 对同一 canonical Kit 连续生成两次 Agent Plugin Skill 投影
      Then 两次 manifest 与全部 Skill 文件字节一致
      And 每个投影 SKILL.md 只有约定的六个 frontmatter 字段

  Rule: 投影与上游提升保持 fail-closed

    Scenario: 手工修改投影后检查失败
      Given Agent Plugin Skill 投影已生成
      And 任一投影文件被手工修改
      When 执行 generated output 检查
      Then 检查因投影漂移失败

    Scenario: 上游提升必须携带完整第三树
      Given 上游候选已经生成 canonical 与 OMP 投影
      When 生成或应用上游提升计划
      Then staging 同时包含经过审计的 Agent Plugin Skill 投影
      And 缺失或额外的第三树文件会阻止提升

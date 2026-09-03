Feature: DSH T4 manuals 同步
  把 640-skills v1.0.13 白名单 skill 的 SKILL.md 与该 skill 自己的 references/ 只读同步进 manuals/，
  用 MANIFEST.json 记录 sourcePath、sha256 与 sourceRevision。不拷 skill-root markdown、安装器或整棵源树。

  Scenario: 白名单 skill 全部落在 manuals/<skill-id>/
    Given 源 revision 为 f8aa0d7225a26c5e00b81d2f1b05121108e63630
    When 运行 scripts/sync-manuals.sh
    Then manuals 含 12 个白名单目录且各有 SKILL.md
    And 包含 grill-with-docs 等 external-skills 下的 skill
    And 不含 install.sh 或 onboard.py
    And 不含 domain-modeling 的 ADR-FORMAT.md、CONTEXT-FORMAT.md 或其他 skill-root markdown 或 agents/

  Scenario: MANIFEST 与文件 checksum 一致
    Given manuals/MANIFEST.json
    Then sourceRevision 等于钉死的 SHA
    And 每个 sourcePath 落在 templates/skills 或 external-skills/stable/skills
    And 按 skills/<id>/<rest> 映射到 manuals 后 sha256 与文件内容一致

  Scenario: 源缺失或 SHA 不对则非 0
    When SOURCE 不存在
    Then 脚本以非 0 退出
    When SOURCE 的 HEAD 不是钉死 SHA
    Then 脚本以非 0 退出

  Scenario: 拷贝失败则非 0
    When SOURCE 含白名单 skill 的 references/install.sh
    Then 脚本以非 0 退出且 stderr 含 copy fail

  Scenario: checksum 失败则非 0
    When 拷贝后 dest 字节与 source blob 不一致
    Then 脚本以非 0 退出且 stderr 含 checksum fail

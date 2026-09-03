Feature: DSH T4 manuals 同步
  把 640-skills v1.0.13 白名单 skill 的 SKILL.md 与 references/ 只读同步进 manuals/，
  用 MANIFEST.json 记录 path、sha256 与 revision。不拷安装器或整棵源树。

  Scenario: 白名单 skill 全部落在 manuals/<skill-id>/
    Given 源 revision 为 f8aa0d7225a26c5e00b81d2f1b05121108e63630
    When 运行 scripts/sync-manuals.sh
    Then manuals 含 12 个白名单目录且各有 SKILL.md
    And 包含 grill-with-docs 等 external-skills 下的 skill
    And 不含 install.sh 或 onboard.py

  Scenario: MANIFEST 与文件 checksum 一致
    Given manuals/MANIFEST.json
    Then revision 等于钉死的 SHA
    And 每个 path 的 sha256 与文件内容一致

  Scenario: 源缺失或 SHA 不对则非 0
    When SOURCE 不存在
    Then 脚本以非 0 退出
    When SOURCE 的 HEAD 不是钉死 SHA
    Then 脚本以非 0 退出

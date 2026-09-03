# T4 design

## Boundary

T4 是只读同步桥，不是 runtime tool。`apply()` / `hooks.ts` / `sbtd_plan` 保持 T3。无新 `sbtd_*` tool。无 T5。

## Layout

Flat `packages/dsh-sbtd/manuals/<skill-id>/`。不采用 v1.2 全景里的 `manuals/bundled|external` 分层：白名单只有 12 个 id，flat 足够。

```
packages/dsh-sbtd/
├── scripts/sync-manuals.sh
├── manuals/
│   ├── MANIFEST.json
│   └── <id>/SKILL.md
│       └── references/   # 仅当源 skill 有该目录
├── features/t4-manuals-sync.feature
└── test/t4-manuals.test.mjs
    test/t4-sync-exit.test.mjs
```

## Source resolution

`sync-manuals.sh [SOURCE]`

- 有 SOURCE：必须是 git checkout，`rev-parse HEAD` == pin `f8aa0d7225a26c5e00b81d2f1b05121108e63630`。
- 无 SOURCE：clone `https://github.com/KunoLu/640-skills.git` 到临时目录并 checkout 该 SHA，EXIT 时删除。

每个 id 在两个根各找一次 `SKILL.md`，命中恰好一个：

1. `$SOURCE/sbtd-workflow-onboard/templates/skills/<id>`
2. `$SOURCE/sbtd-workflow-onboard/assets/external-skills/stable/skills/<id>`

两个都没有 → missing source（非 0）。两个都有 → duplicate（非 0）。不得只搜 templates。

## Copy policy

每个命中目录只拷：

- `SKILL.md` → `manuals/<id>/SKILL.md`
- 若存在 `references/` → `manuals/<id>/references/`（整目录）

明确不拷：整棵 640-skills 树、`.git`、`onboard.py`、`install.sh`、`agents/`、LICENSE、NOTICE、以及 skill 根上非 `references/` 的附件（例如 `domain-modeling/ADR-FORMAT.md`、`CONTEXT-FORMAT.md`）。

拷完若 dest 出现 `install.sh` 或 `onboard.py` → copy fail（非 0）。

## MANIFEST

`manuals/MANIFEST.json`：

```json
{
  "source": "KunoLu/640-skills",
  "version": "1.0.13",
  "sourceRevision": "f8aa0d7225a26c5e00b81d2f1b05121108e63630",
  "files": [
    {
      "sourcePath": "sbtd-workflow-onboard/templates/skills/<id>/SKILL.md",
      "sha256": "<hex>",
      "sourceRevision": "f8aa0d7225a26c5e00b81d2f1b05121108e63630"
    }
  ]
}
```

- `sourcePath`：相对 640-skills 仓根的 posix 源路径，必须落在 `templates/skills/<id>/` 或 `assets/external-skills/stable/skills/<id>/` 下。
- dest 由 `(templates|assets/external-skills/stable)/skills/<id>/<rest>` 映射为 `manuals/<id>/<rest>`。
- `sha256`：dest 文件字节的 SHA-256 hex（与源文件一致）。
- `sourceRevision`：顶层与每条记录都钉死同一 SHA。
- 写完立即按 MANIFEST 重读 dest 比对；不一致 → checksum fail（非 0）。

## Failure

| 条件 | stderr 标记 | exit |
|---|---|---|
| SOURCE 不是目录 | `missing source` | ≠ 0 |
| 无 `.git` 或 HEAD ≠ pin | `SHA mismatch` | ≠ 0 |
| 白名单 id 两个根都找不到 | `missing source skill` | ≠ 0 |
| `cp` 失败 | `copy fail` | ≠ 0 |
| dest 含 install.sh / onboard.py | `copy fail` | ≠ 0 |
| dest 与 MANIFEST 不一致 | `checksum fail` | ≠ 0 |

## Tests

- `t4-manuals.test.mjs`：12 目录、每条 `sourcePath`/`sha256`/`sourceRevision` 与 dest 字节一致、包树无 `install.sh`、tools 仍只有 `plan.ts`、README 含 pin 与「不要手改」。
- `t4-sync-exit.test.mjs`：缺失 SOURCE、用非 pin 目录 → 非 0。

## Compatibility

- `package.json` `private: true`，`files` 含 `manuals/`，peer `0.1.1-rc.2`。
- README 保持尚未发布 + `@next` 安装说明 + 宿主 pin。
- 不改根 README、不改 `hooks.ts`。

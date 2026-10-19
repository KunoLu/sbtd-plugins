# Explicit legacy identity migration

Read only after the user authorizes migration of this specific project. Ordinary lesson reading/writing, mode routing, check or global Skill installation never uses legacy identity as an automatic source. This reference defines the identity policy; it does not itself execute migration.

The legacy input is `<project>/.trellis/.developer`; the current identity is `<project>/.sbtd/developer`. Do not invoke `trellis init` or an old init_developer script. Do not derive identity from historical workspace directory names, Git/OS/environment values or old lesson markers.

The installed Onboard provides the separately authorized `migration --phase plan|apply|verify` batch interface. Use its actual installed script and Migration Runtime reference: plan validates private preparation, apply explicitly extracts the old name while preserving the full original, and verify consumes deployment evidence. Do not call this from a daily lesson write, invent a standalone identity-migration CLI, or treat this interface as completed deployment/cleanup/recovery.

## Preconditions

- Authorized project and exact operation scope are known. Preserve original data in the migration's private backup, with the manifest/evidence/repair constraints owned by Onboard's migration contract.
- Relevant roots, parents and files have verified containment/type/readability; a symlink, dangling link, directory or unsafe reserved path is not a missing file. Parse one clear `name=` value safely; a normal inherited name must match `^[a-z0-9]+$` verbatim.
- Inspect the current local identity first. Only if it is genuinely absent and its local parent path is safe may a linked worktree read the verified main checkout's current identity. A valid main identity is used in place, not copied; it prevents a local legacy-to-new identity copy. Invalid/uncertain current or main-checkout identity cannot be bypassed through the legacy file.
- When local identity is absent, verify the checkout classification before choosing a main-source or no-main-source branch. Verified non-linked includes a verified non-Git project; missing Git tooling or ambiguous metadata is not that proof and stops identity creation/migration.
- Before creating current identity, actual local ignore/tracked protection and narrow write authority must hold. A migration authorization is not permission to hide user business content, untrack data or remove legacy ignore protection prematurely.

## Decision table

Resolve the current identity chain before choosing a legacy-name branch. A present invalid/unsafe local or eligible main-checkout file is a conflict, never absence. A valid eligible main identity wins before any legacy-name decision. An "invalid name" below means a safely read, unique but nonconforming value; an unreadable/ambiguous file or unsafe path instead takes the conflict branch. Inspect only the sources needed by that precedence; other legacy inventory remains a separate migration obligation.

| Observed legacy input | Current identity / environment | Decision |
|---|---|---|
| Valid name | Current genuinely missing; verified non-linked checkout, or linked checkout with genuinely absent main current file and safe parent paths | With the authorized plan, create current identity using the unchanged legacy name; verify saved value. A present invalid main file never enters this branch. |
| Valid name | Valid current identity with the same name | Identity already matches; do not rewrite or claim a second migration. |
| Valid name | Valid current identity with a different name | Preserve both, report conflict and ask the user to choose the identity policy. Do not overwrite or rename history. |
| Invalid name | Current genuinely missing; verified non-linked checkout, or linked checkout with genuinely absent main current file and safe parent paths | Ask for a conforming user-chosen name; do not normalize the old one or call the new value an unchanged migration. A valid main identity wins instead; an invalid main file is a conflict. |
| Absent | Current valid | Use current identity; no legacy identity copy is needed. |
| Both legacy and local current files genuinely absent | Verified non-linked checkout, or linked checkout with genuinely absent main current file and safe parent paths | Follow the first-write identity question; do not invent a placeholder. Present malformed, unreadable or unsafe main files take the conflict branch. |
| Any legacy state | Current missing, valid current identity in verified main checkout | Read that identity in place; do not migrate/copy the local old identity into this worktree. |
| Invalid legacy name | Current valid | Preserve the valid current file and report the invalid legacy input for explicit migration-plan resolution; do not infer an old-to-new identity mapping or declare that copy complete. |
| Any relevant path/type/content is unsafe or ambiguous | Any | Stop the affected identity migration, preserve originals and resolve the conflict; do not fall through to another source. |

A successful new identity write proves only that identity operation, not task/lesson migration, deployment or cleanup. Recheck expected old/absent state before writing and validate afterward; retries recognize the same valid saved value rather than overwriting it. Changed current content after planning invalidates that write plan.

Keep the old identity until the full authorized migration, verification and independently confirmed cleanup have completed. Neither a same-name current file nor an identity-only success authorizes deletion. Historical lesson names, IDs, anchors and other authors' blocks stay unchanged.

Original history remains complete in private backups. Any shared projection requires separate privacy validation of text, markers, IDs and links; if that projection cannot be safe and internally consistent, block it instead of publishing private history or silently rewriting its original ownership.

## Current implementation boundary

The current-chain resolution this reference defers to is implemented by Onboard's `scripts/sbtd_identity.py` (`DeveloperStore.resolve` / `plan` / `ensure`): local valid identity first, verified linked-worktree main read in place without copying, abnormal present files as conflicts, unknown Git or worktree metadata as blocked, and first writes only after verified genuine absence with separately confirmed narrow ignore protection. That helper never opens `.trellis/.developer` during ordinary resolution. Explicit batch migration separately handles legacy reads and approved safe lesson projections; historical IDs and markers remain unchanged, and cleanup stays separately gated. Do not describe an identity created or verified by the ordinary helper as a completed legacy migration.

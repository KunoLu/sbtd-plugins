# Design -- T7 Trellis backend

## Module

`packages/dsh-sbtd/src/backends/trellis.ts` exports:

- detect(cwd) -> DetectResult
- readWorkflow(cwd) -> ReadWorkflowResult
- currentTask(cwd, sessionKey?) -> CurrentTaskResult
- writeArtifact(cwd, task, name, body) -> WriteArtifactResult

## Decisions (locked)

1. DetectResult independence -- three booleans; CLI absence never flips exists.
2. FS-first -- Node fs only for read/write/current; trellis binary solely for cliOnPath PATH probe.
3. Whitelist -- prd.md | design.md | implement.md only.
4. Session pointer -- .trellis/.runtime/sessions/<key>.json current_task; no in_progress scan.
5. Errors -- missing tree/CLI/pointer -> structured; path escape -> throw. Validate slug/name before missing-trellis (tip e9bc7cb).
6. sanitizeKey -- align with Trellis 0.6.16 _sanitize_key (tip e9bc7cb).

## Out of scope

index apply, T8 consumer wiring, physical-realpath symlink sandbox policy (FOLLOWUPS residual).

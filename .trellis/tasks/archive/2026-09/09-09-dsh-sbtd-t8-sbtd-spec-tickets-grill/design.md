# Design -- T8 grill (product forks only)

T8 tools consume T7 Trellis Backend. They are not Trellis CLI, not `to-spec`/`to-tickets` skills, not T7 reopen.

## Decisions (locked in grill, confirmed in DDD)

1. Pointer vs slug are different types. Explicit `task` wins; else strip `.trellis/tasks/`.
2. DDD unconfirmed is tool-level refuse (`blocked.kind=ddd-unconfirmed`), not host ask.
3. Has-Trellis write gate is `detect.exists` only.
4. Spec owns `prd.md`; tickets own `implement.md` slices in the same dir.
5. Both tools register from `apply()`.
6. Undetermined path is draft, not throw.

## Out of scope

Child-task creation, Channel, `trellis init`, `docs/prd` rewrite, CONTEXT/ADR disk write.

# Security Policy

## Reporting a Vulnerability

Report security vulnerabilities in `@kunolu/omp-sbtd` by email to
**songlin.lu@neox-inc.com**. Please do not open public GitHub issues for
unpatched vulnerabilities.

Include:

- the affected package version (for example `0.1.0-rc.11`);
- the Oh My Pi host version (`@oh-my-pi/pi-coding-agent` peer version);
- a minimal reproduction or the exact tool-call/prompt sequence;
- whether secret material, dependency mutation, or validation evidence is
  involved.

We acknowledge reports within 5 business days. This is a release candidate;
there is no formal SLA.

## Scope

This package intercepts host tool calls to enforce SBTD workflow gates. Its
security posture is *local-guarded*: it classifies tool risk (dependency
install, secret read, unknown capability) from event text and fails closed
when the embedded Kit or the validation evidence validator cannot be
integrity-verified.

Known limits, by design:

- Shell text parsing is best effort. Aliases, shell functions, wrappers and
  dynamic variables cannot be proven from command text; the Plugin proves
  high-confidence danger, never complete mediation.
- Approvals are typed (install vs secret-read), one-shot, bound to the exact
  input fingerprint, and never survive a tool result, deny, changed input, or
  turn boundary.

## Supported Versions

| Version | Supported |
| --- | --- |
| `0.1.0-rc.x` (latest RC) | Yes |
| older RCs | No |

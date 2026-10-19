# Tool availability, privacy and validation roles

Load the relevant section when a tool/installation/validation boundary matters. Do not inspect every tool or print a full inventory for an unrelated default/lite task. Project-defined commands and configurations win; missing capabilities must limit claims rather than fabricate results.

## Commands and managed installation

Prefer RTK for ordinary terminal output where appropriate. Missing RTK falls back to native and does not stop work. When workflow/onboard/first-command checks reveal it missing, explain that RTK compresses output without changing command semantics and ask whether to install; install only after confirmation, then verify `rtk --version` and `rtk gain`. Decline/failure means continue native and disclose the result.

Report-producing tests use native/project report-safe commands unless wrapper execution and side effects are proven. If report files are missing, stale, unchanged or show cache replay, rerun natively; cached text is not evidence. Report RTK used/skipped-for-report/fallback-native with the reason.

Onboard owns installation, update/reset, canonical Skills, paths and source integrity. An ordinary task is not permission to install runtimes/global packages, overwrite global rules, migrate user data or change an external provider. Preserve the managed stable external set and licenses, the Ponytail provider-conflict boundary, optional Caveman installation/known-family maintenance, and explicit style activation; do not fork mirrors or silently switch to upstream/latest. Check is read-only, not repair.

Public Skills bootstrap installs Onboard only; project-only does not inspect/install/configure global tools/Skills/MCP/HOME. Configuration files or package shells alone do not prove a host session or MCP works. Resolve actual active HOME/Skill roots rather than hardcoding default paths; preserve unrelated entries, comments and user modifications.

## Capability and credential boundaries

Treat a tool as available only from current callable discovery or real verified capability. Catalogs, marketplace entries, remote versions and install prompts are candidates, not current authority. If a requested special connector/library capability has a discovery tool, discover it before falling back to project facts/official docs. Do not install a neighboring plugin just because it looks useful.

Use OAuth/session/cookies/accounts only through controlled Agent/connector interfaces; never copy, print or persist secrets in repo/config examples/logs/reports. Do not alter system proxy/PAC/WPAD/enterprise network configuration without an explicit request. Distinguish an infrastructure proxy failure from application logic.

Do not silently change MCP transports, host plugins/hooks, optional startup grace, planning-tool enablement or output limits. One invalid marketplace does not invalidate others. A configured optional MCP absent on first discovery deserves a second visibility check, not an immediate reinstall. Extensions may transform tool results; raw server output is not proof of what the model received. Package-style server names containing `:`, `@`, `/` or `.` are not inherently invalid.

## Graft

Use only the supported, verified structural subset and selected repository roots. Never init/build/query a shared parent as a federation shortcut; query authorized roots independently and summarize read-only. Nested repositories/submodules need separate authorization and stay off by default. Worktree/branch/root binding must be observed, not inferred from an open server.

Managed CLI/MCP/hook entry points keep DO_NOT_TRACK=1 and prevent LLM/cloud enrichment, `--deep`, `blast --name` and automatic code/query uploads. Existing connected cloud/provider state blocks that integration plan; do not disconnect another user use silently. No ordinary task changes global env or prints API keys. If the managed privacy/side-effect safeguards are not available, use source/LSP/contract evidence instead of invoking an unsafe path.

Raw graph/blast output can contain source, diffs and Git author information. Do not upload it to PR artifacts, public viewers or knowledge systems. A requested report uses `--no-owners` where supported and a minimal redacted summary; an output request is not authorization to publish raw project data or personal identifiers.

Default local version detection must be proven read-only; `graft version` includes npm metadata lookup and is not that proof. npm lookup unreachable means unknown/unreachable, not a fabricated latest or an install loop. Authorized downloads/metadata access do not authorize code upload. Missing native dependencies or installation failure is not installation success, though unrelated safe work may continue.

Query refresh can fail, be disabled, be busy or miss unsupported/ignored changes. `check` reports freshness only and does not repair or prove business correctness; exit0/empty blast is not no-risk proof. Record actual diff basis: default blast may use the last commit when clean, and `<base>...HEAD` does not include extra working-tree changes. Account separately for untracked/deleted/renamed/mode-only/unindexed files; preserve pre-change dependency evidence where the current graph lost a deleted symbol. Basic graph grep is not a complete Markdown/YAML/Shell/JSON audit.

Never promise PDG/taint/API-route/rename parity that the tool does not provide. Six MCP tools do not imply a direct blast tool. Passive projections need their own freshness evidence; hooks stay off unless separately authorized and actually verified, with no translation of one host's hooks into another's events.

## Web / Mobile / API evidence

- Chrome DevTools MCP: runtime/console/network/storage/performance/screenshot diagnosis, not a CI pass.
- Playwright CLI/@playwright/test: repeatable Web regression/CI runner. Playwright MCP: exploration and locator assistance, not replacement for that runner.
- Maestro CLI: Mobile/Hybrid E2E and optional Web smoke runner. Maestro MCP: device/view/flow assistance, not CLI replacement.
- web-ui-autotest-generator: durable Web test assets/coverage; maestro-mobile-e2e: BDD-backed Mobile flows and report handling. They do not invent unknown contracts, accounts, devices, artifacts or selectors.
- A browser context has one controller. Use the user's selected browser for agentic operations, without treating browser exploration as the project's required E2E result.

Before installation inspect project dependencies/config/scripts and existing tests. Ask before adding project Playwright; do not install it globally. Maestro needs Java17+, recommend a current supported JDK such as Temurin21 when absent and ask before installation; then verify CLI before MCP. MCP unavailable with working CLI does not block an existing CLI flow; no CLI means no claimed run. Flow assets use the project's convention, normally `maestro/flow/`; default language/naming/report rules stay in their owning Skills.

Formal validation uses `project-validation` and the applicable runner: named native/raw report plus same-stem Chinese summary, archived outside current/overwrite directories. Keep failed reports. Unit reports belong in the unit archive; local CLI/API integration in the API archive; Playwright named HTML and same-stem MD under its formal archive; Maestro named XML/HTML and same-stem MD. Do not manufacture completion from stdout-only diagnostics. API coverage maps each actual method+URI; non-HTTP CLI integration says so instead of inventing endpoints.

Record repository key, source ref/full SHA, worktree, evidence source, environment and publication. Dirty local cannot prove PR head; revalidate final commits before publication. Publication means receipt by the target, not a pass or an automatic Git commit. Cross-repository execution needs real contracts/Revision Sets; mock/contract/smoke is not full-stack. Check every required artifact actually exists before declaring generated.

Web UI machine assets normally use `tests/e2e/manifest/{ui-test-manifest,ui-selector-audit,ui-test-coverage}.json`; keep root duplicates out and use project-validation's path contract before generator calls. A repair plan is a run artifact, not automatically a durable manifest.

## Relevant status vocabulary

Use only the fields relevant to the task, with accurate exercised scope:

- Chrome DevTools MCP: diagnosed/inspected/blocked/skipped/not-needed; Playwright MCP: explored/locator-assisted/blocked/skipped/not-needed.
- Playwright CLI: available/installed/missing/skipped-by-user/blocked; Playwright Web Tests: run/failed/blocked/skipped.
- Java: available/installed/missing/incompatible/blocked/skipped-by-user; Maestro CLI: available/installed/missing/skipped-by-user/blocked; Maestro MCP: available/configured/unavailable/blocked/skipped.
- Maestro Mobile: run-local/run-cloud/blocked/skipped/not-needed; Maestro Web Smoke: run/blocked/skipped/not-needed; Maestro Flow Assets: generated/reused/blocked/skipped; Web UI test assets: generated/coverage-only/blocked/skipped.
- Knowledge Ingest: run/partial/blocked/not-needed; Cross-repo context: complete/contract-only/environment-only/missing/not-needed; API Contract: verified/user-provided/stale/missing/not-needed.
- E2E Mode: full-stack/contract-backed/mock-backed/app-mocked/smoke-only/backend-only/blocked/not-needed; Mobile Platform Scope: ios/android/both/hybrid/not-needed; Mock Strategy: none/contract-backed/user-approved/blocked/not-needed.
- Final Test Report: generated/blocked/not-supported/not-needed; Run Summary MD: generated/blocked/not-needed; Targeted Rerun: passed/failed/blocked/not-needed; Final Full Rerun: passed/failed/blocked/skipped-with-risk/not-needed.
- Evidence Source: developer-local/ci/knowledge-server/not-needed; Source Revision: exact/dirty/unknown/not-needed; Environment Alignment: verified/unverified/mismatch/not-needed; Evidence Publication: local-only/published/blocked/not-configured/not-needed.
- SEO/GEO: audited/static-only/blocked/skipped/not-needed. Internal apps/APIs and ordinary test runs do not become SEO tasks without the relevant public/search scope.
- Graft: used/skipped/blocked/not-available, with the actual CLI/MCP surface, authorized root, observed version and coverage/freshness limitations. Report it when used or when unavailability affects the conclusion; omit the row for unrelated work.

These enums describe facts. Missing environment/data/authorization does not become passed through a label, an alternate tool or a lighter execution mode.

<p align="center">
  <a href="./README.md">EN</a>
  ·
  <a href="./README.zh.md">中文</a>
</p>

# @kunolu/omp-sbtd

OMP-hosted SBTD workflow plugin for KPi. It provides `/sbtd` commands and a fixed, read-only SBTD Kit snapshot; it does not silently install global tools or modify a project during plugin installation.

**Current source candidate: `0.2.0-rc.3`, not published.** Registry availability,
dist-tags and an rc.3 release/tag have not been verified. Local build/package
checks do not establish publication readiness or trusted §4 acceptance.

## Requirements

- `0.2.0-rc.3` declares peer `@oh-my-pi/pi-coding-agent`
  `>=18 <19`; the development dependency remains pinned to **18.11.1**.
- Official OMP **18.11.1** runs `dist/cli.js` with **Bun >=1.3.14** and its
  platform-native dependencies. Node.js/npm installation tooling is separate
  from the Host interpreter; do not launch this CLI with Node.
- Commands requiring a provider need the corresponding configured provider
  profile; CLI startup may require a default model even for local commands.

> Historical D11/rc.2 note: no omp 17.x support; prior testing targeted 18.11.1; as of the D11 lock on 2026-10-19, upstream latest was 18.12.2. This is not rc.3 Host evidence.

Peer range only decides *installable*. Installation and npm publication do
not certify host compatibility: `published`, `installable`, and `certified`
are distinct. Certified status is tracked in repository compatibility
records, not implied by installation.

Check the installed host version before installing:

```bash
omp --version
```

## Install

The commands below are the installation pins prepared for `0.2.0-rc.3`.
Publication has **not** happened yet: the 2026-11-26 lookup found `latest` and
`next` still pointing to `0.2.0-rc.2`, and moving `latest`/`next` to
`0.2.0-rc.3` has not happened either, so do not treat the moving
`@latest`/`@next` tags as this version. Historical release:
`@kunolu/omp-sbtd@0.2.0-rc.2` was published to npm on
2026-10-23 20:44:10 +08:00; `next` and `latest` pointed to it in that record.
The pins below require omp `>=18 <19`; omp 17.x users must explicitly pin an
older 0.1.x.

For authorized rc.3 candidate testing before publication, use the exact
reviewed local `kunolu-omp-sbtd-0.2.0-rc.3.tgz` through an isolated npm
tarball installation workflow, not a source-directory link or an assumed
Registry `@0.2.0-rc.3`. This candidate preparation does not itself install the
package, and the pins below apply only once `0.2.0-rc.3` is actually
published.

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.3
```

OMP installs to user scope by default. To install only for the current project:

```bash
omp plugin install --scope project @kunolu/omp-sbtd@0.2.0-rc.3
```

Open a new OMP session after installation, then verify the plugin and command registry:

```bash
omp plugin list
omp plugin doctor
```

```text
/sbtd help
```

Prior cloud installation/session evidence used local **rc.2** tarball SHA256
`0375a386b98d3f79aa512681e842ecc8b62539a2c4b1320d6ea6d4031f347610`
with official 18.11.1/Bun. Four commands completed through the official SDK/RPC
session; the CLI attempt stopped before dispatch because no default model was
configured. Neither result transfers to the new rc.3 tarball or proves trusted
§4, CLI/TUI, model or full-Host acceptance.

## Embedded workflow

The canonical vendor/lock base remains **640-skills v2.0.2**
(`1d82494d74f6df9bca7dccef2da409f87091883e`), with transform version
`p0-v4`. The closed `r1-manuals` partial selection comprises **six file
operations across four Skills**: domain-modeling's SKILL update, CONTEXT-FORMAT
removal and GLOSSARY-FORMAT addition; grilling and to-tickets SKILL updates;
and sbtd-task's presentation reference update. This is not a whole-upstream
v2.1.0 upgrade. Exact source/license identities remain in the Kit provenance.
Sync, projection and generation live in this package; supply-chain source ID
`sbtd-workflow-kit-upstream` is unchanged.

The bundle includes all 33 upstream Python scripts, nine runtime assets,
two schemas, and the `sbtd-task` template tree (eight template files, plus LICENSE and NOTICE). Recognized
dependency-requiring SBTD Python commands, including upgrade and migration,
use an isolated preflight for the five pinned dependencies in
`kit/onboard/runtime/requirements.txt`: `jsonschema`, `PyYAML`,
`markdown-it-py`, `tomlkit`, and `cryptography`. Missing dependencies fail
closed; signature verification refuses to run without `cryptography`.
There is no automatic installation or skipped fallback. Standard-library-only
onboard commands remain usable; this host guard is not a general shell sandbox.

The onboard Skill catalog uses `sbtd-task` instead of `trellis-workflow` and
`trellis-channel`. Read-only task observation recognizes `in-progress` and
`checking` under `ai/tasks/**` and `.sbtd/tasks/**`; legacy `.trellis`
observation remains read-only. Task state writing stays with `sbtd-task`.

**Handoff evidence:** the `omp-extension-v2` contract and
`omp-host-events-v2` profile require `session_compact` (13 required events
plus 1 optional event). A successful handoff requires a correlated event with
`compactionEntry.method === "handoff"`; missing method or competing compact
in the window fails. `HANDOFF_EVENT_UNOBSERVABLE` is a hard failure.
The omp 18.11.1 install-path smoke is not model end-to-end testing or full
host-event certification.

## Platform support

This package declares no `os` or `cpu` restriction and contains no native binary dependency of its own. Runtime support follows the official OMP Host, including its Bun interpreter and platform-native dependencies; Node.js/npm installation tooling is a separate requirement.

- **macOS and Linux:** no package-level restriction is declared.
- **Windows:** installation requires a supported official OMP/Bun/native environment; no Windows acceptance is claimed here. The bundled `/sbtd onboard` bootstrap does not automate native-Windows Node.js/npm installation; install Node.js/npm first (for example with nvm-windows, nvs, or an approved equivalent).
- **Publish helper:** `docs/deploy/publish-omp-sbtd.sh` is the only approved Registry writer. Run it from Bash on macOS, Linux, WSL, or Git Bash—not directly in `/bin/sh` or PowerShell. Windows users must use that helper from a Bash-capable shell; do not substitute a direct `npm publish` command.

## Publishing an RC release

Published npm tarballs are immutable. Build and pack one new prerelease tarball;
do not reuse a tarball that has already been published.

Publication requires the trusted `omp-section4-publish-gate` workflow to build
and pack from an immutable `main` SHA and pass the four-command acceptance for
that **same full tarball digest**: `/sbtd help`, `/sbtd status`, `/sbtd report`,
and `/sbtd onboard plan`, without a Provider request, approval or unexpected
write. Local SDK/API tests, build checks or a locally packed candidate do not
substitute for this trusted run. See the repository
[`handbook §3/§4`](../../docs/assets/omp/omp-plugin-host-acceptance.md).

The repository helper then publishes that same tarball only to `next`:

```bash
export NPM_TOKEN='npm access token'
docs/deploy/publish-omp-sbtd.sh /absolute/path/kunolu-omp-sbtd-<version>.tgz --tag next
```

The helper rejects a stable version, another package, `latest` or any other
dist-tag, an occupied version, and an unknown Registry availability result
before it can call `npm publish`.
The operator must separately verify the trusted run, source SHA and full
artifact digest: the helper does not verify §4 evidence itself. An authorized
publish also requires a fresh, explicit Registry-availability result.

The authorized follow-up release plan for `0.2.0-rc.3` is to publish the
package with the helper to `next` and then also point `latest` (and `next`) at
`0.2.0-rc.3`; the helper itself still only accepts `--tag next`, and this
plan has not been executed yet.

`NPM_TOKEN` must be an npm access token with **Read and write** permission for
`@kunolu/omp-sbtd` or its scope. If the account or organization requires 2FA,
configure the token with **Bypass two-factor authentication** or provide the
required OTP; otherwise `npm publish` may still request an OTP.

### Optional repository-local `.env`

The repository already ignores a root `.env`. It may contain only the local secret reference:

```dotenv
NPM_TOKEN=npm_your_token_value
```

Keep that file private and owner-readable only:

```bash
chmod 600 .env
```

The helper resolves credentials in this order:

1. A non-empty literal `NPM_TOKEN=<token>` assignment in the repository-root `.env`.
2. A non-empty inherited `NPM_TOKEN` environment variable when `.env` is absent or that assignment is empty.

The helper parses `.env` as data and never sources or executes it. It accepts the literal assignment form above; other lines are ignored. Therefore a `.env` token overrides an inherited environment token. Invoke the helper directly:

```bash
docs/deploy/publish-omp-sbtd.sh /absolute/path/kunolu-omp-sbtd-<version>.tgz --tag next
```

The helper never accepts a token argument, prints no token value, and passes npm an owner-only temporary userconfig containing only the literal `${NPM_TOKEN}` reference.

## Support

- Issues: <https://github.com/KunoLu/sbtd-plugins/issues>
- Security reports: see [SECURITY.md](./SECURITY.md) (email
  songlin.lu@neox-inc.com; no public issues for unpatched vulnerabilities).
- Release candidates carry no formal SLA; the latest RC line is the only
  supported one.

## Data handling and telemetry

This Plugin collects **no telemetry** and makes **no network calls** of its
own. All observations run locally: session state is appended to the host's
session entries (`kpi.sbtd.session.v1`), and validation evidence descriptors
persist only SHA-256 fingerprints (scenario locator digest, report digest,
sidecar digest, commit), never file contents, secrets, or prompt text. The
embedded validator (`python3 validate_validation_evidence.py`) reads only
files inside the project root.

## Uninstall and rollback

1. Remove the extension from your OMP config (or
   `npm uninstall -g @kunolu/omp-sbtd` for a global install).
2. Delete session state: remove `kpi.sbtd.session.v1` entries via your host's
   session management, or start a new session — the Plugin holds no state
  outside the session log.
3. Rollback: install the previous RC (`npm install -g
   @kunolu/omp-sbtd@<previous-rc>`). Older readers ignore the additive
   `validationEvidence` descriptor field, so state written by this version
   remains readable.

## License

Apache-2.0. See [LICENSE](./LICENSE) and [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).

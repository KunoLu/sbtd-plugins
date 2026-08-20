# @kunolu/omp-sbtd

OMP-hosted SBTD workflow plugin. It provides `/sbtd` commands and a fixed, read-only SBTD Kit snapshot; it does not silently install global tools or modify a project during plugin installation.

## Requirements

- Oh My Pi / OMP with `@oh-my-pi/pi-coding-agent` **17.3.5**. The package declares this exact peer dependency.
- An authenticated OMP provider profile for commands that need a provider.

Check the installed host version before installing:

```bash
omp --version
```

## Install

Pin the release version for a reproducible installation:

```bash
omp plugin install @kunolu/omp-sbtd@0.1.0-rc.11
```

RC 版本始终显式安装；RC 发布不会使用 npm 的 `latest` tag：

```bash
omp plugin install @kunolu/omp-sbtd@0.1.0-rc.11
```

OMP installs to user scope by default. To install only for the current project:

```bash
omp plugin install --scope project @kunolu/omp-sbtd@0.1.0-rc.11
```

Open a new OMP session after installation, then verify the plugin and command registry:

```bash
omp plugin list
omp plugin doctor
```

```text
/sbtd help
```

## Platform support

This package declares no `os` or `cpu` restriction and contains no native binary dependency. Its runtime support therefore follows the installed OMP host and Node.js environment, rather than the npm package itself.

- **macOS and Linux:** no package-level restriction is declared.
- **Windows:** the plugin may be installed where OMP and its required Node.js runtime are supported. The bundled `/sbtd onboard` bootstrap does not automate native-Windows Node.js/npm installation; install Node.js/npm first (for example with nvm-windows, nvs, or an approved equivalent).
- **Publish helper:** `docs/deploy/publish-omp-sbtd.sh` is the only approved Registry writer. Run it from Bash on macOS, Linux, WSL, or Git Bash—not directly in `/bin/sh` or PowerShell. Windows users must use that helper from a Bash-capable shell; do not substitute a direct `npm publish` command.

## Publishing an RC release

Published npm tarballs are immutable. Build and pack one new prerelease tarball;
do not reuse a tarball that has already been published.

Before publishing, run the repository handbook's isolated exact-tarball
four-command acceptance: `/sbtd help`, `/sbtd status`, `/sbtd report`, and
`/sbtd onboard plan`. The commands must complete without a Provider request,
approval, or unexpected write. The detailed procedure and cleanup boundary are
in [`docs/assets/omp-plugin-host-acceptance.md`](../../docs/assets/omp-plugin-host-acceptance.md).

The repository helper then publishes that same tarball only to `next`:

```bash
export NPM_TOKEN='npm access token'
docs/deploy/publish-omp-sbtd.sh /absolute/path/kunolu-omp-sbtd-0.1.0-rc.11.tgz --tag next
```

The helper rejects a stable version, another package, `latest` or any other
dist-tag, an occupied version, and an unknown Registry availability result
before it can call `npm publish`.

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
docs/deploy/publish-omp-sbtd.sh /absolute/path/kunolu-omp-sbtd-0.1.0-rc.11.tgz --tag next
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

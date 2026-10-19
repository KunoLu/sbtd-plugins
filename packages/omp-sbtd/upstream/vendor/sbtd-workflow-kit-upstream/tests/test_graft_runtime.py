from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "sbtd-workflow-onboard" / "scripts" / "graft_runtime.py"

spec = importlib.util.spec_from_file_location("graft_runtime", RUNTIME)
assert spec is not None and spec.loader is not None
graft_runtime = importlib.util.module_from_spec(spec)
sys.modules["graft_runtime"] = graft_runtime
spec.loader.exec_module(graft_runtime)

PINNED = graft_runtime.GRAFT_PINNED_VERSION


class GraftRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="graft-runtime-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name).resolve()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.prefix = self.root / "npm-prefix"
        (self.prefix / "bin").mkdir(parents=True)
        (self.prefix / "lib" / "node_modules").mkdir(parents=True)
        # PATH mirrors a real machine: the managed bin dir plus the npm global
        # bin directory (where a global install exposes the graft executable).
        self.env = {
            "PATH": str(self.bin_dir) + os.pathsep + str(self.prefix / "bin"),
            "HOME": str(self.home),
            # Hostile inherited activation/trackable variables that managed
            # subprocesses must never see.
            "GRAFT_API_KEY": "secret-graft",
            "OPENROUTER_API_KEY": "secret-openrouter",
            "ORCAROUTER_API_KEY": "secret-orcarouter",
            "OPENAI_API_KEY": "secret-openai",
            "ANTHROPIC_API_KEY": "secret-anthropic",
            "NODE_OPTIONS": "--require /tmp/evil.js",
            "NODE_PATH": "/tmp/evil",
            "DOTENV_CONFIG_DEBUG": "true",
            "DOTENV_CONFIG_QUIET": "false",
        }
        self.env_patch = mock.patch.dict(os.environ, self.env, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    # -- fixture helpers -------------------------------------------------

    def write_executable(self, name: str, body: str) -> Path:
        target = self.bin_dir / name
        target.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        return target

    def make_package_layout(
        self,
        *,
        package_version: str = PINNED,
        cli_version: str | None = PINNED,
        cli_exit: int = 0,
        env_capture: Path | None = None,
    ) -> Path:
        """Real on-disk npm global layout: package + bin symlink → cli.js."""
        pkg_dir = self.prefix / "lib" / "node_modules" / "@nanonets" / "graft"
        (pkg_dir / "dist").mkdir(parents=True, exist_ok=True)
        (pkg_dir / "package.json").write_text(
            json.dumps({"name": "@nanonets/graft", "version": package_version}),
            encoding="utf-8",
        )
        capture_line = (
            f"/usr/bin/env > {env_capture}\n" if env_capture is not None else ""
        )
        version_line = f"echo {cli_version}\n" if cli_version is not None else ""
        cli = pkg_dir / "dist" / "cli.js"
        cli.write_text(
            f"#!/bin/sh\n{capture_line}{version_line}exit {cli_exit}\n",
            encoding="utf-8",
        )
        cli.chmod(cli.stat().st_mode | stat.S_IXUSR)
        link = self.bin_dir / "graft"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(cli)
        return pkg_dir

    def make_node(self, version: str = "v20.11.0") -> None:
        self.write_executable("node", f'#!/bin/sh\necho "{version}"\n')

    def make_npm(
        self,
        *,
        version: str = "12.0.2",
        install: str = "success",
        install_pkg_version: str = PINNED,
        install_cli_version: str = PINNED,
        prefix_broken: bool = False,
    ) -> tuple[Path, Path]:
        """Fake npm handling --version/config get prefix/root -g/install.

        install: "success" materializes the pinned package layout like a real
        global install; "broken-cli" installs valid metadata whose CLI crashes
        at startup; anything else fails like a native build error.
        prefix_broken makes prefix resolution fail (config get prefix exits 1,
        prefix -g is unhandled). Sets self.npm_probe_env to the probe-env
        capture path. Returns (argv_log, npm_install_env_capture).
        """
        argv_log = self.root / "npm-argv.log"
        npm_env = self.root / "npm-env.log"
        cli_env = self.root / "cli-env.log"
        self.npm_probe_env = self.root / "npm-probe-env.log"
        pkg_dir = "$PREFIX/lib/node_modules/@nanonets/graft"
        if install == "success":
            cli_body = [
                "#!/bin/sh",
                f"/usr/bin/env > {cli_env}",
                f"echo {install_cli_version}",
            ]
        elif install == "broken-cli":
            cli_body = ["#!/bin/sh", "echo native crash >&2", "exit 1"]
        else:
            cli_body = []
        if prefix_broken:
            config_branch = ["  exit 1"]
        else:
            config_branch = [
                '  if [ "$2" = "get" ] && [ "$3" = "prefix" ]; then',
                f"    echo {self.prefix}",
                "    exit 0",
                "  fi",
                "  exit 1",
            ]
        lines = [
            "#!/bin/sh",
            f"printf '%s\\n' \"$@\" >> {argv_log}",
            'case "$1" in',
            "--version)",
            f'  echo "{version}"',
            "  exit 0",
            "  ;;",
            "config)",
            f"  /usr/bin/env > {self.npm_probe_env}",
            *config_branch,
            "  ;;",
            "root)",
            f"  /usr/bin/env > {self.npm_probe_env}",
            f"  echo {self.prefix}/lib/node_modules",
            "  exit 0",
            "  ;;",
            "install)",
            f"  /usr/bin/env > {npm_env}",
        ]
        if cli_body:
            lines += [
                '  PREFIX=""',
                "  while [ $# -gt 0 ]; do",
                '    if [ "$1" = "--prefix" ]; then shift; PREFIX="$1"; fi',
                "    shift",
                "  done",
                f'  /bin/mkdir -p "{pkg_dir}/dist" "$PREFIX/bin"',
                f"  /bin/cat > \"{pkg_dir}/package.json\" <<'JSON'",
                json.dumps({"name": "@nanonets/graft", "version": install_pkg_version}),
                "JSON",
                f"  /bin/cat > \"{pkg_dir}/dist/cli.js\" <<'CLI'",
                *cli_body,
                "CLI",
                f'  /bin/chmod +x "{pkg_dir}/dist/cli.js"',
                '  /bin/ln -sf ../lib/node_modules/@nanonets/graft/dist/cli.js "$PREFIX/bin/graft"',
                "  exit 0",
            ]
        else:
            lines += [
                '  echo "npm ERR! tree-sitter-kotlin native build failed" >&2',
                "  exit 1",
            ]
        lines += ["  ;;", "esac", "exit 1"]
        self.write_executable("npm", "\n".join(lines) + "\n")
        return argv_log, npm_env

    def fake_fetch(self, payload: bytes = b"fixture-tarball"):
        records: dict[str, object] = {}

        def _fetch(url: str, dest: Path, timeout: int) -> None:
            records["url"] = url
            records["dest"] = dest
            records["parentMode"] = stat.S_IMODE(dest.parent.stat().st_mode)
            dest.write_bytes(payload)

        self.fetch_records = records
        return mock.patch.object(graft_runtime, "_fetch_tarball", side_effect=_fetch)

    def patch_integrity_for(self, payload: bytes):
        digest = base64.b64encode(hashlib.sha512(payload).digest()).decode("ascii")
        return mock.patch.object(
            graft_runtime, "GRAFT_TARBALL_INTEGRITY", f"sha512-{digest}"
        )

    def npm_invocations(self, argv_log: Path) -> list[list[str]]:
        if not argv_log.exists():
            return []
        lines = argv_log.read_text(encoding="utf-8").splitlines()
        # Each invocation was logged as one line per argument; --version /
        # config / root are 1-3 args, install starts with "install".
        calls: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if line in ("--version", "config", "root", "install"):
                if current:
                    calls.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            calls.append(current)
        return calls

    def npm_install_calls(self, argv_log: Path) -> list[list[str]]:
        return [c for c in self.npm_invocations(argv_log) if c and c[0] == "install"]

    def home_snapshot(self) -> dict[str, tuple[bytes, int]]:
        snapshot: dict[str, tuple[bytes, int]] = {}
        for path in sorted(self.home.rglob("*")):
            rel = str(path.relative_to(self.home))
            if path.is_file() and not path.is_symlink():
                st = path.stat()
                snapshot[rel] = (path.read_bytes(), st.st_mtime_ns)
        return snapshot

    def read_env_capture(self, path: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            result[key] = value
        return result

    # -- check_graft ------------------------------------------------------

    def test_check_reports_not_available_without_graft_or_npm(self) -> None:
        result = graft_runtime.check_graft()
        self.assertEqual(result["name"], "graft")
        self.assertEqual(result["category"], "cli")
        self.assertFalse(result["installed"])
        self.assertFalse(result["packagePresent"])
        self.assertIsNone(result["path"])
        self.assertEqual(result["status"], "not-available")
        self.assertEqual(result["pinnedVersion"], PINNED)
        self.assertIsNone(result["projectInstall"])
        self.assertIn(PINNED, str(result["nextStep"]))

    def test_check_does_not_execute_unrecognized_graft_binary(self) -> None:
        marker = self.root / "unowned-executed.marker"
        self.write_executable(
            "graft",
            f"#!/bin/sh\n/bin/echo ran > {marker}\necho 1.0.0\n",
        )
        result = graft_runtime.check_graft()
        self.assertFalse(result["installed"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["identity"], "unknown")
        self.assertFalse(result["packagePresent"])
        self.assertIn("not executed", str(result["reason"]))
        self.assertFalse(
            marker.exists(), "unrecognized graft binary must never be executed"
        )

    def test_check_rejects_package_name_in_unowned_shim_without_execution(self) -> None:
        self.make_package_layout()
        link = self.bin_dir / "graft"
        link.unlink()
        marker = self.root / "spoofed-shim-executed"
        shim = self.prefix / "bin" / "graft"
        shim.write_text(
            f"#!/bin/sh\n# @nanonets/graft\n/bin/echo ran > {marker}\necho {PINNED}\n",
            encoding="utf-8",
        )
        shim.chmod(0o700)
        result = graft_runtime.check_graft()
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["installed"])
        self.assertFalse(marker.exists())

    def test_check_rejects_other_package_file_as_cli_without_execution(self) -> None:
        package = self.make_package_layout()
        marker = self.root / "wrong-target-executed"
        other = package / "other.js"
        other.write_text(
            f"#!/bin/sh\n/bin/echo ran > {marker}\necho {PINNED}\n",
            encoding="utf-8",
        )
        other.chmod(0o700)
        link = self.bin_dir / "graft"
        link.unlink()
        link.symlink_to(other)
        result = graft_runtime.check_graft()
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(marker.exists())

    def test_check_accepts_official_npm_bin(self) -> None:
        package = self.make_package_layout()
        official = package / "dist" / "bin" / "graft.js"
        official.parent.mkdir()
        official.write_text(f"#!/bin/sh\necho {PINNED}\n", encoding="utf-8")
        official.chmod(0o700)
        link = self.bin_dir / "graft"
        link.unlink()
        link.symlink_to(official)

        result = graft_runtime.check_graft()

        self.assertEqual(result["status"], "available")
        self.assertTrue(result["installed"])
        self.assertEqual(result["version"], PINNED)


    def test_install_verification_rejects_unowned_prefix_command(self) -> None:
        self.make_package_layout()
        marker = self.root / "unowned-installed-command"
        executable = self.prefix / "bin" / "graft"
        executable.write_text(
            f"#!/bin/sh\n# @nanonets/graft\n/bin/echo ran > {marker}\necho {PINNED}\n",
            encoding="utf-8",
        )
        executable.chmod(0o700)
        usable, _, partial = graft_runtime._verify_installation(self.env, self.prefix)
        self.assertFalse(usable)
        self.assertTrue(partial)
        self.assertFalse(marker.exists())

    def test_check_blocks_unsupported_version(self) -> None:
        self.make_package_layout(package_version="0.17.0", cli_version="0.17.0")
        result = graft_runtime.check_graft()
        self.assertFalse(result["installed"])
        self.assertTrue(result["packagePresent"])
        self.assertEqual(result["packageVersion"], "0.17.0")
        self.assertEqual(result["version"], "0.17.0")
        self.assertEqual(result["status"], "blocked")
        self.assertIn(PINNED, str(result["reason"]))

    def test_check_accepts_verified_pinned_cli_without_npm(self) -> None:
        self.make_package_layout()
        # No npm/node fixtures on PATH: check must still prove local capability.
        result = graft_runtime.check_graft()
        self.assertTrue(result["installed"])
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["version"], PINNED)
        self.assertEqual(result["identity"], "nanonets-package")
        self.assertTrue(result["packagePresent"])
        self.assertEqual(Path(str(result["path"])).name, "graft")

    def test_check_blocks_verified_pinned_cli_on_unsupported_node(self) -> None:
        self.make_node("v18.20.0")
        self.make_package_layout()
        result = graft_runtime.check_graft()
        self.assertFalse(result["installed"])
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["node"]["compatible"])
        self.assertIn("Node", str(result["reason"]))

    def test_check_forces_dotenv_quiet_mode_for_version_probe(self) -> None:
        capture = self.root / "check-cli-env.log"
        self.make_package_layout(env_capture=capture)
        result = graft_runtime.check_graft()
        self.assertTrue(result["installed"])
        probe_env = self.read_env_capture(capture)
        self.assertNotIn("DOTENV_CONFIG_DEBUG", probe_env)
        self.assertEqual(probe_env.get("DOTENV_CONFIG_QUIET"), "true")

    def test_check_distinguishes_package_present_from_usable_cli(self) -> None:
        pkg_dir = self.prefix / "lib" / "node_modules" / "@nanonets" / "graft"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "package.json").write_text(
            json.dumps({"name": "@nanonets/graft", "version": PINNED}),
            encoding="utf-8",
        )
        self.make_npm()  # npm root -g exposes the package; no bin/graft exists
        result = graft_runtime.check_graft()
        self.assertFalse(result["installed"])
        self.assertTrue(result["packagePresent"])
        self.assertEqual(result["packageVersion"], PINNED)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("no usable `graft` executable", str(result["reason"]))

    def test_check_blocks_native_startup_failure(self) -> None:
        self.make_package_layout(cli_version=None, cli_exit=1)
        result = graft_runtime.check_graft()
        self.assertFalse(result["installed"])
        self.assertTrue(result["packagePresent"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("exit code 1", str(result["reason"]))

    def test_check_version_probe_uses_sanitized_env_and_writes_nothing(self) -> None:
        capture = self.root / "check-cli-env.log"
        self.make_package_layout(env_capture=capture)
        before = self.home_snapshot()
        result = graft_runtime.check_graft()
        self.assertTrue(result["installed"])
        probe_env = self.read_env_capture(capture)
        self.assertEqual(probe_env.get("DO_NOT_TRACK"), "1")
        self.assertEqual(probe_env.get("DNT"), "1")
        self.assertEqual(probe_env.get("DOTENV_CONFIG_PATH"), os.devnull)
        for scrubbed in (
            "GRAFT_API_KEY",
            "OPENROUTER_API_KEY",
            "ORCAROUTER_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "NODE_OPTIONS",
            "NODE_PATH",
        ):
            self.assertNotIn(scrubbed, probe_env)
        self.assertNotEqual(probe_env.get("CI"), "1")
        self.assertEqual(before, self.home_snapshot(), "check must not write to HOME")

    # -- install_graft: confirmation gate ---------------------------------

    def test_install_without_confirmation_makes_zero_writes(self) -> None:
        self.make_node()
        argv_log, _ = self.make_npm()
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=False)
            fetch.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(result["mode"], "install-graft")
        self.assertEqual(result["status"], "needs-confirmation")
        self.assertEqual(self.npm_install_calls(argv_log), [])
        self.assertFalse(
            (self.home / ".graft").exists(),
            "unconfirmed run must not create ~/.graft",
        )

    def test_install_plan_is_readonly_and_explicit(self) -> None:
        self.make_node()
        self.make_npm(version="12.0.2")
        result, code = graft_runtime.install_graft(confirmed=False)
        self.assertEqual(code, 2)
        plan = result["plan"]
        self.assertEqual(plan["package"], f"@nanonets/graft@{PINNED}")
        self.assertEqual(plan["integrity"], graft_runtime.GRAFT_TARBALL_INTEGRITY)
        self.assertEqual(plan["tarballUrl"], graft_runtime.GRAFT_TARBALL_URL)
        self.assertEqual(plan["prefix"], str(self.prefix))
        self.assertEqual(
            plan["telemetry"]["path"], str(self.home / ".graft" / "telemetry.json")
        )
        self.assertEqual(plan["telemetry"]["changes"], {"enabled": False})
        self.assertTrue(plan["telemetry"]["preservesUnknownKeys"])
        self.assertEqual(
            plan["npm"]["allowScripts"], list(graft_runtime.NPM12_ALLOW_SCRIPTS)
        )
        self.assertFalse(plan["npm"]["ignoreScripts"])
        self.assertIn("<verified-tarball>", plan["command"])
        self.assertEqual(plan["env"]["DO_NOT_TRACK"], "1")
        self.assertEqual(plan["env"]["CI"], "1")

    def test_unconfirmed_probe_reports_blockers_without_prompting(self) -> None:
        # npm missing entirely: the probe must surface blocked (not
        # needs-confirmation) so wrappers never prompt for an impossible
        # install.
        self.make_node()
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=False)
            fetch.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "npm")
        self.assertFalse((self.home / ".graft").exists())

    def test_unconfirmed_probe_reports_already_installed_readonly(self) -> None:
        self.make_package_layout()
        graft_dir = self.home / ".graft"
        graft_dir.mkdir()
        target = graft_dir / "telemetry.json"
        original = b'{"enabled": false, "installId": "abc-123"}\n'
        target.write_bytes(original)
        result, code = graft_runtime.install_graft(confirmed=False)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "already-installed")
        self.assertFalse(result["telemetry"]["changed"])
        self.assertEqual(target.read_bytes(), original)

    def test_unconfirmed_probe_with_pending_telemetry_change_needs_confirmation(
        self,
    ) -> None:
        self.make_package_layout()
        graft_dir = self.home / ".graft"
        graft_dir.mkdir()
        target = graft_dir / "telemetry.json"
        original = b'{"enabled": true, "installId": "abc-123"}\n'
        target.write_bytes(original)
        result, code = graft_runtime.install_graft(confirmed=False)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "needs-confirmation")
        self.assertEqual(
            target.read_bytes(), original, "unconfirmed probe must not write"
        )

    def test_telemetry_only_confirmation_fails_closed_after_cli_disappears(
        self,
    ) -> None:
        argv_log, _ = self.make_npm()
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(
                confirmed=True, telemetry_only=True
            )
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "telemetry-only")
        self.assertEqual(self.npm_install_calls(argv_log), [])
        fetch.assert_not_called()

    def test_npm_probes_use_isolated_cache_and_leave_home_unchanged(self) -> None:
        self.make_node()
        self.make_npm()
        before = self.home_snapshot()
        result, code = graft_runtime.install_graft(confirmed=False)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "needs-confirmation")
        self.assertEqual(self.home_snapshot(), before)
        probe_env = self.read_env_capture(self.npm_probe_env)
        cache = probe_env.get("NPM_CONFIG_CACHE", "")
        self.assertIn("graft-npm-probe-", cache)
        self.assertFalse(
            Path(cache).exists(), "probe cache must be removed after probing"
        )
        self.assertNotIn(str(self.home), cache)

    def test_check_npm_probe_uses_isolated_cache(self) -> None:
        self.make_npm()
        before = self.home_snapshot()
        result = graft_runtime.check_graft()
        self.assertEqual(result["status"], "not-available")
        probe_env = self.read_env_capture(self.npm_probe_env)
        cache = probe_env.get("NPM_CONFIG_CACHE", "")
        self.assertIn("graft-npm-probe-", cache)
        self.assertFalse(Path(cache).exists())
        self.assertEqual(before, self.home_snapshot())

    def test_install_blocks_when_prefix_unresolvable(self) -> None:
        self.make_node()
        argv_log, _ = self.make_npm(prefix_broken=True)
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
            fetch.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "prefix")
        self.assertIsNone(result["plan"]["prefix"])
        self.assertEqual(self.npm_install_calls(argv_log), [])

    # -- install_graft: prerequisite/conflict blockers ---------------------

    def test_install_blocks_without_node(self) -> None:
        self.make_npm()
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
            fetch.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "node")

    def test_install_blocks_incompatible_node(self) -> None:
        self.make_node("v18.19.0")
        self.make_npm()
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
            fetch.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "node")
        self.assertIn("v18.19.0", str(result["reason"]))

    def test_install_blocks_without_npm(self) -> None:
        self.make_node()
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
            fetch.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "npm")

    def test_install_blocks_unowned_executable_conflict(self) -> None:
        self.make_node()
        argv_log, _ = self.make_npm()
        marker = self.root / "unowned-executed.marker"
        self.write_executable(
            "graft",
            f"#!/bin/sh\n/bin/echo ran > {marker}\necho 1.0.0\n",
        )
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
            fetch.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "conflict")
        self.assertEqual(self.npm_install_calls(argv_log), [])
        self.assertFalse(marker.exists())

    # -- install_graft: operational failures -------------------------------

    def test_install_fails_on_integrity_mismatch(self) -> None:
        self.make_node()
        argv_log, _ = self.make_npm()
        # Real frozen integrity constant: fixture bytes cannot match it.
        with self.fake_fetch(b"tampered-bytes") as fetch:
            result, code = graft_runtime.install_graft(confirmed=True)
            fetch.assert_called_once()
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "verify-integrity")
        self.assertFalse(result["partialInstallation"])
        self.assertEqual(self.npm_install_calls(argv_log), [])
        self.assertFalse((self.home / ".graft").exists())
        destination = self.fetch_records["dest"]
        assert isinstance(destination, Path)
        self.assertFalse(
            destination.exists(),
            "private temp storage must be cleaned up",
        )

    def test_install_reports_npm_failure_stage(self) -> None:
        self.make_node()
        argv_log, _ = self.make_npm(install="fail")
        payload = b"fixture-tarball"
        with self.fake_fetch(payload), self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "npm-install")
        self.assertIn("tree-sitter-kotlin", str(result.get("npmStderr")))
        self.assertFalse(result["partialInstallation"])
        self.assertEqual(len(self.npm_install_calls(argv_log)), 1)
        self.assertFalse((self.home / ".graft").exists())

    def test_install_reports_verification_failure_for_wrong_version(self) -> None:
        self.make_node()
        self.make_npm(install_pkg_version="0.17.0", install_cli_version="0.17.0")
        payload = b"fixture-tarball"
        with self.fake_fetch(payload), self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "verify-install")
        self.assertIn("0.17.0", str(result["reason"]))
        self.assertTrue(result["partialInstallation"])
        # Failure must not claim success and must not persist telemetry.
        self.assertFalse((self.home / ".graft" / "telemetry.json").exists())

    def test_install_reports_native_verification_failure(self) -> None:
        self.make_node()
        # npm exits 0 and installs valid pinned metadata, but the CLI itself
        # crashes at startup (e.g. missing tree-sitter native build).
        self.make_npm(install="broken-cli")
        payload = b"fixture-tarball"
        with self.fake_fetch(payload), self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "verify-install")
        self.assertIn("not runnable", str(result["reason"]))
        self.assertTrue(result["partialInstallation"])
        self.assertFalse((self.home / ".graft" / "telemetry.json").exists())

    # -- install_graft: success path ---------------------------------------

    def test_install_success_verifies_and_persists_telemetry(self) -> None:
        self.make_node("v24.15.0")
        argv_log, npm_env = self.make_npm(version="12.0.2")
        payload = b"fixture-tarball"
        with self.fake_fetch(payload), self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["before"]["status"], "not-available")
        self.assertTrue(result["after"]["installed"])
        self.assertEqual(result["after"]["version"], PINNED)

        install_calls = self.npm_install_calls(argv_log)
        self.assertEqual(len(install_calls), 1)
        argv = install_calls[0]
        self.assertIn("-g", argv)
        self.assertIn("--ignore-scripts=false", argv)
        self.assertIn("--foreground-scripts", argv)
        prefix_index = argv.index("--prefix")
        self.assertEqual(argv[prefix_index + 1], str(self.prefix))
        allow = [a for a in argv if a.startswith("--allow-scripts=")]
        self.assertEqual(len(allow), 1)
        self.assertEqual(
            allow[0][len("--allow-scripts=") :].split(","),
            list(graft_runtime.NPM12_ALLOW_SCRIPTS),
        )
        self.assertTrue(argv[-1].endswith(f"graft-{PINNED}.tgz"))

        npm_child_env = self.read_env_capture(npm_env)
        self.assertEqual(npm_child_env.get("CI"), "1")
        self.assertEqual(npm_child_env.get("DNT"), "1")
        self.assertEqual(npm_child_env.get("DO_NOT_TRACK"), "1")
        self.assertNotIn("OPENAI_API_KEY", npm_child_env)
        self.assertNotIn("NODE_OPTIONS", npm_child_env)

        cli_env = self.read_env_capture(self.root / "cli-env.log")
        self.assertEqual(cli_env.get("DO_NOT_TRACK"), "1")
        self.assertEqual(cli_env.get("DOTENV_CONFIG_PATH"), os.devnull)
        self.assertNotIn("GRAFT_API_KEY", cli_env)

        telemetry = json.loads(
            (self.home / ".graft" / "telemetry.json").read_text(encoding="utf-8")
        )
        self.assertIs(telemetry["enabled"], False)
        self.assertTrue(result["telemetry"]["changed"])
        self.assertTrue(result["telemetry"]["created"])

        self.assertEqual(self.fetch_records["url"], graft_runtime.GRAFT_TARBALL_URL)
        self.assertEqual(self.fetch_records["parentMode"], 0o700)
        destination = self.fetch_records["dest"]
        assert isinstance(destination, Path)
        self.assertFalse(destination.exists())

    def test_install_omits_allow_scripts_for_npm_before_12(self) -> None:
        self.make_node()
        argv_log, _ = self.make_npm(version="10.9.0")
        payload = b"fixture-tarball"
        with self.fake_fetch(payload), self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 0)
        self.assertTrue(result["after"]["installed"])
        argv = self.npm_install_calls(argv_log)[0]
        self.assertEqual([a for a in argv if a.startswith("--allow-scripts")], [])
        self.assertIn("--ignore-scripts=false", argv)

    # -- install_graft: already-installed idempotency -----------------------

    def test_already_installed_is_readonly_when_telemetry_disabled(self) -> None:
        self.make_package_layout()
        graft_dir = self.home / ".graft"
        graft_dir.mkdir()
        target = graft_dir / "telemetry.json"
        original = b'{"enabled": false, "installId": "abc-123"}\n'
        target.write_bytes(original)
        payload = b"fixture-tarball"
        with self.fake_fetch(payload) as fetch, self.patch_integrity_for(payload):
            result, code = graft_runtime.install_graft(confirmed=True)
            fetch.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "already-installed")
        self.assertFalse(result["telemetry"]["changed"])
        self.assertEqual(target.read_bytes(), original)

    def test_existing_mutable_telemetry_blocks_without_overwriting_keys_or_mode(
        self,
    ) -> None:
        self.make_package_layout()
        graft_dir = self.home / ".graft"
        graft_dir.mkdir()
        target = graft_dir / "telemetry.json"
        original = b'{"installId": "abc-123", "enabled": true, "noticeShown": true}\n'
        target.write_bytes(original)
        os.chmod(target, 0o640)
        result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "telemetry")
        self.assertIn("Graft-owned", str(result["reason"]))
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

    # -- telemetry safety ----------------------------------------------------

    def _usable_cli_install(self) -> None:
        self.make_package_layout()
        graft_dir = self.home / ".graft"
        graft_dir.mkdir(exist_ok=True)

    def test_telemetry_malformed_json_blocks_without_writing(self) -> None:
        self._usable_cli_install()
        target = self.home / ".graft" / "telemetry.json"
        target.write_bytes(b"{not json")
        result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "telemetry")
        self.assertEqual(target.read_bytes(), b"{not json")

    def test_telemetry_duplicate_keys_block(self) -> None:
        self._usable_cli_install()
        target = self.home / ".graft" / "telemetry.json"
        original = b'{"enabled": true, "enabled": false}\n'
        target.write_bytes(original)
        result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("duplicate", str(result["reason"]))
        self.assertEqual(target.read_bytes(), original)

    def test_telemetry_non_object_root_blocks(self) -> None:
        self._usable_cli_install()
        target = self.home / ".graft" / "telemetry.json"
        target.write_bytes(b"[1, 2, 3]\n")
        result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(target.read_bytes(), b"[1, 2, 3]\n")

    def test_telemetry_symlink_escape_blocks_and_leaves_target_alone(self) -> None:
        self._usable_cli_install()
        outside = self.root / "outside.json"
        outside.write_bytes(b'{"enabled": true}\n')
        link = self.home / ".graft" / "telemetry.json"
        link.symlink_to(outside)
        result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("symlink", str(result["reason"]))
        self.assertEqual(outside.read_bytes(), b'{"enabled": true}\n')
        self.assertTrue(link.is_symlink(), "must not replace the escaping symlink")

    def test_telemetry_parent_not_directory_blocks(self) -> None:
        self.make_package_layout()
        (self.home / ".graft").write_bytes(b"i am a file")
        result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "telemetry")

    def test_telemetry_create_failure_reports_real_stage(self) -> None:
        self._usable_cli_install()
        target = self.home / ".graft" / "telemetry.json"
        with mock.patch.object(
            graft_runtime.os, "link", side_effect=OSError("disk full")
        ):
            result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "telemetry-persist")
        self.assertFalse(target.exists())

    def test_telemetry_concurrent_creator_is_rejected_without_overwrite(self) -> None:
        self._usable_cli_install()
        target = self.home / ".graft" / "telemetry.json"
        foreign = b'{"enabled": true, "installId": "someone-else"}\n'
        real_link = graft_runtime.os.link

        def publish_after_foreign_write(source: str, destination: Path) -> None:
            writer = threading.Thread(target=target.write_bytes, args=(foreign,))
            writer.start()
            writer.join()
            real_link(source, destination)

        with mock.patch.object(
            graft_runtime.os, "link", side_effect=publish_after_foreign_write
        ):
            result, code = graft_runtime.install_graft(confirmed=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("concurrently", str(result["reason"]))
        self.assertEqual(target.read_bytes(), foreign)
        leftover = list((self.home / ".graft").glob(".telemetry-*.tmp"))
        self.assertEqual(leftover, [], "failed persist must clean its temp file")


if __name__ == "__main__":
    unittest.main()

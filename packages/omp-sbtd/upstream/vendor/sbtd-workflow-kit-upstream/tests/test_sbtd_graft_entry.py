from __future__ import annotations

import codecs
import hashlib
import json
import os
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))

from onboard_contracts import ContractError
from sbtd_graft_entry import validate_build_scope, validate_project
from sbtd_migration_files import snapshot


def graft_state(root):
    (root / "graft/.graph").mkdir(parents=True)
    (root / "graft/.cache").mkdir()
    (root / "graft/.graph/wiring.json").write_text('{"fixture":true}\n')
    stamp = {
        "version": "0.22.0",
        "hosts": ["agents"],
        "opts": {"global": False, "mcp": False, "hooks": False, "statusline": False},
        "at": "2026-09-19T00:00:00Z",
    }
    (root / "graft/.cache/wiring-stamp.json").write_text(json.dumps(stamp))


def project_fixture(base):
    root = base / "project"
    graft_state(root)
    init_git_repo(root)
    return root


class GuardedLaunchTests(unittest.TestCase):
    def test_missing_or_old_stamp_never_repairs_itself(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            original = snapshot(base)
            self.assertEqual(validate_project(root)["root"], str(root))
            self.assertEqual(snapshot(base), original)
            path = root / "graft/.cache/wiring-stamp.json"
            stamp = json.loads(path.read_text())
            stamp["version"] = "0.17.0"
            path.write_text(json.dumps(stamp))
            before = snapshot(base)
            with self.assertRaises(ContractError):
                validate_project(root)
            self.assertEqual(snapshot(base), before)
            path.unlink()
            before = snapshot(base)
            with self.assertRaises(ContractError):
                validate_project(root)
            self.assertEqual(snapshot(base), before)

    def test_internal_graph_symlink_does_not_claim_business_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = project_fixture(Path(directory).resolve())
            graph = root / "graft"
            business = root / "business-data"
            graph.rename(business)
            graph.symlink_to(business, target_is_directory=True)
            with self.assertRaises(ContractError):
                validate_project(root)
            self.assertTrue(graph.is_symlink())
            self.assertTrue((business / ".graph/wiring.json").is_file())

    def test_real_launcher_child_receives_only_safe_project_and_home_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            home = base / "home"
            home.mkdir(mode=0o700)
            package = base / "node_modules/@nanonets/graft"
            (package / "dist").mkdir(parents=True)
            (package / "package.json").write_text(
                '{"name":"@nanonets/graft","version":"0.22.0"}'
            )
            cli = package / "dist/cli.js"
            cli.write_text(
                'import json,os\nprint(json.dumps({key:os.environ.get(key) for key in ("HOME","DO_NOT_TRACK","DNT","GRAFT_DIR","GRAFT_NO_REFRESH","CLAUDE_PROJECT_DIR","OPENAI_API_KEY","GRAFT_API_KEY","NODE_OPTIONS")}))\n'
            )
            environment = {
                **os.environ,
                "HOME": str(home),
                "USERPROFILE": str(home),
                "OPENAI_API_KEY": "synthetic-secret",
                "GRAFT_API_KEY": "synthetic-secret",
                "NODE_OPTIONS": "synthetic-preload",
                "CLAUDE_PROJECT_DIR": str(base / "unselected"),
            }
            before = snapshot(home)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPTS / "sbtd_graft_entry.py"),
                    "mcp",
                    "--node",
                    str(Path(sys.executable).resolve()),
                    "--entry",
                    str(cli),
                ],
                env=environment,
                cwd=str(root),
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            observed = json.loads(completed.stdout)
            self.assertEqual(observed["GRAFT_NO_REFRESH"], "1")
            self.assertEqual(observed["DO_NOT_TRACK"], "1")
            self.assertEqual(observed["DNT"], "1")
            self.assertEqual(observed["GRAFT_DIR"], str(root / "graft"))
            self.assertEqual(observed["CLAUDE_PROJECT_DIR"], str(root))
            for key in ("OPENAI_API_KEY", "GRAFT_API_KEY", "NODE_OPTIONS"):
                self.assertIsNone(observed[key])
            self.assertNotEqual(observed["HOME"], str(home))
            self.assertFalse(Path(observed["HOME"]).exists())
            self.assertEqual(snapshot(home), before)


def graph_node(path, span="L1-L3"):
    return {
        "id": path,
        "name": path.rsplit("/", 1)[-1],
        "kind": "file",
        "path": path,
        "span": span,
        "signature": None,
        "exported": True,
        "origin": "ast",
        "body_hash": "hash",
        "summary_state": "pending",
        "summary": None,
        "crux": None,
    }


def write_graph(root, payload):
    (root / "graft/.graph/wiring.json").write_text(json.dumps(payload) + "\n")


class BuildScopeGuardTests(unittest.TestCase):
    def assert_refused_readonly(self, base, check):
        def observed():
            entries = {}
            for directory, children, files in os.walk(base, followlinks=False):
                for name in children + files:
                    path = Path(directory) / name
                    mode = path.lstat().st_mode
                    content = (
                        os.readlink(path)
                        if stat.S_ISLNK(mode)
                        else (path.read_bytes() if stat.S_ISREG(mode) else None)
                    )
                    entries[str(path.relative_to(base))] = (mode, content)
            return entries

        before = observed()
        with self.assertRaises(ContractError):
            check()
        self.assertEqual(observed(), before)

    def test_explicit_build_state_without_graph_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            root.mkdir()
            self.assertIsNone(validate_build_scope(root))
            (root / "graft").mkdir()
            self.assertIsNone(validate_build_scope(root))
            (root / "src").mkdir()
            (root / "src/a.ts").write_text("export const a = 1;\n")
            self.assertIsNone(validate_build_scope(root))

    def test_workspace_index_refused_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            index = root / "graft/workspace.json"
            for payload in (
                '{"version":1,"children":["../sibling"]}',
                "not even json",
            ):
                index.write_text(payload)
                self.assert_refused_readonly(base, lambda: validate_build_scope(root))
                self.assert_refused_readonly(base, lambda: validate_project(root))
                index.unlink()

    def test_workspace_parent_invocation_refused_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            # This scenario owns the root's .git presence itself (workspace
            # parent first, ordinary repo after): build the graph state
            # without the genuine-repository fixture.
            root = base / "project"
            graft_state(root)
            for name in ("repoA", "repoB"):
                (root / name / ".git").mkdir(parents=True)
            self.assert_refused_readonly(base, lambda: validate_build_scope(root))
            self.assert_refused_readonly(base, lambda: validate_project(root))
            # An own .git makes the same children an ordinary repo, which the
            # pinned package never treats as a workspace build root.
            (root / ".git").mkdir()
            self.assertIsNone(validate_build_scope(root))

    def test_generated_tree_link_hardlink_special_refused_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            victim = base / "victim.md"
            victim.write_text("original foreign bytes\n")
            (root / "graft/INDEX.md").symlink_to(victim)
            self.assert_refused_readonly(base, lambda: validate_build_scope(root))
            self.assertEqual(victim.read_text(), "original foreign bytes\n")
            (root / "graft/INDEX.md").unlink()
            origin = base / "origin.md"
            origin.write_text("shared inode\n")
            os.link(origin, root / "graft/hardlinked.md")
            self.assert_refused_readonly(base, lambda: validate_build_scope(root))
            (root / "graft/hardlinked.md").unlink()
            if hasattr(os, "mkfifo"):
                os.mkfifo(root / "graft/pipe")
                self.assert_refused_readonly(base, lambda: validate_build_scope(root))
                (root / "graft/pipe").unlink()
            self.assertIsNone(validate_build_scope(root))

    def test_trail_notes_cannot_read_linked_or_special_files(self):
        for kind in ("trail-link", "learnings-link", "note-link", "hardlink", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                if kind == "fifo" and not hasattr(os, "mkfifo"):
                    continue
                base = Path(directory).resolve()
                root = project_fixture(base)
                outside = base / "outside"
                outside.mkdir()
                note = outside / "note.md"
                note.write_text("---\ntitle: private note\n---\nforeign contents\n")
                trail = root / ".trail"
                if kind == "trail-link":
                    trail.symlink_to(outside, target_is_directory=True)
                else:
                    trail.mkdir()
                    learnings = trail / "learnings"
                    if kind == "learnings-link":
                        learnings.symlink_to(outside, target_is_directory=True)
                    else:
                        learnings.mkdir()
                        target = learnings / "note.md"
                        if kind == "note-link":
                            target.symlink_to(note)
                        elif kind == "hardlink":
                            os.link(note, target)
                        else:
                            os.mkfifo(target)
                self.assert_refused_readonly(base, lambda root=root: validate_project(root))
                self.assertEqual(note.read_text(), "---\ntitle: private note\n---\nforeign contents\n")

    def test_regular_project_trail_notes_are_valid_without_a_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            notes = root / ".trail/learnings"
            notes.mkdir(parents=True)
            note = notes / "note.md"
            note.write_text("---\ntitle: local note\n---\nproject contents\n")
            before = snapshot(root)
            validate_build_scope(root)
            self.assertEqual(snapshot(root), before)

    def test_ancestor_note_checkout_is_outside_selected_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            parent = project_fixture(base)
            selected = parent / "selected"
            graft_state(selected)
            self.assert_refused_readonly(base, lambda: validate_project(selected))

    def test_single_child_note_checkout_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "workspace"
            root.mkdir()
            child = root / "node_modules"
            (child / ".git").mkdir(parents=True)
            notes = child / ".trail/learnings"
            notes.mkdir(parents=True)
            target = notes / "note.md"
            target.write_text("local note\n")
            validate_build_scope(root)
            target.unlink()
            victim = base / "private.md"
            victim.write_text("private contents\n")
            target.symlink_to(victim)
            self.assert_refused_readonly(base, lambda: validate_build_scope(root))

    def test_session_start_skill_inputs_are_bounded(self):
        for kind in ("parent-link", "skill-link", "hardlink", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                if kind == "fifo" and not hasattr(os, "mkfifo"):
                    continue
                base = Path(directory).resolve()
                root = project_fixture(base)
                (root / ".trail").mkdir()
                outside = base / "external"
                (outside / "skills" / "foreign").mkdir(parents=True)
                victim = outside / "skills/foreign/SKILL.md"
                victim.write_text("foreign skill\n")
                if kind == "parent-link":
                    (root / ".claude").symlink_to(outside, target_is_directory=True)
                else:
                    skill = root / ".claude/skills/local/SKILL.md"
                    skill.parent.mkdir(parents=True)
                    if kind == "skill-link":
                        skill.symlink_to(victim)
                    elif kind == "hardlink":
                        os.link(victim, skill)
                    else:
                        os.mkfifo(skill)
                self.assert_refused_readonly(base, lambda root=root: validate_project(root))

    def test_poisoned_graph_paths_and_spans_refused_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            poisons = [
                {"nodes": [graph_node("../evil.ts")]},
                {"nodes": [graph_node("/etc/passwd")]},
                {"nodes": [graph_node("src/a.ts", span="../..:L1-L2")]},
                {"nodes": [graph_node("src/a.ts", span="L1-")]},
                {
                    "nodes": [],
                    "edges": [
                        {
                            "source": "s",
                            "target": "../../etc/passwd:L1-L2",
                            "relation": "imports",
                            "confidence": "extracted",
                        }
                    ],
                },
                {
                    "nodes": [],
                    "edges": [
                        {
                            "source": "/etc/passwd:L1-L2",
                            "target": "t",
                            "relation": "contains",
                            "confidence": "extracted",
                        }
                    ],
                },
            ]
            for payload in poisons:
                with self.subTest(payload=payload):
                    write_graph(root, payload)
                    self.assert_refused_readonly(
                        base, lambda: validate_build_scope(root)
                    )
            self.assertEqual(
                json.loads((root / "graft/.graph/wiring.json").read_text()),
                poisons[-1],
            )

    def test_source_links_and_hardlinks_refused_but_missing_permitted(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            (root / "src").mkdir()
            (root / "src/a.ts").write_text("export const a = 1;\n")
            (root / "src/link.ts").symlink_to(root / "src/a.ts")
            os.link(root / "src/a.ts", root / "src/hard.ts")
            for path in ("src/link.ts", "src/hard.ts"):
                with self.subTest(path=path):
                    write_graph(root, {"nodes": [graph_node(path)]})
                    self.assert_refused_readonly(
                        base, lambda: validate_build_scope(root)
                    )
            # Restoring single-link src/a.ts for the valid graph below (the
            # hardlink refusal check raised both inodes' link counts).
            (root / "src/hard.ts").unlink()
            write_graph(
                root,
                {
                    "nodes": [
                        graph_node("src/a.ts"),
                        graph_node("src/gone.ts"),
                    ],
                    "edges": [
                        {
                            "source": "src/a.ts",
                            "target": "lodash",
                            "relation": "imports",
                            "confidence": "extracted",
                        },
                        {
                            "source": "s",
                            "target": "src/a.ts:L1-L3",
                            "relation": "contains",
                            "confidence": "extracted",
                        },
                    ],
                },
            )
            self.assertIsNone(validate_build_scope(root))
            self.assertIsNotNone(validate_project(root)["stamp"])

    def test_poisoned_extract_cache_refused_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            (root / "src").mkdir()
            (root / "src/a.ts").write_text("export const a = 1;\n")
            cache = root / "graft/.cache/extract.0123456789abcdef.json"
            entry = {"size": 18, "mtimeMs": 1, "hash": "hash"}
            poisons = [
                {
                    "files": {
                        "src/a.ts": {
                            **entry,
                            "nodes": [graph_node("../evil.ts")],
                            "rawEdges": [],
                        }
                    }
                },
                {
                    "files": {
                        "src/a.ts": {
                            **entry,
                            "nodes": [graph_node("src/evil.ts")],
                            "rawEdges": [],
                        }
                    }
                },
                {
                    "files": {
                        "src/a.ts": {
                            **entry,
                            "nodes": [graph_node("src/a.ts", span="../x:L1-L2")],
                            "rawEdges": [],
                        }
                    }
                },
                {
                    "files": {
                        "src/a.ts": {
                            **entry,
                            "nodes": [],
                            "rawEdges": [
                                {
                                    "source": "../../etc/passwd:L1-L2",
                                    "relation": "contains",
                                    "file": "src/a.ts",
                                }
                            ],
                        }
                    }
                },
                {
                    "files": {
                        "src/a.ts": {
                            **entry,
                            "nodes": [],
                            "rawEdges": [
                                {
                                    "source": "s",
                                    "relation": "imports",
                                    "file": "src/a.ts",
                                    "specifier": "../../etc/passwd:L1-L2",
                                }
                            ],
                        }
                    }
                },
            ]
            for payload in poisons:
                with self.subTest(payload=payload):
                    cache.write_text(json.dumps(payload))
                    self.assert_refused_readonly(
                        base, lambda: validate_build_scope(root)
                    )
            cache.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "extractor": "0123456789abcdef",
                        "files": {
                            "src/a.ts": {
                                **entry,
                                "nodes": [graph_node("src/a.ts")],
                                "rawEdges": [
                                    {
                                        "source": "src/a.ts",
                                        "relation": "imports",
                                        "file": "src/a.ts",
                                        "specifier": "lodash",
                                    }
                                ],
                            },
                            "src/broken.ts": {
                                **entry,
                                "nodes": [],
                                "rawEdges": [],
                                "error": "parse failed",
                            },
                        },
                    }
                )
            )
            self.assertIsNone(validate_build_scope(root))

    def test_poisoned_concept_pointers_refused_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            (root / "src").mkdir()
            (root / "src/a.ts").write_text("export const a = 1;\n")
            concept = root / "graft/Concept.md"
            poisons = [
                "---\nslug: Concept\nsources:\n  - path: ../../etc/passwd:L1-L2\n---\nbody\n",
                "---\nslug: ../../etc/passwd:L1-L2\n---\nbody\n",
                '---json\n{"slug": "../../etc/passwd:L1-L2"}\n---\nbody\n',
                "---javascript\n({slug: 'Concept'})\n---\nbody\n",
            ]
            for payload in poisons:
                with self.subTest(payload=payload):
                    concept.write_text(payload)
                    self.assert_refused_readonly(
                        base, lambda: validate_build_scope(root)
                    )
            concept.write_text(
                "---\nslug: Concept\nsources:\n  - path: src/a.ts\n    span: L1-L3\n---\nbody\n"
            )
            (root / "graft/INDEX.md").write_text(
                "---\nslug: ../../etc/passwd:L1-L2\n---\n# roster\n"
            )
            self.assertIsNone(validate_build_scope(root))

    def test_effective_concept_pointer_coercion_join_and_fallback_are_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            victim = base / "private.txt"
            victim.write_bytes(b"private original\n")
            (root / "outside").symlink_to(victim)
            (root / "a, b").symlink_to(victim)
            cases = [
                ("concept.md", {"slug": ["../private.txt:L1-L2"]}),
                (
                    "concept.md",
                    {"slug": "safe", "sources": [{"path": ["../private.txt:L1-L2"]}]},
                ),
                (
                    "concept.md",
                    {"slug": "safe", "sources": [{"path": "outside:L1-L2"}]},
                ),
                ("outside:L1-L2.md", {"name": "fallback"}),
                ("concept.md", {"sources": [{"path": "a"}, {"path": "b:L1-L2"}]}),
            ]
            for filename, frontmatter in cases:
                with self.subTest(filename=filename, frontmatter=frontmatter):
                    concept = root / "graft" / filename
                    concept.write_text(
                        "---json\n" + json.dumps(frontmatter) + "\n---\nNeedle\n"
                    )
                    self.assert_refused_readonly(
                        base, lambda: validate_build_scope(root)
                    )
                    self.assertEqual(victim.read_bytes(), b"private original\n")
                    concept.unlink()

    def test_poisoned_manifest_probe_refused_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            (root / "src").mkdir()
            (root / "src/a.ts").write_text("export const a = 1;\n")
            manifest = root / "graft/manifest.json"
            manifest.write_text(json.dumps({"files": [{"path": "../../etc/passwd"}]}))
            self.assert_refused_readonly(base, lambda: validate_build_scope(root))
            manifest.write_text(json.dumps({"files": [{"path": "src/a.ts"}]}))
            self.assertIsNone(validate_build_scope(root))


def fake_runtime_fixture(base):
    """A fake pinned runtime: the real python as node, a graft package shell."""
    package = base / "node_modules/@nanonets/graft"
    (package / "dist/claude").mkdir(parents=True)
    (package / "dist/cli.js").write_text("// pinned cli placeholder\n")
    (package / "package.json").write_text(
        '{"name":"@nanonets/graft","version":"0.22.0"}'
    )
    (package / "dist/claude/hooks.js").write_text("// pinned hook module\n")
    return package


def launch_env(base):
    """Subprocess env with controlled HOME and TMPDIR (tmp must stay clean)."""
    home = base / "home"
    home.mkdir(mode=0o700)
    tmp = base / "tmp"
    tmp.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "TMPDIR": str(tmp),
    }
    return env, tmp


# A controlled "native" MCP server speaking the pinned framing: one JSON
# object per line on stdin, one reply per request on stdout, EOF exits 0.
# Every consumed message is appended to a marker log inside the root so the
# test can prove exactly which lines native ever saw.
FAKE_MCP_SERVER = (
    "import json, sys\n"
    "marker = sys.argv[2] + '/consumed.log'\n"
    "for line in sys.stdin:\n"
    "    text = line.strip()\n"
    "    if not text:\n"
    "        continue\n"
    "    msg = json.loads(text)\n"
    "    with open(marker, 'a') as handle:\n"
    "        handle.write(json.dumps({'id': msg.get('id'), 'method': msg.get('method')}) + '\\n')\n"
    "    if 'id' not in msg:\n"
    "        continue\n"
    "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'seen': msg.get('method')}}) + '\\n')\n"
    "    sys.stdout.flush()\n"
)


def launch_mcp(cwd, cli, env):
    """Launch the managed MCP entry with the project selected by process cwd."""
    return subprocess.Popen(
        [
            str(Path(sys.executable).resolve()),
            "-B",
            str(SCRIPTS / "sbtd_graft_entry.py"),
            "mcp",
            "--node",
            str(Path(sys.executable).resolve()),
            "--entry",
            str(cli),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(cwd),
    )


def send_line(proc, message):
    proc.stdin.write(
        message if isinstance(message, bytes) else json.dumps(message).encode()
    )
    proc.stdin.write(b"\n")
    proc.stdin.flush()


def read_reply(proc, timeout=10.0):
    # Windows select() accepts sockets, not subprocess pipes. A bounded
    # background read exercises the same protocol seam on every platform.
    with ThreadPoolExecutor(max_workers=1) as reader:
        pending = reader.submit(proc.stdout.readline)
        try:
            line = pending.result(timeout=timeout)
        except FutureTimeout:
            proc.kill()
            raise AssertionError("timed out waiting for a protocol line") from None
    if not line:
        if proc.poll() is None:
            proc.kill()
        code = proc.wait(timeout=5)
        # A failed launcher may leave a descendant holding stderr open.
        # Read a separate unbuffered descriptor so timeout/close never waits
        # on the test process's BufferedReader lock.
        stderr_fd = os.dup(proc.stderr.fileno())
        captured = []

        def collect_error():
            with os.fdopen(stderr_fd, "rb", buffering=0) as stream:
                captured.append(stream.read().decode("utf-8", errors="replace"))

        error_reader = threading.Thread(target=collect_error, daemon=True)
        error_reader.start()
        error_reader.join(timeout=2)
        stderr = captured[0] if captured else "<stderr did not close within 2s>"
        raise AssertionError(
            f"the launcher closed its protocol stdout (exit {code}): {stderr}"
        )
    return json.loads(line)


def consumed_requests(root):
    marker = root / "consumed.log"
    if not marker.exists():
        return []
    return [json.loads(line) for line in marker.read_text().splitlines()]

FAKE_ANALYZE_CLI = (
    "import json, os, sys\n"
    "print(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), "
    "'refresh': os.environ.get('GRAFT_NO_REFRESH')}))\n"
)


def run_analyze(arguments, root, cli, env):
    return subprocess.run(
        [
            str(Path(sys.executable).resolve()),
            "-B",
            str(SCRIPTS / "sbtd_graft_entry.py"),
            "analyze",
            "--root",
            str(root),
            "--node",
            str(Path(sys.executable).resolve()),
            "--entry",
            str(cli),
            *arguments,
        ],
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


class GuardedAnalysisTests(unittest.TestCase):
    def test_closed_analysis_commands_map_to_json_no_refresh_native_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_ANALYZE_CLI)
            env, tmp = launch_env(base)
            cases = {
                ("ask", "where is validation"): [
                    "ask", "where is validation", ".", "--json", "--no-refresh"
                ],
                ("map",): ["map", ".", "--json", "--no-refresh"],
                ("skeleton", "src/app.py"): [
                    "skeleton", "src/app.py", ".", "--json", "--no-refresh"
                ],
                ("callers", "validate_project"): [
                    "callers", "validate_project", ".", "--json", "--no-refresh"
                ],
                ("check",): ["check", ".", "--json"],
                ("grep", "needle text"): [
                    "grep", "needle text", ".", "--fixed", "--json", "--no-refresh"
                ],
                ("blast",): [
                    "blast", ".", "--format", "json", "--no-refresh"
                ],
            }
            for arguments, expected in cases.items():
                with self.subTest(command=arguments[0]):
                    completed = run_analyze(arguments, root, cli, env)
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    observed = json.loads(completed.stdout)
                    self.assertEqual(observed["argv"], expected)
                    self.assertEqual(observed["cwd"], str(root))
                    self.assertEqual(observed["refresh"], "1")
            self.assertEqual(list(tmp.iterdir()), [])

    def test_forbidden_analysis_options_and_paths_never_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_ANALYZE_CLI)
            env, _tmp = launch_env(base)
            for arguments in (
                ("blast", "--name"),
                ("blast", "--export-viz", str(base / "viz")),
                ("ask", "query", "--deep"),
                ("map", "--dir", str(base)),
                ("skeleton", "../outside.py"),
                ("skeleton", str(base / "outside.py")),
            ):
                with self.subTest(arguments=arguments):
                    completed = run_analyze(arguments, root, cli, env)
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")

    def test_option_shaped_analysis_values_never_become_native_options(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_ANALYZE_CLI)
            env, _tmp = launch_env(base)
            for arguments in (
                ("ask", "--", "--dir=/tmp/other-graph"),
                ("callers", "--json"),
                ("grep", "--fixed"),
            ):
                with self.subTest(arguments=arguments):
                    completed = run_analyze(arguments, root, cli, env)
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")



def close_pipes(proc):
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        try:
            stream.close()
        except (BrokenPipeError, OSError):
            pass


class ScopedMcpForwardingTests(unittest.TestCase):
    def test_accepted_then_poisoned_graph_blocked_before_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            env, tmp = launch_env(base)
            proc = launch_mcp(root, cli, env)
            try:
                send_line(
                    proc,
                    {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
                )
                reply = read_reply(proc)
                self.assertEqual(reply["id"], 0)
                self.assertEqual(reply["result"], {"seen": "initialize"})
                # A notification is forwarded and answered with silence.
                send_line(
                    proc, {"jsonrpc": "2.0", "method": "notifications/initialized"}
                )
                send_line(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "graft_find_code", "arguments": {}},
                    },
                )
                reply = read_reply(proc)
                self.assertEqual(reply["id"], 1)
                self.assertEqual(reply["result"], {"seen": "tools/call"})
                # A graph replaced behind the running child (explicit build or
                # the Stop hook's sync build) was never validated at startup:
                # the next request must meet the fresh guard, not the graph.
                write_graph(root, {"nodes": [graph_node("../evil.ts")]})
                send_line(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "graft_find_code",
                            "arguments": {"query": "needle-b42c1-secret"},
                        },
                    },
                )
                reply = read_reply(proc)
                self.assertEqual(reply["id"], 2)
                self.assertNotIn("result", reply)
                self.assertEqual(reply["error"]["code"], -32603)
                self.assertIsInstance(reply["error"]["message"], str)
                # The refusal is fixed and sanitized: no request bytes, no
                # graph content, no path detail.
                self.assertNotIn("needle-b42c1-secret", json.dumps(reply))
                self.assertNotIn("evil", json.dumps(reply))
                self.assertEqual(proc.wait(timeout=10), 2)
                stderr = proc.stderr.read().decode()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            close_pipes(proc)
            self.assertTrue(stderr.startswith("sbtd-graft-entry:"), stderr)
            self.assertNotIn("evil", stderr)
            # The poisoned request was never consumed by native; the earlier
            # accepted requests and the notification were.
            consumed = consumed_requests(root)
            self.assertEqual([entry["id"] for entry in consumed], [0, None, 1])
            self.assertEqual(
                [entry["method"] for entry in consumed],
                ["initialize", "notifications/initialized", "tools/call"],
            )
            # The scoped temporary HOME was removed even on the failure path.
            self.assertEqual(list(tmp.iterdir()), [])

    def test_ambiguous_line_never_reaches_native_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            env, _tmp = launch_env(base)
            proc = launch_mcp(root, cli, env)
            try:
                # Duplicate keys: a last-wins parser would dispatch the second
                # method; the guard must refuse instead of forwarding.
                send_line(
                    proc,
                    b'{"jsonrpc":"2.0","id":9,"method":"ping","method":"tools/call"}',
                )
                reply = read_reply(proc)
                self.assertIsNone(reply["id"])
                self.assertEqual(reply["error"]["code"], -32700)
                self.assertNotIn("result", reply)
                self.assertEqual(proc.wait(timeout=10), 2)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            close_pipes(proc)
            self.assertEqual(consumed_requests(root), [])

    def test_native_exit_does_not_wait_for_host_stdin_or_abort_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(
                "import time\nprint('native-final-line', flush=True)\ntime.sleep(0.1)\nraise SystemExit(7)\n"
            )
            env, tmp = launch_env(base)
            proc = launch_mcp(root, cli, env)
            try:
                # Host intentionally leaves stdin open while native exits.
                code = proc.wait(timeout=10)
                errors = proc.stderr.read()
                self.assertEqual(code, 7, errors.decode())
                self.assertEqual(proc.stdout.read(), b"native-final-line\n")
                self.assertNotIn(b"Fatal Python error", errors)
                self.assertEqual(list(tmp.iterdir()), [])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                close_pipes(proc)

    def test_native_epipe_preserves_child_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(
                "import os, time\n"
                "os.close(0)\n"
                "print('stdin-closed', flush=True)\n"
                "time.sleep(0.2)\n"
                "raise SystemExit(7)\n"
            )
            env, _tmp = launch_env(base)
            proc = launch_mcp(root, cli, env)
            try:
                self.assertEqual(proc.stdout.readline(), b"stdin-closed\n")
                send_line(
                    proc,
                    {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                self.assertEqual(proc.wait(timeout=10), 7, proc.stderr.read().decode())
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                close_pipes(proc)

    def test_slow_host_drains_complete_native_reply_without_shutdown_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(
                "import json\nprint(json.dumps({'jsonrpc':'2.0','id':1,'result':'x'*1048576}),flush=True)\n"
            )
            env, _tmp = launch_env(base)
            proc = launch_mcp(root, cli, env)
            try:
                ready, _, _ = select.select([proc.stdout], [], [], 10)
                self.assertTrue(ready, "native never produced output")
                time.sleep(6)
                self.assertIsNone(
                    proc.poll(), "host backpressure must not discard native output"
                )
                reply = json.loads(proc.stdout.readline())
                self.assertEqual(reply["result"], "x" * 1048576)
                self.assertEqual(proc.wait(timeout=10), 0)
                self.assertNotIn(b"Fatal Python error", proc.stderr.read())
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                close_pipes(proc)

    def test_host_eof_lets_native_exit_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            env, tmp = launch_env(base)
            proc = launch_mcp(root, cli, env)
            try:
                send_line(
                    proc,
                    {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
                )
                reply = read_reply(proc)
                self.assertEqual(reply["result"], {"seen": "initialize"})
                proc.stdin.close()
                self.assertEqual(proc.wait(timeout=10), 0)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            close_pipes(proc)
            self.assertEqual(
                [entry["method"] for entry in consumed_requests(root)],
                ["initialize"],
            )
            self.assertEqual(list(tmp.iterdir()), [])


def git_env():
    """Env for fixture Git setup: no inherited GIT_*, no user/system config."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env=git_env(),
        text=True,
    )


def init_git_repo(path):
    """A genuine Git repository at path (unborn branch, no managed init)."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
        env=git_env(),
        text=True,
    )


class SessionRootResolutionTests(unittest.TestCase):
    def run_mcp(self, cwd, cli, env, extra=()):
        return subprocess.run(
            [
                str(Path(sys.executable).resolve()),
                "-B",
                str(SCRIPTS / "sbtd_graft_entry.py"),
                "mcp",
                "--node",
                str(Path(sys.executable).resolve()),
                "--entry",
                str(cli),
                *extra,
            ],
            input=b"",
            env=env,
            cwd=str(cwd),
            capture_output=True,
            timeout=20,
            check=False,
        )

    def serve_initialize(self, proc, root):
        try:
            send_line(
                proc,
                {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
            )
            reply = read_reply(proc)
            self.assertEqual(reply["result"], {"seen": "initialize"})
            proc.stdin.close()
            self.assertEqual(proc.wait(timeout=10), 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            close_pipes(proc)
        self.assertEqual(
            [entry["method"] for entry in consumed_requests(root)],
            ["initialize"],
        )

    def test_subdirectory_resolves_to_the_enclosing_repository_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            subdir = root / "src/deep"
            subdir.mkdir(parents=True)
            self.serve_initialize(launch_mcp(subdir, cli, env), root)
            self.assertEqual(list(tmp.iterdir()), [])

    def test_linked_worktree_resolves_to_the_worktree_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            main = base / "main"
            init_git_repo(main)
            git(main, "config", "user.email", "fixture@test")
            git(main, "config", "user.name", "fixture")
            (main / "app.py").write_text("VALUE = 'main'\n")
            git(main, "add", "app.py")
            git(main, "commit", "-m", "initial")
            linked = base / "linked"
            git(main, "worktree", "add", "-b", "feature", str(linked))
            graft_state(linked)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            subdir = linked / "src"
            subdir.mkdir()
            self.serve_initialize(launch_mcp(subdir, cli, env), linked)
            self.assertFalse((main / "consumed.log").exists())
            # The main checkout holds no managed graph: launching from it
            # fails closed rather than borrowing the worktree's state.
            completed = self.run_mcp(main, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse((main / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_nested_repository_never_borrows_the_outer_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            outer = base / "outer"
            graft_state(outer)
            init_git_repo(outer)
            nested = outer / "inner"
            init_git_repo(nested)
            deep = nested / "pkg"
            deep.mkdir()
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            before = snapshot(outer / "graft")
            completed = self.run_mcp(deep, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertTrue(
                completed.stderr.startswith(b"sbtd-graft-entry:"), completed.stderr
            )
            self.assertFalse((outer / "consumed.log").exists())
            self.assertFalse((nested / "consumed.log").exists())
            self.assertEqual(snapshot(outer / "graft"), before)
            self.assertEqual(list(tmp.iterdir()), [])

    def test_neutral_common_parent_finds_no_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            parent = base / "workspace"
            for name in ("alpha", "beta"):
                graft_state(parent / name)
                init_git_repo(parent / name)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            completed = self.run_mcp(parent, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse((parent / "alpha" / "consumed.log").exists())
            self.assertFalse((parent / "beta" / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_no_git_context_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            plain = base / "plain"
            plain.mkdir()
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            completed = self.run_mcp(plain, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertTrue(
                completed.stderr.startswith(b"sbtd-graft-entry:"), completed.stderr
            )
            self.assertEqual(list(tmp.iterdir()), [])

    def test_home_directory_is_never_a_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            home = base / "home"
            graft_state(home)
            init_git_repo(home)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            completed = self.run_mcp(home, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse((home / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_git_environment_overrides_cannot_steal_the_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            decoy = base / "decoy"
            graft_state(decoy)
            init_git_repo(decoy)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            subdir = root / "src"
            subdir.mkdir()
            env = {
                **env,
                "GIT_DIR": str(decoy / ".git"),
                "GIT_WORK_TREE": str(decoy),
                "GIT_CEILING_DIRECTORIES": str(root),
            }
            self.serve_initialize(launch_mcp(subdir, cli, env), root)
            self.assertFalse((decoy / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_unsafe_git_markers_fail_closed_instead_of_skipping_outward(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            outer = base / "outer"
            graft_state(outer)
            init_git_repo(outer)
            nested = outer / "inner"
            nested.mkdir()
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            marker = nested / ".git"
            marker.symlink_to(outer / ".git", target_is_directory=True)
            completed = self.run_mcp(nested, cli, env)
            self.assertEqual(completed.returncode, 2)
            marker.unlink()
            marker.write_text("not a gitdir pointer\n")
            completed = self.run_mcp(nested, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse((outer / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_marker_shape_alone_never_selects_a_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            outer = base / "outer"
            graft_state(outer)
            init_git_repo(outer)
            nested = outer / "inner"
            nested.mkdir()
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            marker = nested / ".git"
            # An empty hand-made .git directory is not a checkout.
            marker.mkdir()
            completed = self.run_mcp(nested, cli, env)
            self.assertEqual(completed.returncode, 2)
            marker.rmdir()
            # A pointer to a nonexistent gitdir is not a checkout.
            marker.write_text(f"gitdir: {base / 'absent-gitdir'}\n")
            completed = self.run_mcp(nested, cli, env)
            self.assertEqual(completed.returncode, 2)
            # A pointer to a real but unrelated gitdir resolves to that
            # checkout's top-level, never to the boundary directory — the
            # outer graph must not be borrowed even though it is valid.
            marker.write_text(f"gitdir: {outer / '.git'}\n")
            completed = self.run_mcp(nested, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse((outer / "consumed.log").exists())
            self.assertFalse((nested / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_bare_repository_is_not_a_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            repo = base / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "--bare", str(repo / ".git")],
                check=True,
                capture_output=True,
                env=git_env(),
                text=True,
            )
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            completed = self.run_mcp(repo, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse((repo / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_nested_bare_repository_tree_cannot_launch_the_outer_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            outer = base / "outer"
            graft_state(outer)
            init_git_repo(outer)
            bare = outer / "cache.git"
            subprocess.run(
                ["git", "init", "--bare", str(bare)],
                check=True,
                capture_output=True,
                env=git_env(),
                text=True,
            )
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            # A bare data tree carries no .git marker of its own; launching
            # from it or its subdirectories must refuse, never adopt the
            # marked outer ancestor's valid graph.
            for cwd in (bare, bare / "objects"):
                with self.subTest(cwd=cwd.name):
                    completed = self.run_mcp(cwd, cli, env)
                    self.assertEqual(completed.returncode, 2)
            self.assertFalse((outer / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_git_administrative_tree_cannot_launch_the_worktree_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            admin = root / ".git" / "refs"
            self.assertTrue(admin.is_dir())
            completed = self.run_mcp(admin, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse((root / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])


    def test_path_entries_inside_the_project_never_supply_git(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            invoked = root / "sentinel-invoked"
            sentinel = bin_dir / "git"
            sentinel.write_text(
                f"#!{Path(sys.executable).resolve()}\n"
                "import pathlib\n"
                f"pathlib.Path({str(invoked)!r}).write_text('invoked')\n"
                "raise SystemExit(1)\n"
            )
            sentinel.chmod(0o755)
            real_path = os.environ.get("PATH", "")
            # A project bin/, a relative entry and an empty entry all precede
            # the real PATH: the sentinel can never be trusted, so the
            # genuine external Git still proves the root and the launch works.
            for prefix in (str(bin_dir), ".", "", "relative"):
                with self.subTest(prefix=prefix):
                    poisoned = {**env, "PATH": prefix + os.pathsep + real_path}
                    proc = launch_mcp(root, cli, poisoned)
                    try:
                        send_line(
                            proc,
                            {
                                "jsonrpc": "2.0",
                                "id": 0,
                                "method": "initialize",
                                "params": {},
                            },
                        )
                        reply = read_reply(proc)
                        self.assertEqual(reply["result"], {"seen": "initialize"})
                        proc.stdin.close()
                        self.assertEqual(proc.wait(timeout=10), 0)
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.wait()
                        close_pipes(proc)
                    self.assertFalse(invoked.exists())
            # With no absolute entry outside the candidate at all there is
            # no trusted Git: the launch fails closed, again without the
            # sentinel ever running.
            refused = {**env, "PATH": str(bin_dir) + os.pathsep + "relative"}
            consumed_before = consumed_requests(root)
            completed = self.run_mcp(root, cli, refused)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(invoked.exists())
            self.assertEqual(consumed_requests(root), consumed_before)
            self.assertEqual(list(tmp.iterdir()), [])


    def test_unicode_repository_initializes_with_utf8_mode_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            env["PYTHONUTF8"] = "0"
            probe = subprocess.run(
                [
                    str(Path(sys.executable).resolve()), "-B", "-c",
                    (
                        "import json, locale, sys; "
                        "print(json.dumps({'utf8_mode': sys.flags.utf8_mode, "
                        "'encoding': locale.getencoding()}))"
                    ),
                ],
                env=env,
                capture_output=True,
                text=True,
                encoding="ascii",
                timeout=10,
                check=True,
            )
            settings = json.loads(probe.stdout)
            self.assertEqual(settings["utf8_mode"], 0)
            if os.name == "nt":
                self.assertNotEqual(
                    codecs.lookup(settings["encoding"]).name,
                    "utf-8",
                    "Windows regression requires a non-UTF-8 default decoder",
                )
                print(f"Windows Git path decoding precondition: {settings}")
            root = project_fixture(base / "caf\u00e9-\u4e2d\u6587")
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            self.serve_initialize(launch_mcp(root, cli, env), root)
            self.assertEqual(list(tmp.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX executable fixture emits invalid bytes")
    def test_undecodable_git_toplevel_is_a_controlled_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            trusted = base / "trusted-git"
            trusted.mkdir()
            executable = trusted / "git"
            executable.write_text("#!/bin/sh\nprintf '\\377\\nfalse\\n'\n")
            executable.chmod(0o700)
            env.update(PATH=str(trusted), PYTHONUTF8="1")
            before = snapshot(root)
            completed = self.run_mcp(root, cli, env)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertNotIn(b"Traceback", completed.stderr)
            self.assertFalse((root / "consumed.log").exists())
            self.assertEqual(snapshot(root), before)
            self.assertEqual(list(tmp.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "native Windows Git executable lookup")
    def test_windows_cwd_git_does_not_shadow_the_external_executable(self):
        """R3: Windows which must not insert the current project directory."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            real_git = Path(shutil.which("git.exe")).resolve(strict=True)
            local_git = root / "git.exe"
            local_git.write_bytes(b"project-owned file, never executable\n")
            env = {
                key: value for key, value in env.items()
                if key.upper() != "NODEFAULTCURRENTDIRECTORYINEXEPATH"
            }
            env["PATH"] = str(real_git.parent) + os.pathsep + env["PATH"]
            self.serve_initialize(launch_mcp(root, cli, env), root)
            self.assertEqual(local_git.read_bytes(), b"project-owned file, never executable\n")
            self.assertEqual(list(tmp.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "native Windows batch-file execution")
    def test_windows_batch_git_is_never_executed(self):
        """R1: batch shims are skipped, even with CMD metacharacters in cwd."""
        real_git = Path(shutil.which("git.exe")).resolve(strict=True)
        for extension in (".cmd", ".bat"):
            for native_available in (True, False):
                with (
                    self.subTest(extension=extension, native_available=native_available),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    base = Path(directory).resolve()
                    env, tmp = launch_env(base)
                    root = project_fixture(base / "project&boundary")
                    package = fake_runtime_fixture(base)
                    cli = package / "dist/cli.js"
                    cli.write_text(FAKE_MCP_SERVER)
                    shims = base / "external-shims"
                    shims.mkdir()
                    marker = base / "batch-executed"
                    (shims / ("git" + extension)).write_text(
                        f'@echo off\necho executed>"{marker}"\nexit /b 7\n',
                        encoding="utf-8",
                    )
                    env["PATHEXT"] = ".CMD;.BAT;.EXE"
                    env["PATH"] = str(shims)
                    if native_available:
                        env["PATH"] += os.pathsep + str(real_git.parent)
                        self.serve_initialize(launch_mcp(root, cli, env), root)
                    else:
                        completed = self.run_mcp(root, cli, env)
                        self.assertEqual(completed.returncode, 2, completed.stderr)
                        self.assertFalse((root / "consumed.log").exists())
                    self.assertFalse(marker.exists(), "Git proof executed a batch shim")
                    self.assertEqual(list(tmp.iterdir()), [])

    def test_graph_hardlink_is_refused_without_changing_the_outside_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            outside = base / "outside.md"
            outside.write_bytes(b"user-owned content\n")
            os.link(outside, root / "graft/linked.md")
            completed = self.run_mcp(root, cli, env)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertIn(b"hardlinked", completed.stderr)
            self.assertEqual(outside.read_bytes(), b"user-owned content\n")
            self.assertFalse((root / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_fixed_root_option_is_rejected_before_native_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            completed = self.run_mcp(root, cli, env, extra=("--root", str(root)))
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, b"")
            self.assertFalse((root / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_missing_graph_or_old_stamp_refuses_the_cwd_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env, tmp = launch_env(base)
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            cli = package / "dist/cli.js"
            cli.write_text(FAKE_MCP_SERVER)
            graph = root / "graft/.graph/wiring.json"
            saved_graph = graph.read_bytes()
            graph.unlink()
            completed = self.run_mcp(root, cli, env)
            self.assertEqual(completed.returncode, 2)
            graph.write_bytes(saved_graph)
            stamp_path = root / "graft/.cache/wiring-stamp.json"
            stamp = json.loads(stamp_path.read_text())
            stamp["version"] = "0.17.0"
            stamp_path.write_text(json.dumps(stamp))
            completed = self.run_mcp(root, cli, env)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(stamp_path.read_text())["version"], "0.17.0")
            self.assertFalse((root / "consumed.log").exists())
            self.assertEqual(list(tmp.iterdir()), [])


def fake_node_fixture(base):
    """An executable fake node that records its argv and stdin digest."""
    marker = base / "hook-marker.json"
    node = base / "fake-node"
    node.write_text(
        f"#!{Path(sys.executable).resolve()}\n"
        "import hashlib, json, sys\n"
        "payload = sys.stdin.buffer.read()\n"
        f"with open({str(marker)!r}, 'w') as handle:\n"
        "    json.dump({'argv': sys.argv[1:], 'sha256': hashlib.sha256(payload).hexdigest()}, handle)\n"
    )
    node.chmod(0o755)
    return node, marker


class HookScopingTests(unittest.TestCase):
    def run_hook(self, root_arg, payload, env, node, entry):
        return subprocess.run(
            [
                str(Path(sys.executable).resolve()),
                "-B",
                str(SCRIPTS / "sbtd_graft_entry.py"),
                "hook",
                "--root",
                str(root_arg),
                "--node",
                str(node),
                "--entry",
                str(entry),
                "--event",
                "stop",
            ],
            input=payload,
            env=env,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def test_unrelated_cwd_noops_even_when_bound_root_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            elsewhere = base / "elsewhere"
            elsewhere.mkdir()
            absent = base / "absent-runtime"
            shutil.rmtree(root)
            env, tmp = launch_env(base)
            completed = self.run_hook(
                root,
                json.dumps({"cwd": str(elsewhere)}).encode(),
                env,
                absent,
                absent,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, b"")
            self.assertFalse((base / "hook-marker.json").exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_unrelated_cwd_noops_before_any_runtime_or_project_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            elsewhere = base / "elsewhere"
            elsewhere.mkdir()
            absent = base / "absent-runtime"
            env, tmp = launch_env(base)
            completed = self.run_hook(
                root,
                json.dumps({"cwd": str(elsewhere)}).encode(),
                env,
                absent,
                absent,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, b"")
            self.assertEqual(list(tmp.iterdir()), [])

    def test_related_event_on_deleted_root_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            node, marker = fake_node_fixture(base)
            shutil.rmtree(root)
            env, tmp = launch_env(base)
            completed = self.run_hook(
                root,
                json.dumps({"cwd": str(root)}).encode(),
                env,
                node,
                package / "dist/cli.js",
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(list(tmp.iterdir()), [])

    def test_malformed_payload_fails_before_scoping(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            absent = base / "absent-runtime"
            env, tmp = launch_env(base)
            completed = self.run_hook(root, b"not even json{", env, absent, absent)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(list(tmp.iterdir()), [])
            shutil.rmtree(root)
            completed = self.run_hook(root, b"not even json{", env, absent, absent)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(list(tmp.iterdir()), [])

    def test_related_event_launches_bridge_with_original_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = project_fixture(base)
            package = fake_runtime_fixture(base)
            node, marker = fake_node_fixture(base)
            payload = json.dumps(
                {"cwd": str(root), "hook_event_name": "Stop", "extra": "vérbatim"}
            ).encode()
            env, tmp = launch_env(base)
            completed = self.run_hook(root, payload, env, node, package / "dist/cli.js")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            observed = json.loads(marker.read_text())
            self.assertEqual(observed["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(observed["argv"][-1], "stop")
            self.assertTrue(
                observed["argv"][0].endswith("assets/graft-hook-entry.mjs"),
                observed["argv"],
            )
            self.assertEqual(list(tmp.iterdir()), [])

    def test_relative_binding_is_rejected_not_defaulted(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            elsewhere = base / "elsewhere"
            elsewhere.mkdir()
            absent = base / "absent-runtime"
            env, _tmp = launch_env(base)
            completed = self.run_hook(
                "relative/project",
                json.dumps({"cwd": str(elsewhere)}).encode(),
                env,
                absent,
                absent,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_arguments

_FOLLOWUP_OPTIONS = (
    ("--followup-manifest", "/private/manifest.json"),
    ("--followup-apply-receipt", "/private/apply.json"),
    ("--followup-deployment-evidence", "/private/deployment.json"),
    ("--followup-verification", "/private/verification.json"),
    ("--followup-cleanup-receipt", "/private/cleanup.json"),
)


class FollowupCliTests(unittest.TestCase):
    def _argv(self, *extra, phase="plan"):
        argv = [
            "migration",
            "--phase",
            phase,
            "--projects-root",
            "/repo/one",
            "--backup-root",
            "/private/backup",
            "--custodian",
            "release-owner",
        ]
        if phase != "plan":
            argv = ["migration", "--phase", phase, "--manifest", "/private/manifest.json"]
        return [*argv, *extra]

    def _followup_argv(self, *extra):
        flat = [token for pair in _FOLLOWUP_OPTIONS for token in pair]
        return self._argv(
            *flat, "--deployment-mode", "init", "--deployment-platform", "omp", *extra
        )

    def assert_parse_error(self, argv):
        stderr = io.StringIO()
        stdout = io.StringIO()
        with (
            contextlib.redirect_stderr(stderr),
            contextlib.redirect_stdout(stdout),
            self.assertRaises(SystemExit) as caught,
        ):
            onboard_arguments.parse_workflow_args(argv)
        self.assertEqual(caught.exception.code, 2, stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")

    def test_full_followup_group_parses_for_plan(self):
        args = onboard_arguments.parse_workflow_args(self._followup_argv())
        self.assertEqual(args.followup_manifest, "/private/manifest.json")
        self.assertEqual(args.followup_apply_receipt, "/private/apply.json")
        self.assertEqual(args.followup_deployment_evidence, "/private/deployment.json")
        self.assertEqual(args.followup_verification, "/private/verification.json")
        self.assertEqual(args.followup_cleanup_receipt, "/private/cleanup.json")
        self.assertEqual(args.deployment_mode, "init")
        self.assertEqual(args.deployment_platform, "omp")

    def test_partial_followup_group_is_rejected(self):
        # Each single option alone, and all-but-one, must fail closed.
        for index in range(len(_FOLLOWUP_OPTIONS)):
            only_one = [token for token in _FOLLOWUP_OPTIONS[index]]
            self.assert_parse_error(
                self._argv(
                    *only_one, "--deployment-mode", "init", "--deployment-platform", "omp"
                )
            )
        flat = [
            token
            for pair in _FOLLOWUP_OPTIONS[:-1]
            for token in pair
        ]
        self.assert_parse_error(
            self._argv(
                *flat, "--deployment-mode", "init", "--deployment-platform", "omp"
            )
        )

    def test_empty_followup_path_is_rejected(self):
        self.assert_parse_error(
            self._argv(
                "--followup-manifest",
                "   ",
                "--followup-apply-receipt",
                "/private/apply.json",
                "--followup-deployment-evidence",
                "/private/deployment.json",
                "--followup-verification",
                "/private/verification.json",
                "--followup-cleanup-receipt",
                "/private/cleanup.json",
                "--deployment-mode",
                "init",
                "--deployment-platform",
                "omp",
            )
        )

    def test_followup_options_rejected_outside_plan_phase(self):
        flat = [token for pair in _FOLLOWUP_OPTIONS for token in pair]
        self.assert_parse_error(self._argv(*flat, phase="apply"))

    def test_followup_rejects_successor_combination(self):
        self.assert_parse_error(
            self._followup_argv(
                "--successor-manifest",
                "/private/prev-manifest.json",
                "--successor-apply-receipt",
                "/private/prev-apply.json",
            )
        )

    def test_followup_rejects_publication_and_routing_options(self):
        self.assert_parse_error(
            self._followup_argv("--publication-decisions", "/private/decisions.json")
        )
        self.assert_parse_error(
            self._followup_argv("--routing-approvals", "/private/routing.json")
        )
        self.assert_parse_error(
            self._followup_argv("--routing-approval-key", "/private/key.pem")
        )
        for option in (
            "--publication-decisions",
            "--routing-approvals",
            "--routing-approval-key",
        ):
            with self.subTest(option=option, value=""):
                self.assert_parse_error(self._followup_argv(option, ""))

    def test_followup_requires_init_mode_and_explicit_omp_platform(self):
        flat = [token for pair in _FOLLOWUP_OPTIONS for token in pair]
        # Missing deployment mode.
        self.assert_parse_error(self._argv(*flat, "--deployment-platform", "omp"))
        # Wrong deployment mode.
        self.assert_parse_error(
            self._argv(
                *flat, "--deployment-mode", "init-projects", "--deployment-platform", "omp"
            )
        )
        # Missing platform entirely (must be explicit, never defaulted).
        self.assert_parse_error(self._argv(*flat, "--deployment-mode", "init"))
        # Codex platform is not a followup predecessor host.
        self.assert_parse_error(
            self._argv(*flat, "--deployment-mode", "init", "--deployment-platform", "codex")
        )

    def test_followup_rejects_graft_hooks(self):
        self.assert_parse_error(self._followup_argv("--graft-hooks"))

    def test_followup_option_rejects_repeats(self):
        self.assert_parse_error(
            self._followup_argv("--followup-manifest", "/private/other.json")
        )


if __name__ == "__main__":
    unittest.main()

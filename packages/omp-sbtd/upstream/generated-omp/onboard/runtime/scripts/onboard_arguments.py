"""Target SBTD workflow CLI argument grammar (P1-01 contract foundation).

``parse_workflow_args`` is the pure, executable parse contract for the target
workflow CLI: the existing check/check-projects/plan/init/reset/init-projects
modes without the removed Trellis flags, plus the full ``migration`` and
``recovery`` phase grammar from the PRD (sections 10.2.1 and 10.2.3).

``parse_workflow_args`` remains the full target grammar. The shared migration
parser helpers also serve the live CLI's implemented phase subset; parsing
never reads or writes user paths or loads referenced artifacts.
Authorization is never synthesized here: absent ``--yes``/``--confirm-cleanup``/
``--confirm-recovery`` tokens still parse so the owning handler can answer with
its blocked envelope, and confirmation IDs pass through unexamined because the
parser holds no loaded artifacts to compare them against.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

__all__ = [
    "SingleValueAction",
    "WorkflowArgumentParser",
    "add_cleanup_legacy_parser",
    "add_migration_parser",
    "add_recovery_parser",
    "add_upgrade_parser",
    "parse_workflow_args",
    "validate_cleanup_legacy_args",
    "validate_developer_name",
    "validate_migration_args",
    "validate_recovery_args",
    "validate_upgrade_args",
]

PROG = "onboard.py"

_DEVELOPER_PATTERN = re.compile(r"^[a-z0-9]+$")

_MIGRATION_PHASES = ("plan", "apply", "reconcile", "verify", "cleanup")
_RECOVERY_PHASES = ("plan", "apply")

# Phase rules map each phase to (required value options, optional options).
# Consent tokens (--yes/--confirm-cleanup/--confirm-recovery) are deliberately
# optional at parse level: the PRD makes their absence a blocked envelope from
# the handler, not an argparse syntax error.
_MIGRATION_RULES = {
    "plan": (
        ("projects_root", "backup_root", "custodian"),
        (
            "publication_decisions",
            "routing_approvals",
            "routing_approval_key",
            "successor_manifest",
            "successor_apply_receipt",
            "followup_manifest",
            "followup_apply_receipt",
            "followup_deployment_evidence",
            "followup_verification",
            "followup_cleanup_receipt",
            "deployment_mode",
            "deployment_platform",
            "graft_hooks",
            "json",
        ),
    ),
    "apply": (
        ("manifest",),
        (
            "apply_receipt",
            "yes",
            "json",
            "routing_approvals",
            "no_routing_approvals",
        ),
    ),
    "reconcile": (
        (
            "manifest",
            "apply_receipt",
            "missing_deployment_evidence",
            "deployment_evidence_out",
        ),
        ("yes", "json"),
    ),
    "verify": (
        ("manifest", "apply_receipt", "deployment_evidence"),
        ("json",),
    ),
    "cleanup": (
        ("manifest", "apply_receipt", "deployment_evidence", "verification"),
        ("cleanup_receipt", "confirm_cleanup", "upgrade_plan", "upgrade_receipt", "json"),
    ),
}
_MIGRATION_VALUE_OPTIONS = (
    "projects_root",
    "backup_root",
    "custodian",
    "publication_decisions",
    "routing_approvals",
    "routing_approval_key",
    "successor_manifest",
    "successor_apply_receipt",
    "followup_manifest",
    "followup_apply_receipt",
    "followup_deployment_evidence",
    "followup_verification",
    "followup_cleanup_receipt",
    "deployment_mode",
    "deployment_platform",
    "manifest",
    "apply_receipt",
    "deployment_evidence",
    "missing_deployment_evidence",
    "deployment_evidence_out",
    "verification",
    "cleanup_receipt",
    "confirm_cleanup",
    "upgrade_plan",
    "upgrade_receipt",
)
_MIGRATION_FLAG_OPTIONS = (
    "yes",
    "json",
    "graft_hooks",
    "no_routing_approvals",
)

_RECOVERY_RULES = {
    "plan": (
        ("manifest",),
        (
            "apply_receipt",
            "deployment_evidence",
            "cleanup_receipt",
            "projects_root",
            "json",
        ),
    ),
    "apply": (
        ("plan",),
        ("recovery_receipt", "confirm_recovery", "json"),
    ),
}
_RECOVERY_VALUE_OPTIONS = (
    "manifest",
    "apply_receipt",
    "deployment_evidence",
    "cleanup_receipt",
    "projects_root",
    "plan",
    "recovery_receipt",
    "confirm_recovery",
)
_RECOVERY_FLAG_OPTIONS = ("json",)

_CLEANUP_LEGACY_PHASES = ("plan", "apply")
_CLEANUP_LEGACY_RULES = {
    "plan": (("projects_root", "backup_root"), ("global_skills_dir", "json")),
    "apply": (("plan",), ("cleanup_receipt", "confirm_cleanup", "json")),
}
_CLEANUP_LEGACY_VALUE_OPTIONS = (
    "projects_root",
    "backup_root",
    "global_skills_dir",
    "plan",
    "cleanup_receipt",
    "confirm_cleanup",
)
_CLEANUP_LEGACY_FLAG_OPTIONS = ("json",)

# init/init-projects migration context: the three deployment evidence inputs
# are one group; --previous-deployment-evidence may only extend the group.
_MIGRATION_CONTEXT_GROUP = (
    "migration_manifest",
    "migration_apply_receipt",
    "deployment_evidence_out",
)
_MIGRATION_CONTEXT_OPTIONAL = ("previous_deployment_evidence",)

# Followup deployment batch: the five predecessor documents are one group;
# all five or none, plan phase only.
_FOLLOWUP_INPUTS = (
    "followup_manifest",
    "followup_apply_receipt",
    "followup_deployment_evidence",
    "followup_verification",
    "followup_cleanup_receipt",
)


def _option_name(dest: str) -> str:
    return "--" + dest.replace("_", "-")


def validate_developer_name(value: str) -> str:
    if not _DEVELOPER_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "developer must match ^[a-z0-9]+$ (lowercase letters and digits only)"
        )
    return value


class WorkflowArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse diagnostics can interpolate private paths and arbitrary tokens.
        # Usage is built only from this module's fixed program/option declarations.
        super().error("invalid arguments; use --help for supported syntax")


class SingleValueAction(argparse.Action):
    """Single-value option that rejects repeats instead of last-value-wins."""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            parser.error(f"{option_string} must be provided at most once")
        setattr(namespace, self.dest, values)


def _add_common_options(
    sub: argparse.ArgumentParser, *, projects_root_required: bool
) -> None:
    sub.add_argument(
        "--projects-root",
        action=SingleValueAction,
        required=projects_root_required,
        help="Comma-separated absolute project root paths.",
    )
    sub.add_argument(
        "--skip-project-agents",
        action="store_true",
        help="Skip the project AGENTS template; explicitly selected Graft wiring still maintains its managed fence.",
    )
    sub.add_argument(
        "--global-agents-path",
        action=SingleValueAction,
        help="Override Codex global AGENTS.md path.",
    )
    sub.add_argument(
        "--global-skills-dir",
        action=SingleValueAction,
        help="Override global skills directory.",
    )
    sub.add_argument(
        "--yes",
        action="store_true",
        help="Allow init/reset to write files.",
    )
    sub.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable plan.",
    )
    sub.add_argument(
        "--platform",
        action=SingleValueAction,
        help="Target Agent platform: codex, claude, kimi, oh-my-pi, or omp.",
    )
    sub.add_argument(
        "--developer",
        action=SingleValueAction,
        type=validate_developer_name,
        help="Developer identity (lowercase letters and digits).",
    )
    sub.add_argument(
        "--graft-hooks",
        action="store_true",
        help="Separately authorize the displayed Codex hooks; never grants host trust.",
    )


def _add_migration_context(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--migration-manifest",
        action=SingleValueAction,
        help="Migration manifest file for a migration-context deployment.",
    )
    sub.add_argument(
        "--migration-apply-receipt",
        action=SingleValueAction,
        help="Complete apply receipt bound to the migration manifest.",
    )
    sub.add_argument(
        "--previous-deployment-evidence",
        action=SingleValueAction,
        help="Previous deployment evidence file; required on retry, never alone.",
    )
    sub.add_argument(
        "--deployment-evidence-out",
        action=SingleValueAction,
        help="Unoccupied private target file for the new deployment evidence.",
    )


def add_migration_parser(
    subparsers: argparse._SubParsersAction,
    *,
    phases: Sequence[str] = _MIGRATION_PHASES,
) -> argparse.ArgumentParser:
    """Share phase declarations without advertising unimplemented phases."""
    if not phases or any(phase not in _MIGRATION_RULES for phase in phases):
        raise ValueError("unsupported migration parser phase set")
    migration = subparsers.add_parser("migration", allow_abbrev=False)
    migration.add_argument(
        "--phase",
        action=SingleValueAction,
        required=True,
        choices=tuple(phases),
        help="Explicit migration phase; deployment remains a separate operation.",
    )
    allowed = {
        option
        for phase in phases
        for options in _MIGRATION_RULES[phase]
        for option in options
    }
    descriptions = {
        "projects_root": "Comma-separated absolute project roots.",
        "backup_root": "Existing private backup directory outside the repositories.",
        "custodian": "Explicit responsible custodian label.",
        "publication_decisions": "Private approved publication-decisions file.",
        "routing_approvals": "Private approved routing-candidate record. Plan seals it; apply must be given the same file by the caller.",
        "routing_approval_key": "Private key outside the vault and selected projects. Plan uses it only to sign the routing approval file.",
        "successor_manifest": "Private manifest of one completed deployment-less batch; pairs with --successor-apply-receipt.",
        "successor_apply_receipt": "Private complete apply receipt of the same completed batch.",
        "followup_manifest": "Private manifest of the completed codex predecessor batch; requires all five --followup-* inputs.",
        "followup_apply_receipt": "Private complete apply receipt of the codex predecessor batch.",
        "followup_deployment_evidence": "Private successful deployment evidence of the codex predecessor batch.",
        "followup_verification": "Private verified verification record of the codex predecessor batch.",
        "followup_cleanup_receipt": "Private successful cleanup receipt of the codex predecessor batch.",
        "deployment_mode": "Declare deployment before apply: init or init-projects.",
        "deployment_platform": "Declare the deployment host: codex or omp.",
        "manifest": "Explicit private migration manifest file.",
        "apply_receipt": "Explicit apply receipt for retry or verification.",
        "deployment_evidence": "Explicit completed deployment evidence file.",
        "missing_deployment_evidence": "Explicit absent historical deployment evidence path; never overwritten.",
        "deployment_evidence_out": "New private current-state evidence output, distinct from the missing historical path.",
        "verification": "Explicit verification record for cleanup.",
        "cleanup_receipt": "Explicit cumulative cleanup receipt for retry.",
        "confirm_cleanup": "The verification_id confirmed for this cleanup attempt.",
        "upgrade_plan": "Native complete Onboard upgrade plan (cleanup only; pair with --upgrade-receipt).",
        "upgrade_receipt": "Native complete Onboard upgrade receipt (cleanup only).",
    }
    for dest in _MIGRATION_VALUE_OPTIONS:
        if dest not in allowed:
            continue
        option_kwargs = {"action": SingleValueAction, "help": descriptions[dest]}
        if dest == "deployment_platform":
            option_kwargs["choices"] = ("codex", "omp")
        migration.add_argument(_option_name(dest), **option_kwargs)
    for dest in _MIGRATION_FLAG_OPTIONS:
        if dest in allowed:
            migration.add_argument(
                _option_name(dest),
                action="store_true",
                help={
                    "yes": "Authorize this apply or current-state reconciliation attempt.",
                    "graft_hooks": "Plan explicitly authorized Codex hook definitions for full deployment.",
                    "json": "Emit the private single-JSON exchange document.",
                    "no_routing_approvals": "Apply a plan that has no routing approval record. Does not authorize AGENTS.md pause or marker removal.",
                }[dest],
            )
    return migration


def add_recovery_parser(subparsers: Any) -> argparse.ArgumentParser:
    recovery = subparsers.add_parser("recovery", allow_abbrev=False)
    recovery.add_argument(
        "--phase",
        action=SingleValueAction,
        required=True,
        choices=_RECOVERY_PHASES,
        help="Recovery phase: plan or apply.",
    )
    recovery.add_argument(
        "--manifest",
        action=SingleValueAction,
        help="Migration manifest file (plan only).",
    )
    recovery.add_argument(
        "--apply-receipt",
        action=SingleValueAction,
        help="Apply receipt evidence, possibly partial (plan only).",
    )
    recovery.add_argument(
        "--deployment-evidence",
        action=SingleValueAction,
        help="Deployment evidence, possibly partial (plan only).",
    )
    recovery.add_argument(
        "--cleanup-receipt",
        action=SingleValueAction,
        help="Cleanup receipt evidence, possibly partial (plan only).",
    )
    recovery.add_argument(
        "--projects-root",
        action=SingleValueAction,
        help="Optional manifest project subset for the recovery plan (plan only).",
    )
    recovery.add_argument(
        "--plan",
        action=SingleValueAction,
        help="Recovery plan file (apply only).",
    )
    recovery.add_argument(
        "--recovery-receipt",
        action=SingleValueAction,
        help="Recovery receipt for an explicit apply retry (apply only).",
    )
    recovery.add_argument(
        "--confirm-recovery",
        action=SingleValueAction,
        help="plan_id confirmed this run; absence stays blocked in the handler.",
    )
    recovery.add_argument(
        "--json",
        action="store_true",
        help="Print the single machine-readable envelope.",
    )
    for option in ("upgrade-plan", "upgrade-receipt", "upgrade-recovery-plan", "output"):
        recovery.add_argument("--" + option, action=SingleValueAction)
    return recovery


def add_upgrade_parser(subparsers: Any) -> argparse.ArgumentParser:
    upgrade = subparsers.add_parser("upgrade", allow_abbrev=False)
    upgrade.add_argument("--phase", action=SingleValueAction, required=True,
                         choices=("plan", "apply", "verify", "authorize-link"))
    for option, help_text in (
        ("scope", "Explicit version-1 upgrade scope JSON (plan only)."),
        ("backup-root", "Existing private vault, outside every source and target."),
        ("output", "Save a new plan in its private vault; otherwise stdout only."),
        ("plan", "Previously displayed sealed upgrade plan."),
        ("receipt", "Bound cumulative receipt for retry or verification."),
        ("confirm-plan", "The displayed plan_id, not a substitute for authorization."),
        ("host", "Scope host id owning the linked Skill (authorize-link only)."),
        ("skill-path", "Absolute logical path of the linked Skill (authorize-link only)."),
        ("target-path", "Operator-supplied physical link target directory (authorize-link only)."),
        ("link-authorization", "Comma-separated sealed link authorization artifacts (verify --probe only)."),
    ):
        upgrade.add_argument("--" + option, action=SingleValueAction, help=help_text)
    upgrade.add_argument("--yes", action="store_true", help="Authorize the displayed operation.")
    upgrade.add_argument("--probe", action="store_true", help="Explicitly run runtime/host probes; requires --yes.")
    upgrade.add_argument("--json", action="store_true")
    return upgrade


def validate_upgrade_args(
    args: argparse.Namespace, *, parser: argparse.ArgumentParser
) -> None:
    _check_phase(
        parser, args,
        ("scope", "backup_root", "output", "plan", "receipt", "confirm_plan",
         "host", "skill_path", "target_path", "link_authorization"),
        ("yes", "probe", "json"),
        {
            "plan": (("scope", "backup_root"), ("output", "json")),
            "apply": (("plan",), ("receipt", "confirm_plan", "yes", "json")),
            "verify": (("plan",), ("receipt", "probe", "yes", "json", "link_authorization")),
            "authorize-link": (("plan", "host", "skill_path", "target_path"),
                               ("output", "json")),
        },
    )
    if args.phase == "verify" and args.yes and not args.probe:
        parser.error("--yes is only meaningful with --probe during verification")
    if args.phase == "verify" and args.link_authorization and not args.probe:
        parser.error("--link-authorization is only meaningful with --probe during verification")


def add_cleanup_legacy_parser(subparsers: Any) -> argparse.ArgumentParser:
    cleanup = subparsers.add_parser("cleanup-legacy", allow_abbrev=False)
    cleanup.add_argument(
        "--phase",
        action=SingleValueAction,
        required=True,
        choices=_CLEANUP_LEGACY_PHASES,
        help="Legacy cleanup phase: plan (read-only detection) or apply.",
    )
    cleanup.add_argument(
        "--projects-root",
        action=SingleValueAction,
        help="Comma-separated absolute project root paths (plan only).",
    )
    cleanup.add_argument(
        "--backup-root",
        action=SingleValueAction,
        help="Existing private backup directory outside the repositories (plan only).",
    )
    cleanup.add_argument(
        "--global-skills-dir",
        action=SingleValueAction,
        help="Global Skills root override, sealed into the plan (plan only).",
    )
    cleanup.add_argument(
        "--plan",
        action=SingleValueAction,
        help="Sealed cleanup plan file (apply only).",
    )
    cleanup.add_argument(
        "--cleanup-receipt",
        action=SingleValueAction,
        help="Cumulative cleanup receipt for an explicit apply retry (apply only).",
    )
    cleanup.add_argument(
        "--confirm-cleanup",
        action=SingleValueAction,
        help="plan_id confirmed this run; absence stays blocked in the handler.",
    )
    cleanup.add_argument(
        "--json",
        action="store_true",
        help="Print the single machine-readable envelope.",
    )
    return cleanup


def validate_cleanup_legacy_args(
    args: argparse.Namespace, *, parser: argparse.ArgumentParser
) -> None:
    _check_phase(
        parser,
        args,
        _CLEANUP_LEGACY_VALUE_OPTIONS,
        _CLEANUP_LEGACY_FLAG_OPTIONS,
        _CLEANUP_LEGACY_RULES,
    )


def validate_recovery_args(
    args: argparse.Namespace, *, parser: argparse.ArgumentParser
) -> None:
    upgrade_options = ("upgrade_plan", "upgrade_receipt", "upgrade_recovery_plan", "output")
    is_upgrade = any(getattr(args, key, None) is not None for key in upgrade_options)
    if is_upgrade:
        _check_phase(
            parser, args, (*_RECOVERY_VALUE_OPTIONS, *upgrade_options),
            _RECOVERY_FLAG_OPTIONS,
            {
                "plan": (("upgrade_plan", "upgrade_receipt"), ("output", "json")),
                "apply": (("upgrade_recovery_plan",),
                          ("confirm_recovery", "recovery_receipt", "json")),
            },
        )
    else:
        _check_phase(
            parser, args, _RECOVERY_VALUE_OPTIONS, _RECOVERY_FLAG_OPTIONS, _RECOVERY_RULES
        )


def _build_parser() -> tuple[
    argparse.ArgumentParser, dict[str, argparse.ArgumentParser]
]:
    parser = WorkflowArgumentParser(
        prog=PROG,
        allow_abbrev=False,
        description="Target SBTD workflow CLI grammar (contract; not the live entry point).",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subs: dict[str, argparse.ArgumentParser] = {}

    for mode in ("check", "plan", "init", "reset", "init-projects"):
        sub = subparsers.add_parser(mode, allow_abbrev=False)
        _add_common_options(sub, projects_root_required=mode == "init-projects")
        if mode in ("init", "init-projects"):
            _add_migration_context(sub)
        subs[mode] = sub

    project_check = subparsers.add_parser("check-projects", allow_abbrev=False)
    project_check.add_argument(
        "--projects-root",
        action=SingleValueAction,
        required=True,
        help="Comma-separated absolute project root paths.",
    )
    project_check.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable project checks.",
    )
    project_check.add_argument(
        "--skip-project-agents",
        action="store_true",
        help="Exclude project AGENTS.md from installation-target checks.",
    )
    subs["check-projects"] = project_check

    subs["migration"] = add_migration_parser(subparsers)

    subs["recovery"] = add_recovery_parser(subparsers)

    subs["cleanup-legacy"] = add_cleanup_legacy_parser(subparsers)
    subs["upgrade"] = add_upgrade_parser(subparsers)

    return parser, subs


def _check_phase(
    sub: argparse.ArgumentParser,
    args: argparse.Namespace,
    value_options: Sequence[str],
    flag_options: Sequence[str],
    rules: Mapping[str, tuple[Sequence[str], Sequence[str]]],
) -> None:
    required, optional = rules[args.phase]
    allowed = set(required) | set(optional)
    for dest in value_options:
        if getattr(args, dest, None) is not None and dest not in allowed:
            sub.error(f"{_option_name(dest)} is not valid for phase {args.phase!r}")
    for dest in flag_options:
        if getattr(args, dest, False) and dest not in allowed:
            sub.error(f"{_option_name(dest)} is not valid for phase {args.phase!r}")
    for dest in required:
        if getattr(args, dest, None) is None:
            sub.error(f"{_option_name(dest)} is required for phase {args.phase!r}")


def validate_migration_args(
    args: argparse.Namespace, *, parser: argparse.ArgumentParser
) -> None:
    _check_phase(
        parser,
        args,
        _MIGRATION_VALUE_OPTIONS,
        _MIGRATION_FLAG_OPTIONS,
        _MIGRATION_RULES,
    )
    if args.phase == "cleanup":
        upgrade_paths = (
            getattr(args, "upgrade_plan", None),
            getattr(args, "upgrade_receipt", None),
        )
        if any(value is not None for value in upgrade_paths) and not all(
            isinstance(value, str) and value.strip() for value in upgrade_paths
        ):
            parser.error("--upgrade-plan and --upgrade-receipt require two nonempty paths")
    if (
        args.phase == "apply"
        and getattr(args, "routing_approvals", None)
        and getattr(args, "no_routing_approvals", False)
    ):
        parser.error(
            "--routing-approvals cannot be combined with --no-routing-approvals"
        )
    successor_seen = (
        getattr(args, "successor_manifest", None) is not None
        or getattr(args, "successor_apply_receipt", None) is not None
    )
    if args.phase == "plan" and successor_seen:
        if (
            getattr(args, "successor_manifest", None) is None
            or getattr(args, "successor_apply_receipt", None) is None
        ):
            parser.error(
                "--successor-manifest and --successor-apply-receipt must be supplied as a pair"
            )
        if (
            not args.successor_manifest.strip()
            or not args.successor_apply_receipt.strip()
        ):
            parser.error("successor input paths must be nonempty")
        if getattr(args, "publication_decisions", None):
            parser.error(
                "--successor-manifest cannot be combined with --publication-decisions"
            )
        if getattr(args, "routing_approvals", None) or getattr(
            args, "routing_approval_key", None
        ):
            parser.error(
                "successor inputs cannot be combined with routing approval options"
            )
        if not getattr(args, "deployment_mode", None):
            parser.error("successor inputs require --deployment-mode")
    followup_seen = any(
        getattr(args, dest, None) is not None for dest in _FOLLOWUP_INPUTS
    )
    if args.phase == "plan" and followup_seen:
        missing = [
            _option_name(dest)
            for dest in _FOLLOWUP_INPUTS
            if getattr(args, dest, None) is None
        ]
        if missing:
            parser.error(
                "followup inputs require all five predecessor documents; missing "
                + ", ".join(missing)
            )
        if any(not getattr(args, dest).strip() for dest in _FOLLOWUP_INPUTS):
            parser.error("followup input paths must be nonempty")
        if successor_seen:
            parser.error("followup inputs cannot be combined with successor inputs")
        if getattr(args, "publication_decisions", None) is not None:
            parser.error(
                "followup inputs cannot be combined with --publication-decisions"
            )
        if (
            getattr(args, "routing_approvals", None) is not None
            or getattr(args, "routing_approval_key", None) is not None
        ):
            parser.error(
                "followup inputs cannot be combined with routing approval options"
            )
        if getattr(args, "deployment_mode", None) != "init":
            parser.error("followup inputs require --deployment-mode init")
        if getattr(args, "deployment_platform", None) != "omp":
            parser.error("followup inputs require --deployment-platform omp")
        if getattr(args, "graft_hooks", False):
            parser.error("followup inputs cannot be combined with --graft-hooks")


def _check_migration_context(
    sub: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    group = _MIGRATION_CONTEXT_GROUP + _MIGRATION_CONTEXT_OPTIONAL
    if all(getattr(args, dest) is None for dest in group):
        return
    missing = [
        _option_name(dest)
        for dest in _MIGRATION_CONTEXT_GROUP
        if getattr(args, dest) is None
    ]
    if missing:
        sub.error(
            "migration context requires --migration-manifest, --migration-apply-receipt "
            "and --deployment-evidence-out as a group; missing " + ", ".join(missing)
        )


def parse_workflow_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse target workflow CLI arguments into an argparse.Namespace.

    Pure parsing only: no referenced path is read or written, no artifact is
    loaded, and no consent is invented. Syntax and combination errors follow
    argparse semantics: a diagnostic on stderr and exit status 2.
    """

    parser, subs = _build_parser()
    args = parser.parse_args(argv)
    if args.mode == "migration":
        validate_migration_args(args, parser=subs["migration"])
    elif args.mode == "recovery":
        validate_recovery_args(args, parser=subs["recovery"])
    elif args.mode == "upgrade":
        validate_upgrade_args(args, parser=subs["upgrade"])
    elif args.mode == "cleanup-legacy":
        validate_cleanup_legacy_args(args, parser=subs["cleanup-legacy"])
    elif args.mode in ("init", "init-projects"):
        _check_migration_context(subs[args.mode], args)
    return args

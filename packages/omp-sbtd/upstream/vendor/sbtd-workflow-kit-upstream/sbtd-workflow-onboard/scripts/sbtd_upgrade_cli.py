"""Public upgrade CLI: explicit inputs, phase-local consent, one redacted JSON result."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onboard_contracts import ContractError
from sbtd_cleanup_targets import strict_json_object
from sbtd_migration_files import read_file, save_document, snapshot


def _input_path(value: str) -> Path:
    try:
        return Path(value).expanduser().absolute()
    except RuntimeError:
        raise ValueError("input home directory cannot be expanded") from None


def _load(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("input path must not be empty")
    path = _input_path(value)
    state = snapshot(path)
    if state["type"] != "file":
        raise ValueError("input must be a regular JSON file")
    return strict_json_object(read_file(path, state))


def _save(plan: dict[str, Any], output: str | None) -> str | None:
    if output is None:
        return None
    vault = Path(plan["payload"]["backup_root"])
    path = _input_path(output)
    save_document(path, plan, private_root=vault)
    return str(path)


def _save_authorization(
    plan: dict[str, Any], authorization: dict[str, Any], output: str | None
) -> str | None:
    """Persist a sealed link authorization inside the bound plan's vault."""
    if output is None:
        return None
    vault = Path(plan["payload"]["backup_root"])
    path = _input_path(output)
    save_document(path, authorization, private_root=vault)
    return str(path)


def _split_path_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    if not items or any(not item for item in items):
        raise ValueError("a supplied path must not be blank")
    return items


def _emit(args: Any, document: dict[str, Any], code: int) -> int:
    # Human output uses the same metadata-only document; never print raw errors
    # from JSON/TOML parsers or subprocess output that could contain credentials.
    print(json.dumps(document, ensure_ascii=False, allow_nan=False,
                     indent=None if args.json else 2))
    return code


def _failure(args: Any, error: Exception, mode: str) -> int:
    code = getattr(error, "exit_code", 2)
    reason = getattr(error, "code", "invalid-input")
    details = getattr(error, "details", None)
    batch = details.get("batch") if isinstance(details, dict) else None
    if batch is not None:
        # Post-mutation halt: bind the batch identity, backup root, latest
        # checkpoint and measured/unknown mutation state. The checkpoint is
        # recovery evidence, never this attempt's success; pre-write errors
        # below stay generic blocked.
        return _emit(args, {"mode": mode, "phase": args.phase, "status": "failed",
                            "reason": reason, "batch": batch,
                            "nextStep": "Inspect the bound checkpoint and backup root, reconcile unknown mutation, then re-plan recovery; originals are preserved."},
                     3)
    return _emit(args, {"mode": mode, "phase": args.phase, "status": "blocked",
                        "reason": reason,
                        "nextStep": "Check input paths, private vault, declared dependencies and the selected phase; preserve originals."},
                 code if code in (2, 3) else 2)


def _validate_supplied_paths(args: Any, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(args, name, None)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError("a supplied path must not be blank")


def run_upgrade(args: Any) -> int:
    if args.phase == "verify" and args.probe and not args.yes:
        return _emit(args, {"mode": "upgrade", "phase": "verify", "status": "blocked",
                            "reason": "probe-confirmation-required",
                            "nextStep": "Review the selected probe scope, then explicitly confirm with --yes."}, 2)
    try:
        _validate_supplied_paths(
            args,
            ("scope", "backup_root", "output", "plan", "receipt",
             "host", "skill_path", "target_path", "link_authorization"),
        )
        from sbtd_upgrade import (
            apply_upgrade,
            plan_upgrade,
            prepare_probe_link_authorization,
            verify_upgrade,
        )

        if args.phase == "plan":
            plan = plan_upgrade(_load(args.scope), _input_path(args.backup_root))
            output = _save(plan, args.output)
            result = {"mode": "upgrade", "phase": "plan", "plan": plan, "plan_path": output}
            status = plan["payload"].get("status", "planned")
            return _emit(args, result, 2 if status == "blocked" else 0)
        plan = _load(args.plan)
        if args.phase == "authorize-link":
            authorization = prepare_probe_link_authorization(
                plan,
                host_id=args.host,
                skill_path=str(_input_path(args.skill_path)),
                target_path=str(_input_path(args.target_path)),
            )
            output = _save_authorization(plan, authorization, args.output)
            result = {
                "mode": "upgrade",
                "phase": "authorize-link",
                "authorization": authorization,
                "authorization_path": output,
            }
            return _emit(args, result, 0)
        receipt = _load(args.receipt) if args.receipt is not None else None
        if args.phase == "apply":
            confirmed = args.confirm_plan if args.yes else None
            result = apply_upgrade(plan, confirmed=confirmed, receipt=receipt)
        else:
            link_authorizations = None
            if args.link_authorization is not None:
                link_authorizations = [
                    _load(item) for item in _split_path_list(args.link_authorization)
                ]
            result = verify_upgrade(
                plan, receipt=receipt, probe=args.probe,
                link_authorizations=link_authorizations,
            )
        status = result.get("status", result.get("payload", {}).get("status"))
        code = 3 if status in {"failed", "partial"} else 0 if status in {"complete", "aligned"} else 2
        return _emit(args, result, code)
    except (ContractError, OSError, ValueError, TypeError, KeyError, ImportError) as error:
        return _failure(args, error, "upgrade")


def run_upgrade_recovery(args: Any) -> int:
    try:
        _validate_supplied_paths(
            args, ("upgrade_plan", "upgrade_receipt", "upgrade_recovery_plan",
                   "output", "recovery_receipt"),
        )
        from sbtd_upgrade import apply_recovery, plan_recovery

        if args.phase == "plan":
            plan = plan_recovery(_load(args.upgrade_plan), _load(args.upgrade_receipt))
            output = _save(plan, args.output)
            return _emit(args, {"mode": "recovery", "phase": "plan", "plan": plan,
                                "plan_path": output},
                         2 if plan["payload"].get("status") == "blocked" else 0)
        plan = _load(args.upgrade_recovery_plan)
        receipt = _load(args.recovery_receipt) if args.recovery_receipt is not None else None
        result = apply_recovery(plan, confirmed=args.confirm_recovery, receipt=receipt)
        status = result.get("status", result.get("payload", {}).get("status"))
        code = 3 if status in {"failed", "partial"} else 0 if status == "complete" else 2
        return _emit(args, result, code)
    except (ContractError, OSError, ValueError, TypeError, KeyError, ImportError) as error:
        return _failure(args, error, "recovery")

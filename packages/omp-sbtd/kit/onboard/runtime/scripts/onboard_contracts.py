"""Strict codec and semantic contracts for SBTD Onboard v1 exchange objects.

Boundary (docs/prd/sbtd-workflow-v2-onboard-contracts.md, main PRD section 10.2):

- Pure functions over caller-provided Python values and raw bytes, except that
  containment checks may read filesystem identity metadata for existing path
  aliases. The module never opens object-ref targets, scans directories,
  performs network or mutation, or infers that a stage whose document was not
  supplied was unexecuted.
- Schema validity, canonical IDs and declared bindings prove structure and
  declared relationships only. They are not filesystem safety, authorization,
  execution or smoke proof; runtime producers own those checks.
- Deployment evidence may carry an optional closed ``payload.reconciliation``
  record marking a current-state observation of an interrupted deployment:
  ``historical_execution`` stays ``unknown``, the record cites the exact
  original manifest/apply input bytes, and ``succeeded`` then means the
  current postconditions were accepted, never that the original process was
  observed to exit0 or that new target writes occurred.
- ``jsonschema`` is imported lazily inside the validation path so that module
  import, pure argument parsing and the existing CLI keep working without the
  dependency. Missing ``jsonschema`` fails closed with a clear ContractError;
  there is no fallback weak validator.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime
from itertools import chain
from pathlib import Path
from typing import Any, NoReturn

SCHEMA_VERSION = 1
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "onboard-contracts.schema.json"
SCHEMA_ID = "urn:sbtd:onboard-contracts:schema:1"
GRAFT_BUILD_POLICY_PATH = SCHEMA_PATH.parent / "assets" / "graft-build-policy.json"
GRAFT_BUILD_POLICY_SHA256 = (
    "70cc0ada685fe417bce093470339ac96445d4a130a1c61968e57c97249bd4d6d"
)

# kind -> (schema $def name, payload digest key or None)
_DOCUMENT_KINDS: dict[str, tuple[str, str | None]] = {
    "publication_decisions": ("publication_decisions", None),
    "manifest": ("manifest", "manifest_id"),
    "apply_receipt": ("apply_receipt", "apply_id"),
    "verification": ("verification", "verification_id"),
    "cleanup_receipt": ("cleanup_receipt", "cleanup_id"),
    "deployment_evidence": ("deployment_evidence", "deployment_id"),
    "recovery_plan": ("recovery_plan", "plan_id"),
    "recovery_receipt": ("recovery_receipt", "receipt_id"),
    "migration_envelope": ("migration_envelope", None),
    "recovery_envelope": ("recovery_envelope", None),
}

_STAGE_RECEIPT_PHASES = {
    "apply_receipt": "apply",
    "deployment_evidence": "deploy",
    "cleanup_receipt": "cleanup",
}
_PHASE_RECEIPTS = {phase: kind for kind, phase in _STAGE_RECEIPT_PHASES.items()}

_PHASE_ORDER = {"apply": 0, "deploy": 1, "cleanup": 2}
_INVERSE_PHASE_ORDER = {"cleanup": 0, "deploy": 1, "apply": 2}

_BINDABLE_KINDS = frozenset(
    {
        "apply_receipt",
        "verification",
        "cleanup_receipt",
        "deployment_evidence",
        "recovery_plan",
        "recovery_receipt",
    }
)
_RAW_KINDS = frozenset({"manifest"} | _BINDABLE_KINDS)

_CUMULATIVE_KINDS: dict[str, tuple[str, str]] = {
    "apply_receipt": ("apply_id", "previous_receipt_id"),
    "cleanup_receipt": ("cleanup_id", "previous_receipt_id"),
    "deployment_evidence": ("deployment_id", "previous_deployment_id"),
    "recovery_receipt": ("receipt_id", "previous_receipt_id"),
}

# Retired public Trellis report fields (PRD section 10.2 cutover). The JSON
# writer refuses them instead of silently aliasing them to new names.
_RETIRED_TOP_LEVEL_KEYS = frozenset({"trellis", "trellisInit", "trellisProjectSetup"})

_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)

_ENVELOPE_PROJECT_STATUSES = {
    ("migration", "plan"): frozenset({"planned", "blocked", "failed"}),
    ("migration", "apply"): frozenset(
        {"applied", "already-complete", "blocked", "failed"}
    ),
    ("migration", "reconcile"): frozenset({"reconciled", "blocked", "failed"}),
    ("migration", "verify"): frozenset({"verified", "blocked", "failed"}),
    ("migration", "cleanup"): frozenset(
        {"cleaned", "already-complete", "blocked", "failed"}
    ),
    ("recovery", "plan"): frozenset({"planned", "blocked", "failed"}),
    ("recovery", "apply"): frozenset(
        {"restored", "already-complete", "blocked", "failed"}
    ),
}

# (mode, phase) -> (artifact holder field, artifact key, artifact document kind)
_ENVELOPE_ARTIFACT = {
    ("migration", "plan"): ("migration", "manifest", "manifest"),
    ("migration", "apply"): ("migration", "apply_receipt", "apply_receipt"),
    ("migration", "reconcile"): (
        "migration",
        "deployment_evidence",
        "deployment_evidence",
    ),
    ("migration", "verify"): ("migration", "verification", "verification"),
    ("migration", "cleanup"): ("migration", "cleanup_receipt", "cleanup_receipt"),
    ("recovery", "plan"): ("recovery", "plan", "recovery_plan"),
    ("recovery", "apply"): ("recovery", "receipt", "recovery_receipt"),
}

# Envelope success variants that name a transport-phase outcome distinct from
# the embedded artifact's own success status. A reconciled envelope embeds
# current-state deployment evidence whose payload status stays "succeeded".
_ENVELOPE_SUCCESS_ALIASES = {"reconciled": "succeeded"}


def _artifact_success(status: str) -> str:
    return _ENVELOPE_SUCCESS_ALIASES.get(status, status)

_ENVELOPE_IDENTIFIER_KEYS = {
    "migration": frozenset({"manifest_id", "verification_id"}),
    "recovery": frozenset({"manifest_id", "plan_id", "receipt_id"}),
}

_STAGE_SUCCESS_STATUSES = {
    "apply": frozenset({"applied", "already-complete"}),
    "deploy": frozenset({"succeeded"}),
    "cleanup": frozenset({"cleaned", "already-complete"}),
}

__all__ = [
    "ContractError",
    "canonical_json_bytes",
    "load_document",
    "make_envelope",
    "operation_id",
    "recovery_step_id",
    "resource_id",
    "seal_document",
    "validate_cumulative",
    "validate_declared_bindings",
    "validate_deployment_result",
    "validate_document",
    "write_json_response",
]


class ContractError(Exception):
    """Sanitized contract failure.

    ``message`` names the fixed rule that failed and never echoes rejected
    values, raw jsonschema messages or private digests. ``code`` is a stable
    machine token; ``exit_code`` follows the PRD migration semantics
    (2 = invalid input or state conflict, 3 = digest/preservation failure).
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 2,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = None if details is None else dict(details)


# ---------------------------------------------------------------------------
# Canonical serialization and stable identifiers
# ---------------------------------------------------------------------------


def canonical_json_bytes(value: Any) -> bytes:
    """UTF-8 canonical JSON: sorted keys, compact separators, no ASCII escaping."""
    try:
        _check_json_safe(value, allow_numbers=True)
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except ContractError as error:
        if error.code == "malformed-unicode":
            raise
        raise ContractError(
            "non-json-value", "value cannot be serialized as canonical contract JSON"
        ) from None
    except (TypeError, ValueError, RecursionError) as error:
        raise ContractError(
            "non-json-value", "value cannot be serialized as canonical contract JSON"
        ) from error
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ContractError(
            "malformed-unicode", "value contains unpaired Unicode surrogates"
        ) from error


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _raw_digest(raw: bytes | bytearray) -> str:
    return hashlib.sha256(bytes(raw)).hexdigest()


def resource_id(owner_kind: str, target: str) -> str:
    """SHA-256 of the canonical JSON array [owner_kind, normalized_target_path]."""
    _require_strings(("owner_kind", owner_kind), ("target", target))
    return _digest([owner_kind, target])


def operation_id(phase: str, resource: str, selector: str) -> str:
    """SHA-256 of the canonical JSON array [phase, resource_id, selector]."""
    _require_strings(
        ("phase", phase), ("resource_id", resource), ("selector", selector)
    )
    return _digest([phase, resource, selector])


def recovery_step_id(manifest: str, phase: str, resource: str) -> str:
    """SHA-256 of ["recovery", manifest_id, phase, resource_id]; stable per resource/phase."""
    _require_strings(
        ("manifest_id", manifest), ("phase", phase), ("resource_id", resource)
    )
    return _digest(["recovery", manifest, phase, resource])


def _require_strings(*pairs: tuple[str, Any]) -> None:
    for name, value in pairs:
        if not isinstance(value, str):
            raise ContractError("invalid-argument", f"{name} must be a string")


# ---------------------------------------------------------------------------
# Strict decoding
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate-key", "JSON object contains a duplicate key")
        result[key] = value
    return result


def _parse_number(text: str) -> int:
    # Contract v1 defines integers only; any non-integer JSON number literal is
    # a wrong type, and non-finite results are rejected outright.
    value = float(text)
    if not math.isfinite(value):
        raise ContractError("non-finite-number", "JSON number is not finite")
    raise ContractError(
        "unexpected-type", "contract v1 documents do not allow non-integer numbers"
    )


def _reject_constant(text: str) -> Any:
    raise ContractError("non-finite-number", "JSON literal is not a finite number")


def _decode_strict(raw: bytes | bytearray | str) -> Any:
    if isinstance(raw, (bytes, bytearray)):
        try:
            text = bytes(raw).decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ContractError(
                "invalid-utf8", "document is not strict UTF-8"
            ) from error
    elif isinstance(raw, str):
        text = raw
    else:
        raise ContractError("unexpected-type", "raw document must be bytes or str")
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_parse_number,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError) as error:
        raise ContractError(
            "invalid-json", "document is not well-formed JSON"
        ) from error


def _check_json_safe(value: Any, *, allow_numbers: bool = False) -> None:
    try:
        _walk_json_value(value, allow_numbers=allow_numbers)
    except RecursionError:
        raise ContractError(
            "non-json-value", "value cannot be represented as contract JSON"
        ) from None


def _walk_json_value(value: Any, *, allow_numbers: bool = False) -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(
                "non-finite-number", "value contains a non-finite number"
            )
        if not allow_numbers:
            raise ContractError(
                "unexpected-type",
                "contract v1 documents do not allow non-integer numbers",
            )
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ContractError(
                "malformed-unicode", "value contains unpaired Unicode surrogates"
            ) from error
        return
    if isinstance(value, list):
        for item in value:
            _walk_json_value(item, allow_numbers=allow_numbers)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(
                    "unexpected-type", "JSON object keys must be strings"
                )
            _walk_json_value(key, allow_numbers=allow_numbers)
            _walk_json_value(item, allow_numbers=allow_numbers)
        return
    raise ContractError(
        "unexpected-type", "value is not representable as contract JSON"
    )


# ---------------------------------------------------------------------------
# Lazy jsonschema validator with real format checks
# ---------------------------------------------------------------------------

_VALIDATOR: Any = None


def _is_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if not _TIMESTAMP_RE.match(value):
        raise ValueError("timestamp must be RFC 3339 with seconds and a timezone")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must carry a timezone offset")
    return True


def _is_normalized_absolute_path(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if not value or "\x00" in value:
        raise ValueError("path must be non-empty and NUL-free")
    if os.name == "posix" and value.startswith("//"):
        raise ValueError("POSIX paths must have one leading slash")
    if not os.path.isabs(value):
        raise ValueError("path must be absolute")
    if os.path.normpath(value) != value:
        raise ValueError("path must be normalized")
    return True


def _contract_validator() -> Any:
    global _VALIDATOR
    if _VALIDATOR is not None:
        return _VALIDATOR
    try:
        import jsonschema
    except ImportError as error:
        raise ContractError(
            "validator-unavailable",
            "contract validation requires jsonschema; "
            "install sbtd-workflow-onboard/requirements.txt",
        ) from error
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(
            "schema-unavailable",
            "onboard contract schema is missing or unreadable next to the module",
        ) from error
    format_checker = jsonschema.FormatChecker()
    format_checker.checks("date-time", raises=ValueError)(_is_timestamp)
    format_checker.checks("normalized-absolute-path", raises=ValueError)(
        _is_normalized_absolute_path
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    _VALIDATOR = jsonschema.Draft202012Validator(schema, format_checker=format_checker)
    return _VALIDATOR


def _schema_validate(value: Any, def_name: str, kind: str) -> None:
    validator = _contract_validator()
    evolved = validator.evolve(schema={"$ref": f"{SCHEMA_ID}#/$defs/{def_name}"})
    error = next(evolved.iter_errors(value), None)
    if error is not None:
        location = "$"
        for part in error.absolute_path:
            location += f".{part}" if isinstance(part, str) else f"[{part}]"
        raise ContractError(
            "schema-violation", f"{kind} violates the contract schema at {location}"
        )


# ---------------------------------------------------------------------------
# Semantic invariant helpers
# ---------------------------------------------------------------------------


def _fail(code: str, message: str, *, exit_code: int = 2) -> NoReturn:
    raise ContractError(code, message, exit_code=exit_code)


def _path_contains(parent: str, child: str) -> bool:
    """Return whether child is inside parent, resolving only provable live aliases."""
    parent_path = Path(parent)
    child_path = Path(child)
    try:
        parent_path = parent_path.resolve(strict=False)
        child_path = child_path.resolve(strict=False)
    except (OSError, RuntimeError):
        pass
    if child_path.is_relative_to(parent_path):
        return True

    def existing_ancestors(path: Path) -> Iterator[tuple[Path, os.stat_result]]:
        for ancestor in (path, *path.parents):
            try:
                identity = ancestor.stat()
            except OSError:
                continue
            yield ancestor, identity

    # Keep observations local to this call: samefile would stat both paths
    # again for every pair, despite the identities already being available.
    parent_ancestors = tuple(existing_ancestors(parent_path))
    for child_ancestor, child_identity in existing_ancestors(child_path):
        child_tail = child_path.relative_to(child_ancestor).parts
        for parent_ancestor, parent_identity in parent_ancestors:
            if not os.path.samestat(parent_identity, child_identity):
                continue
            parent_tail = parent_path.relative_to(parent_ancestor).parts
            if child_tail[: len(parent_tail)] == parent_tail:
                return True
    return False


def _publication_paths_overlap(left: str, right: str) -> bool:
    """Reject ambiguous new output names without changing resource identity.

    Absent names have no inode to compare. Reserve case/Unicode-equivalent
    spellings conservatively, including on case-sensitive filesystems.
    """
    if _path_contains(left, right) or _path_contains(right, left):
        return True
    left_parts = tuple(unicodedata.normalize("NFC", p).casefold() for p in Path(left).parts)
    right_parts = tuple(unicodedata.normalize("NFC", p).casefold() for p in Path(right).parts)
    length = min(len(left_parts), len(right_parts))
    return left_parts[:length] == right_parts[:length]


def _paths_overlap(paths: Iterable[str]) -> bool:
    values = list(paths)
    return any(
        _path_contains(path, other) or _path_contains(other, path)
        for index, path in enumerate(values)
        for other in values[index + 1 :]
    )


def _paths_identify_same(paths: Iterable[str]) -> bool:
    values = list(paths)
    return any(
        _path_contains(path, other) and _path_contains(other, path)
        for index, path in enumerate(values)
        for other in values[index + 1 :]
    )


def _check_publication_items(items: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    path_states: dict[str, Any] = {}
    targets: list[str] = []
    for item in items:
        if item["item_id"] in seen_ids:
            _fail("semantic-violation", "duplicate publication item_id")
        seen_ids.add(item["item_id"])
        expected_scope = {
            "sources": item["sources"],
            "target_path": item["target_path"],
            "decision": item["decision"],
            "candidate_ref": item["candidate_ref"],
        }
        if item["approval"]["scope"] != expected_scope:
            _fail(
                "semantic-violation",
                "approval.scope is not an exact snapshot of the declared item fields",
            )
        source_paths = [source["path"] for source in item["sources"]]
        if len(set(source_paths)) != len(source_paths):
            _fail(
                "semantic-violation",
                "duplicate source path within one publication item",
            )
        references = list(item["sources"])
        if item["candidate_ref"] is not None:
            references.append(item["candidate_ref"])
        for reference in references:
            if (
                path_states.setdefault(reference["path"], reference["state"])
                != reference["state"]
            ):
                _fail(
                    "semantic-violation",
                    "publication path has conflicting state snapshots",
                )
        if item["decision"] == "private-only":
            if item["required"]:
                _fail(
                    "semantic-violation", "required publication cannot be private-only"
                )
            if item["target_path"] is not None or item["candidate_ref"] is not None:
                _fail(
                    "semantic-violation",
                    "private-only items must keep target_path and candidate_ref null",
                )
        elif item["target_path"] is not None:
            targets.append(item["target_path"])
    if _paths_overlap(targets):
        _fail(
            "semantic-violation",
            "publication target paths overlap lexically (parent/child)",
        )


def _check_reference_states(references: Iterable[Mapping[str, Any]]) -> None:
    states: dict[str, Any] = {}
    for reference in references:
        if (
            states.setdefault(reference["path"], reference["state"])
            != reference["state"]
        ):
            _fail("semantic-violation", "one referenced path has conflicting states")


def _check_nested_reference_paths(references: Iterable[Mapping[str, Any]]) -> None:
    records = list(references)
    for index, reference in enumerate(records):
        for other in records[index + 1 :]:
            contains = _path_contains(reference["path"], other["path"])
            contained = _path_contains(other["path"], reference["path"])
            if contains and contained:
                if reference["state"] != other["state"]:
                    _fail(
                        "semantic-violation",
                        "one report resource has conflicting states",
                    )
            elif contains or contained:
                _fail(
                    "semantic-violation",
                    "deployment report references overlap (parent/child)",
                )


def _check_operation_resources(records: Iterable[Mapping[str, Any]]) -> None:
    owners: dict[str, tuple[str, str | None]] = {}
    for record in records:
        owner = (record["resource_id"], record.get("phase"))
        for op_id in record["operation_ids"]:
            if owners.setdefault(op_id, owner) != owner:
                _fail(
                    "semantic-violation",
                    "one operation is claimed by different resources or phases",
                )


def _check_operation_ids(operation: Mapping[str, Any]) -> None:
    if operation["resource_id"] != resource_id(
        operation["owner_kind"], operation["target"]
    ):
        _fail(
            "id-mismatch",
            "operation resource_id does not match the canonical owner/target digest",
            exit_code=3,
        )
    if operation["operation_id"] != operation_id(
        operation["phase"], operation["resource_id"], operation["selector"]
    ):
        _fail(
            "id-mismatch",
            "operation_id does not match the canonical phase/resource/selector digest",
            exit_code=3,
        )


def _check_operation(operation: Mapping[str, Any]) -> None:
    _check_operation_ids(operation)
    change_kind = operation["change"]["kind"]
    directory = operation["owner_kind"] == "directory"
    if change_kind == "copy-directory" and not directory:
        _fail("semantic-violation", "directory copy requires a directory resource")
    if directory and change_kind in {"copy-file", "ensure-file-block"}:
        _fail("semantic-violation", "file changes cannot target a directory resource")
    if change_kind in {"build-graft", "configure-graft"}:
        if operation["phase"] != "deploy":
            _fail("semantic-violation", "Graft generation is restricted to deployment")
        if (change_kind == "build-graft") != directory:
            _fail(
                "semantic-violation",
                "Graft generation has an incompatible resource type",
            )
        config_owners = {
            "graft-agents": "markdown",
            "graft-mcp": "toml",
            "graft-hooks": "json",
            "graft-omp-mcp": "json",
        }
        if (
            change_kind == "configure-graft"
            and config_owners.get(operation["selector"]) != operation["owner_kind"]
        ):
            _fail("semantic-violation", "unknown Graft configuration selector or type")
        if operation["change"]["source_ref"] != {
            "path": str(GRAFT_BUILD_POLICY_PATH),
            "state": {"type": "file", "checksum": GRAFT_BUILD_POLICY_SHA256},
        }:
            _fail(
                "semantic-violation", "Graft builds require the installed pinned policy"
            )
        if operation["ownership"] != {
            "kind": "template-source",
            "reference": operation["change"]["source_ref"],
        }:
            _fail(
                "semantic-violation", "Graft builds must bind their exact fixed policy"
            )
    if change_kind == "migrate-developer":
        if (
            operation["phase"] != "apply"
            or operation["owner_kind"] != "file"
            or operation["selector"] != "name"
        ):
            _fail(
                "semantic-violation",
                "developer extraction is a private apply operation",
            )
        if operation["before_requirement"] != {
            "kind": "state",
            "state": {"type": "absent", "checksum": None},
        }:
            _fail(
                "semantic-violation", "developer extraction requires a missing target"
            )
        ownership = operation["ownership"]
        if (
            ownership["kind"] != "config-entry"
            or ownership["key_path"] != ["name"]
            or ownership["reference"] != operation["change"]["source_ref"]
        ):
            _fail(
                "semantic-violation",
                "developer extraction must bind its legacy name source",
            )
    if operation["selector"] == "approved-routing-replacement":
        ownership = operation["ownership"]
        if (
            operation["phase"] != "apply"
            or operation["owner_kind"] != "markdown"
            or change_kind != "copy-file"
            or Path(operation["target"]).name != "AGENTS.md"
            or ownership.get("kind") != "approved-candidate"
            or ownership.get("role") not in {"codex-global", "omp-global", "demo-project"}
            or ownership.get("reference") != operation["change"].get("source_ref")
            or not isinstance(ownership.get("approval_ref"), Mapping)
        ):
            _fail(
                "semantic-violation",
                "an approved routing replacement must copy its bound candidate",
            )
    if (directory and operation["selector"] != "whole-resource") or (
        operation["selector"] == "whole-resource"
        and operation["ownership"]["kind"] not in {"template-source", "skill-identity"}
    ):
        _fail(
            "semantic-violation",
            "whole-resource operations require complete resource ownership",
        )
    if operation["dependent_projects"] != sorted(operation["dependent_projects"]):
        _fail("semantic-violation", "operation dependent_projects must be sorted")
    requirement = operation["before_requirement"]
    if requirement["kind"] == "state" and requirement["state"]["type"] != "absent":
        expected = "directory" if directory else "file"
        if requirement["state"]["type"] != expected:
            _fail(
                "semantic-violation",
                "concrete before-state conflicts with the resource owner",
            )
    if requirement["kind"] == "phase-after":
        if requirement["resource_id"] != operation["resource_id"]:
            _fail(
                "semantic-violation",
                "phase-after before_requirement must reference the same resource",
            )
        if _PHASE_ORDER[requirement["phase"]] >= _PHASE_ORDER[operation["phase"]]:
            _fail(
                "semantic-violation",
                "phase-after before_requirement must reference an earlier phase",
            )


def _manifest_operations(payload: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    for project in payload["projects"]:
        yield from project["private_operations"]
    yield from payload["shared_operations"]


def _manifest_input_references(
    payload: Mapping[str, Any],
) -> Iterator[Mapping[str, Any]]:
    for project in payload["projects"]:
        yield from project["sources"]
        no_touch = project.get("agents_no_touch")
        if no_touch is not None:
            yield no_touch["target"]
            yield no_touch["template"]
    deployment = payload["deployment"]
    if deployment is not None:
        yield from deployment["inputs"]
    for item in payload["publication_decisions"]["items"]:
        yield from item["sources"]
        if item["candidate_ref"] is not None:
            yield item["candidate_ref"]
    for operation in _manifest_operations(payload):
        source = operation["change"].get("source_ref")
        if source is not None:
            yield source
        yield operation["ownership"]["reference"]
        approval = operation["ownership"].get("approval_ref")
        if approval is not None:
            yield approval


def _manifest_initial_snapshots(
    payload: Mapping[str, Any],
) -> Iterator[Mapping[str, Any]]:
    yield from _manifest_input_references(payload)
    for operation in _manifest_operations(payload):
        requirement = operation["before_requirement"]
        if requirement["kind"] == "state":
            yield {"path": operation["target"], "state": requirement["state"]}


def _check_publication_links(
    payload: Mapping[str, Any],
    apply_results: Mapping[str, Any] | None = None,
) -> None:
    candidates = {
        item["target_path"]: item["candidate_ref"]
        for item in payload["publication_decisions"]["items"]
        if item["decision"] != "private-only"
    }
    matched: set[str] = set()
    for operation in _manifest_operations(payload):
        if operation["phase"] != "apply":
            continue
        candidate = candidates.get(operation["target"])
        if candidate is None:
            continue
        expected = (
            "copy-directory"
            if candidate["state"]["type"] == "directory"
            else "copy-file"
        )
        change = operation["change"]
        if change["kind"] != expected or change["source_ref"] != candidate:
            _fail(
                "semantic-violation",
                "publication operation differs from its approved candidate",
            )
        matched.add(operation["target"])
        if apply_results is not None:
            result = apply_results.get(operation["resource_id"])
            if (
                result is not None
                and result["status"] == "succeeded"
                and (result["after"] != candidate["state"])
            ):
                _fail(
                    "binding-violation",
                    "published result differs from its approved candidate",
                )
    if matched != candidates.keys():
        _fail(
            "semantic-violation", "approved publication is missing its apply operation"
        )


def _check_operation_group(operations: list[Mapping[str, Any]]) -> None:
    if len(operations) < 2:
        return
    first = operations[0]
    proof_kind = first["ownership"]["kind"]
    change_kind = first["change"]["kind"]
    claims: list[tuple[str, ...]] = []
    for operation in operations:
        proof = operation["ownership"]
        if (
            operation["selector"] == "whole-resource"
            or operation["owner_kind"] == "directory"
            or proof["kind"] not in {"config-entry", "managed-marker"}
            or proof["kind"] != proof_kind
            or operation["change"]["kind"] != change_kind
        ):
            _fail("semantic-violation", "resource changes cannot be safely merged")
        if change_kind == "copy-file" and operation["change"] != first["change"]:
            _fail(
                "semantic-violation",
                "resource copy operations disagree on the candidate",
            )
        claim = (
            tuple(proof["key_path"])
            if proof_kind == "config-entry"
            else (proof["marker"],)
        )
        for previous in claims:
            overlap = claim == previous
            if proof_kind == "config-entry":
                length = min(len(claim), len(previous))
                overlap = claim[:length] == previous[:length]
            if overlap:
                _fail("semantic-violation", "resource ownership selectors overlap")
        claims.append(claim)


def _check_manifest_payload(payload: Mapping[str, Any]) -> None:
    projects = payload["projects"]
    roots = [project["root"] for project in projects]
    if _paths_identify_same(roots):
        _fail("semantic-violation", "duplicate project root in manifest")
    root_set = set(roots)
    _check_reference_states(_manifest_initial_snapshots(payload))
    deploy_operations = [
        operation
        for operation in _manifest_operations(payload)
        if operation["phase"] == "deploy"
    ]
    deployment = payload["deployment"]
    if deployment is None:
        if deploy_operations:
            _fail(
                "semantic-violation",
                "deployment operations require an explicit deployment declaration",
            )
    else:
        if not deploy_operations:
            _fail(
                "semantic-violation",
                "a deployment declaration requires declared deployment operations",
            )
        if deployment["mode"] == "init-projects" and any(
            operation in payload["shared_operations"] for operation in deploy_operations
        ):
            _fail(
                "semantic-violation",
                "project-only deployment cannot declare shared operations",
            )
        input_paths = [reference["path"] for reference in deployment["inputs"]]
        if len(set(input_paths)) != len(input_paths):
            _fail(
                "semantic-violation",
                "deployment read-only inputs must not repeat a source",
            )
        operation_targets = {operation["target"] for operation in deploy_operations}
        if any(path in operation_targets for path in input_paths):
            _fail(
                "semantic-violation",
                "deployment read-only inputs cannot own a writable target",
            )
    successor = payload.get("successor")
    followup = payload.get("followup")
    if successor is not None and followup is not None:
        _fail(
            "semantic-violation",
            "a batch cannot bind both a successor and a followup predecessor",
        )
    if followup is not None and deployment is None:
        _fail(
            "semantic-violation",
            "a followup batch requires its declared deployment",
        )
    embedded_results: dict[str, Mapping[str, Any]] = {}
    if successor is not None:
        if deployment is None:
            _fail(
                "semantic-violation",
                "a successor batch requires its declared deployment",
            )
        for result in successor["apply_results"]:
            if (
                result["phase"] != "apply"
                or result["status"] != "succeeded"
                or result["after"] is None
            ):
                _fail(
                    "semantic-violation",
                    "a successor binding requires complete succeeded apply results",
                )
            if result["resource_id"] in embedded_results:
                _fail(
                    "semantic-violation",
                    "a successor binding repeats a resource result",
                )
            embedded_results[result["resource_id"]] = result
    backup_root = payload["backup_root"]
    for root in roots:
        if _path_contains(root, backup_root) or _path_contains(backup_root, root):
            _fail(
                "semantic-violation",
                "backup_root must be outside the selected projects",
            )
    for item in payload["publication_decisions"]["items"]:
        target = item["target_path"]
        if target is not None and not any(
            _path_contains(root, target) and not _path_contains(target, root)
            for root in roots
        ):
            _fail(
                "semantic-violation",
                "publication target must be strictly inside a selected project",
            )
        candidate = item["candidate_ref"]
        if candidate is not None and any(
            _path_contains(root, candidate["path"]) for root in roots
        ):
            _fail(
                "semantic-violation",
                "publication candidate must stay outside project roots",
            )

    candidate_paths = [
        item["candidate_ref"]["path"]
        for item in payload["publication_decisions"]["items"]
        if item["candidate_ref"] is not None
    ]
    publication_targets = [
        item["target_path"]
        for item in payload["publication_decisions"]["items"]
        if item["target_path"] is not None
    ]
    non_apply_protected_paths = [*candidate_paths, *publication_targets]
    seen_operation_ids: set[str] = set()
    resource_owners: dict[str, tuple[str, str | None]] = {}
    target_owners: dict[str, tuple[str, tuple[str, str | None]]] = {}
    phases_by_resource: dict[str, set[str]] = {}
    requirements: dict[tuple[str, str], Mapping[str, Any]] = {}
    operation_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    scope_roots = root_set | {root["path"] for root in payload["shared_roots"]}

    def register(operation: Mapping[str, Any], owner: tuple[str, str | None]) -> None:
        _check_operation(operation)
        target = operation["target"]
        if operation["change"]["kind"] == "migrate-developer":
            if owner[0] != "private" or owner[1] is None:
                _fail(
                    "semantic-violation",
                    "developer extraction cannot own shared resources",
                )
            project_root = Path(owner[1])
            if (
                Path(target) != project_root / ".sbtd/developer"
                or Path(operation["change"]["source_ref"]["path"])
                != project_root / ".trellis/.developer"
            ):
                _fail(
                    "semantic-violation",
                    "developer extraction must stay in its owning project",
                )
        if operation["change"]["kind"] == "build-graft" and (
            owner[0] != "private"
            or owner[1] is None
            or Path(target) != Path(owner[1]) / "graft"
        ):
            _fail(
                "semantic-violation",
                "a Graft build owns only its selected project graph",
            )
        if operation["change"]["kind"] == "configure-graft":
            selector = operation["selector"]
            if selector == "graft-agents":
                if (
                    owner[0] != "private"
                    or owner[1] is None
                    or Path(target) != Path(owner[1]) / "AGENTS.md"
                ):
                    _fail(
                        "semantic-violation",
                        "Graft instructions belong only to the selected project",
                    )
            elif selector == "graft-omp-mcp":
                if owner[0] != "shared" or not any(
                    root["kind"] == "omp-home"
                    and _path_contains(root["path"], target)
                    and Path(target).name == "mcp.json"
                    for root in payload["shared_roots"]
                ):
                    _fail(
                        "semantic-violation",
                        "Graft OMP configuration requires its declared OMP HOME",
                    )
            else:
                name = "config.toml" if selector == "graft-mcp" else "hooks.json"
                if owner[0] != "shared" or not any(
                    root["kind"] == "codex-home"
                    and Path(target) == Path(root["path"]) / name
                    for root in payload["shared_roots"]
                ):
                    _fail(
                        "semantic-violation",
                        "Graft host configuration requires its declared Codex HOME",
                    )
        if any(_path_contains(target, root) for root in scope_roots):
            _fail("semantic-violation", "managed target contains a declared scope root")
        if _path_contains(target, backup_root) or _path_contains(backup_root, target):
            _fail("semantic-violation", "backup_root overlaps a managed target")
        protected_paths = candidate_paths
        if operation["phase"] != "apply":
            protected_paths = non_apply_protected_paths
        if any(
            _path_contains(target, protected) or _path_contains(protected, target)
            for protected in protected_paths
        ):
            _fail(
                "semantic-violation",
                "managed target overlaps a protected publication path",
            )
        identity = (operation["resource_id"], owner)
        if any(
            _path_contains(target, owned_target)
            and _path_contains(owned_target, target)
            and existing != identity
            for owned_target, existing in target_owners.items()
        ):
            _fail(
                "semantic-violation",
                "one target cannot have conflicting resource owners",
            )
        target_owners.setdefault(target, identity)
        rid, phase = operation["resource_id"], operation["phase"]
        phases_by_resource.setdefault(rid, set()).add(phase)
        requirement = operation["before_requirement"]
        if requirements.setdefault((rid, phase), requirement) != requirement:
            _fail(
                "semantic-violation", "resource selectors disagree on the before-state"
            )
        if operation["operation_id"] in seen_operation_ids:
            _fail("semantic-violation", "duplicate operation_id in manifest")
        seen_operation_ids.add(operation["operation_id"])
        existing = resource_owners.setdefault(operation["resource_id"], owner)
        if existing != owner:
            _fail(
                "semantic-violation",
                "resource is owned by more than one project or by both private "
                "and shared operation sets",
            )
        operation_groups.setdefault((rid, phase), []).append(operation)

    for project in projects:
        exclusive_roots = [
            root
            for root in roots
            if root != project["root"] and _path_contains(project["root"], root)
        ]
        exclusive_roots.extend(
            root["path"]
            for root in payload["shared_roots"]
            if _path_contains(project["root"], root["path"])
        )
        for operation in project["private_operations"]:
            if not (
                _path_contains(project["root"], operation["target"])
                and not _path_contains(operation["target"], project["root"])
            ):
                _fail("semantic-violation", "private target must belong to its project")
            if any(
                _path_contains(root, operation["target"]) for root in exclusive_roots
            ):
                _fail(
                    "semantic-violation",
                    "private target belongs to another declared project or shared scope",
                )
            if operation["dependent_projects"] != [project["root"]]:
                _fail(
                    "semantic-violation",
                    "private operation dependent_projects must be exactly the owning project root",
                )
            register(operation, ("private", project["root"]))
    for operation in payload["shared_operations"]:
        register(operation, ("shared", None))
    if _paths_overlap(target_owners):
        _fail("semantic-violation", "managed resource targets overlap")
    for operations in operation_groups.values():
        _check_operation_group(operations)
    for (rid, phase), requirement in requirements.items():
        earlier = [
            prior
            for prior in phases_by_resource[rid]
            if _PHASE_ORDER[prior] < _PHASE_ORDER[phase]
        ]
        if earlier:
            expected = {
                "kind": "phase-after",
                "phase": max(earlier, key=_PHASE_ORDER.__getitem__),
                "resource_id": rid,
            }
            if requirement != expected:
                _fail(
                    "semantic-violation",
                    "resource must follow its latest declared phase",
                )
        elif requirement["kind"] != "state":
            if (
                requirement["kind"] != "phase-after"
                or requirement["phase"] != "apply"
                or embedded_results.get(rid) is None
            ):
                _fail(
                    "semantic-violation",
                    "initial resource phase needs a concrete before-state",
                )

    shared_by_id = {op["operation_id"]: op for op in payload["shared_operations"]}
    referenced: dict[str, list[str]] = {op_id: [] for op_id in shared_by_id}
    for project in projects:
        for op_id in project["shared_operation_ids"]:
            if op_id not in shared_by_id:
                _fail(
                    "semantic-violation",
                    "project references an unknown shared operation_id",
                )
            referenced[op_id].append(project["root"])
    for op_id, operation in shared_by_id.items():
        if operation["dependent_projects"] != sorted(referenced[op_id]):
            _fail(
                "semantic-violation",
                "shared operation dependent_projects do not match the exact reverse "
                "reference set from projects",
            )

    logical_skills_roots: list[str] = []
    for shared_root in payload["shared_roots"]:
        if not set(shared_root["dependent_projects"]) <= root_set:
            _fail(
                "semantic-violation",
                "shared_root dependent_projects must reference declared projects",
            )
        logical_root = shared_root.get("skills_root")
        if shared_root["kind"] == "skills":
            if logical_root is not None:
                _fail(
                    "semantic-violation",
                    "a skills shared root has no separate logical skills root",
                )
            logical_skills_roots.append(shared_root["path"])
        elif logical_root is not None:
            if not _path_contains(
                shared_root["path"], logical_root
            ) or _path_contains(logical_root, shared_root["path"]):
                _fail(
                    "semantic-violation",
                    "shared_root skills_root must stay strictly below its declared root",
                )
            logical_skills_roots.append(logical_root)
    # One plan resolves one logical Skills root; an absorbed location sealed
    # on a covering home root is that same single choice. A second, distinct
    # namespace would let a resealed cleanup target escape its selected root.
    for index, candidate in enumerate(logical_skills_roots):
        for other in logical_skills_roots[:index]:
            if not (
                _path_contains(candidate, other)
                and _path_contains(other, candidate)
            ):
                _fail(
                    "semantic-violation",
                    "shared roots declare competing logical skills roots",
                )
    for operation in payload["shared_operations"]:
        matching_roots = [
            root
            for root in payload["shared_roots"]
            if _path_contains(root["path"], operation["target"])
        ]
        if len(matching_roots) != 1 or not set(operation["dependent_projects"]) <= set(
            matching_roots[0]["dependent_projects"]
        ):
            _fail(
                "semantic-violation",
                "shared target needs one declared root covering its dependencies",
            )
        shared_root = matching_roots[0]["path"]
        if any(
            root != shared_root
            and _path_contains(shared_root, root)
            and _path_contains(root, operation["target"])
            for root in roots
        ):
            _fail(
                "semantic-violation",
                "shared target belongs to a more-specific selected project",
            )
    _check_publication_links(payload)


def _check_original_reference(result: Mapping[str, Any], reference_key: str) -> None:
    before = result["before"]
    reference = result[reference_key]
    if reference is not None and (
        before is None or before["type"] == "absent" or reference["state"] != before
    ):
        _fail(
            "semantic-violation", "original reference must match a known before-state"
        )
    if (
        result["status"] == "succeeded"
        and before["type"] != "absent"
        and reference is None
    ):
        _fail("semantic-violation", "successful write needs its original reference")


def _check_project_dependencies(
    project: Mapping[str, Any], dependencies: list[Mapping[str, Any]]
) -> None:
    severity = {"blocked": 1, "failed": 2}
    if any(
        severity.get(result["status"], 0) > severity.get(project["status"], 0)
        for result in dependencies
    ):
        _fail("semantic-violation", "project status masks a dependent resource failure")


def _parse_timestamp(value: str) -> tuple[datetime, str]:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    fraction = value.partition(".")[2]
    if fraction:
        fraction = fraction[:-1] if value.endswith("Z") else fraction[:-6]
    # Keep leading zeros; trimming trailing zeros makes digit-string ordering
    # exact without imposing datetime's microsecond or Decimal context limits.
    return timestamp.replace(microsecond=0), fraction.rstrip("0")


def _check_temporal(payload: Mapping[str, Any]) -> None:
    if _parse_timestamp(payload["started_at"]) > _parse_timestamp(
        payload["finished_at"]
    ):
        _fail("semantic-violation", "started_at must not be after finished_at")


def _aggregate(
    stage_statuses: list[str],
    priority: tuple[str, ...],
    success: str,
    complete: str | None,
) -> str:
    present = set(stage_statuses)
    for status in priority:
        if status in present:
            return status
    if complete is not None and success not in present:
        return complete
    return success


def _retained_states(payload: Mapping[str, Any]) -> dict[str, Any]:
    observations: dict[str, Any] = {}
    for project in payload["projects"]:
        seen: set[str] = set()
        for asset in project["retained_assets"]:
            path = asset["path"]
            if path in seen:
                _fail("semantic-violation", "duplicate retained asset path")
            seen.add(path)
            if observations.setdefault(path, asset["state"]) != asset["state"]:
                _fail("semantic-violation", "retained asset observations conflict")
    if "retained_assets" in payload:
        summary = {
            asset["path"]: asset["state"] for asset in payload["retained_assets"]
        }
        if len(summary) != len(payload["retained_assets"]) or summary != observations:
            _fail(
                "semantic-violation",
                "batch retained assets differ from project observations",
            )
    return observations


def _check_stage_payload(kind: str, payload: Mapping[str, Any]) -> None:
    phase = _STAGE_RECEIPT_PHASES[kind]
    roots = [project["root"] for project in payload["projects"]]
    root_set = set(roots)
    if _paths_identify_same(roots):
        _fail("semantic-violation", "duplicate project root in stage document")

    groups = [payload["shared_results"]]
    groups.extend(project["private_results"] for project in payload["projects"])
    _check_operation_resources(result for results in groups for result in results)
    if kind == "deployment_evidence":
        report_refs = [
            reference
            for project in payload["projects"]
            for reference in project["report_refs"]
        ]
        _check_nested_reference_paths(report_refs)
        _check_reference_states(report_refs)
        reconciliation = payload.get("reconciliation")
        if reconciliation is not None:
            cited_paths = [
                reconciliation["manifest_ref"]["path"],
                reconciliation["apply_receipt_ref"]["path"],
                reconciliation["missing_deployment_evidence"]["path"],
            ]
            if _paths_identify_same(cited_paths):
                _fail(
                    "semantic-violation",
                    "reconciliation inputs and the missing-evidence path must be distinct",
                )
    shared_ids: set[str] = set()
    for result in payload["shared_results"]:
        if result["phase"] != phase:
            _fail("semantic-violation", f"{kind} results must record phase {phase}")
        if result["resource_id"] in shared_ids:
            _fail("semantic-violation", "duplicate shared result for one resource")
        shared_ids.add(result["resource_id"])
        if not set(result["dependent_projects"]) <= root_set:
            _fail(
                "semantic-violation", "shared result references an undeclared project"
            )
        _check_original_reference(result, "backup_ref")
    seen_private: set[str] = set()
    for project in payload["projects"]:
        for result in project["private_results"]:
            if result["phase"] != phase:
                _fail("semantic-violation", f"{kind} results must record phase {phase}")
            if result["resource_id"] in seen_private:
                _fail("semantic-violation", "duplicate private result for one resource")
            seen_private.add(result["resource_id"])
            if result["resource_id"] in shared_ids:
                _fail("semantic-violation", "resource is both private and shared")
            if result["dependent_projects"] != [project["root"]]:
                _fail(
                    "semantic-violation",
                    "private result dependencies differ from its owner",
                )
            _check_original_reference(result, "backup_ref")
        dependencies = [
            *project["private_results"],
            *(
                result
                for result in payload["shared_results"]
                if project["root"] in result["dependent_projects"]
            ),
        ]
        _check_project_dependencies(project, dependencies)

    _check_temporal(payload)
    statuses = [project["status"] for project in payload["projects"]]
    if kind == "apply_receipt":
        expected = _aggregate(
            statuses, ("failed", "blocked"), "applied", "already-complete"
        )
    elif kind == "cleanup_receipt":
        upgrade = payload.get("upgrade_context")
        if upgrade is not None:
            references = [
                upgrade[key]
                for key in ("plan_ref", "receipt_ref", "current_package", "previous_package")
            ]
            # Historical pins remain reportable after a live alias drifts.
            # The native upgrade consumer checks physical path safety.
            paths = [reference["path"] for reference in references]
            if len(paths) != len(set(paths)):
                _fail("semantic-violation", "cleanup upgrade references must be distinct")
            _check_reference_states(references)
        _retained_states(payload)
        expected = _aggregate(
            statuses, ("failed", "blocked"), "cleaned", "already-complete"
        )
    else:
        expected = _aggregate(
            statuses, ("failed", "blocked", "not-verified"), "succeeded", None
        )
    if payload["status"] != expected:
        _fail(
            "semantic-violation",
            "stage status does not match the priority aggregation of project statuses",
        )


def _verification_observations(payload: Mapping[str, Any]) -> dict[str, Any]:
    observations = _retained_states(payload)
    groups = [payload["shared_cleanup_candidates"]]
    groups.extend(project["cleanup_candidates"] for project in payload["projects"])
    _check_operation_resources(candidate for group in groups for candidate in group)
    target_resources: dict[str, str] = {}
    for candidates in groups:
        for candidate in candidates:
            if (
                target_resources.setdefault(
                    candidate["target"], candidate["resource_id"]
                )
                != candidate["resource_id"]
            ):
                _fail(
                    "semantic-violation",
                    "one cleanup target is claimed by multiple resources",
                )
            if (
                observations.setdefault(candidate["target"], candidate["state"])
                != candidate["state"]
            ):
                _fail(
                    "semantic-violation",
                    "verification records conflicting current states",
                )
    return observations


def _check_verification_payload(payload: Mapping[str, Any]) -> None:
    _verification_observations(payload)
    roots = [project["root"] for project in payload["projects"]]
    root_set = set(roots)
    if _paths_identify_same(roots):
        _fail("semantic-violation", "duplicate project root in verification")
    retained_paths = {
        asset["path"]
        for project in payload["projects"]
        for asset in project["retained_assets"]
    }
    project_statuses = {
        project["root"]: project["status"] for project in payload["projects"]
    }

    def check_retention(candidate: Mapping[str, Any]) -> None:
        if not any(
            project_statuses[root] == "verified"
            for root in candidate["dependent_projects"]
        ):
            return
        if any(
            _path_contains(candidate["target"], path)
            or _path_contains(path, candidate["target"])
            for path in retained_paths
        ):
            _fail("semantic-violation", "verified cleanup overlaps a retained asset")

    shared_ids: set[str] = set()
    for candidate in payload["shared_cleanup_candidates"]:
        if candidate["resource_id"] in shared_ids:
            _fail("semantic-violation", "duplicate shared cleanup candidate")
        shared_ids.add(candidate["resource_id"])
        if not set(candidate["dependent_projects"]) <= root_set:
            _fail(
                "semantic-violation",
                "shared candidate references an undeclared project",
            )
        check_retention(candidate)
    seen: set[str] = set()
    for project in payload["projects"]:
        for candidate in project["cleanup_candidates"]:
            if candidate["resource_id"] in seen:
                _fail(
                    "semantic-violation", "duplicate cleanup candidate for one project"
                )
            seen.add(candidate["resource_id"])
            if candidate["resource_id"] in shared_ids:
                _fail("semantic-violation", "candidate is both private and shared")
            if candidate["dependent_projects"] != [project["root"]]:
                _fail(
                    "semantic-violation",
                    "private candidate dependencies differ from its owner",
                )
            check_retention(candidate)
    statuses = [project["status"] for project in payload["projects"]]
    expected = _aggregate(statuses, ("failed", "blocked"), "verified", None)
    if payload["status"] != expected:
        _fail(
            "semantic-violation",
            "verification status does not match the priority aggregation of project statuses",
        )


def _check_recovery_plan_payload(payload: Mapping[str, Any]) -> None:
    if payload["status"] == "blocked" and not payload["conflicts"]:
        _fail("semantic-violation", "a blocked recovery plan must record its conflicts")
    if payload["status"] == "planned" and payload["conflicts"]:
        _fail("semantic-violation", "a planned recovery plan cannot record conflicts")

    roots = [project["root"] for project in payload["projects"]]
    root_set = set(roots)
    if _paths_identify_same(roots):
        _fail("semantic-violation", "duplicate project root in recovery plan")

    steps = payload["steps"]
    _check_operation_resources(steps)
    evidence_refs = [
        reference
        for reference in payload["input_evidence"].values()
        if reference is not None
    ]
    backup_refs = [
        step["backup_ref"] for step in steps if step["backup_ref"] is not None
    ]
    _check_reference_states(
        reference for group in (evidence_refs, backup_refs) for reference in group
    )
    target_paths = [entry["target"] for entry in payload["resources"]]
    backup_paths = [reference["path"] for reference in backup_refs]
    evidence_paths = [reference["path"] for reference in evidence_refs]
    if _paths_overlap(target_paths):
        _fail("semantic-violation", "recovery resources share a target")
    if _paths_overlap((*target_paths, *backup_paths, *evidence_paths)):
        _fail("semantic-violation", "recovery targets, backups or evidence overlap")
    for step in steps:
        if step["expected_current"] == step["restore_to"]:
            _fail("semantic-violation", "recovery step must reverse a state transition")
        if payload["input_evidence"][_PHASE_RECEIPTS[step["phase"]]] is None:
            _fail(
                "semantic-violation",
                "recovery step needs a source-stage evidence reference",
            )
        backup = step["backup_ref"]
        target = step["restore_to"]
        if target["type"] == "absent":
            if backup is not None:
                _fail(
                    "semantic-violation", "absent restore target cannot carry a backup"
                )
        elif backup is None or backup["state"] != target:
            _fail(
                "semantic-violation", "restore target needs a matching original backup"
            )
        if step["step_id"] != recovery_step_id(
            payload["manifest_id"], step["phase"], step["resource_id"]
        ):
            _fail(
                "id-mismatch",
                "recovery step_id does not match the canonical digest",
                exit_code=3,
            )
    inverse_order = [_INVERSE_PHASE_ORDER[step["phase"]] for step in steps]
    if inverse_order != sorted(inverse_order):
        _fail(
            "semantic-violation",
            "recovery steps must be ordered cleanup, then deploy, then apply",
        )

    positions = {step["step_id"]: index for index, step in enumerate(steps)}
    if len(positions) != len(steps):
        _fail("semantic-violation", "duplicate recovery step_id")
    for index, step in enumerate(steps):
        for dependency in step["depends_on"]:
            if dependency not in positions:
                _fail(
                    "semantic-violation", "recovery step depends on an unknown step_id"
                )
            if positions[dependency] >= index:
                _fail(
                    "semantic-violation",
                    "recovery step dependencies must precede the step in inverse order",
                )

    by_resource: dict[str, list[Mapping[str, Any]]] = {}
    for step in steps:
        by_resource.setdefault(step["resource_id"], []).append(step)
    for resource, group in by_resource.items():
        phases = [step["phase"] for step in group]
        if len(set(phases)) != len(phases):
            _fail(
                "semantic-violation",
                "multiple recovery steps for one resource and phase",
            )
        for index in range(1, len(group)):
            current = group[index - 1]
            following = group[index]
            if current["restore_to"] != following["expected_current"]:
                _fail(
                    "semantic-violation",
                    "recovery state chain is broken: restore_to must equal the next "
                    "step's expected_current for the same resource",
                )
            if current["step_id"] not in following["depends_on"]:
                _fail(
                    "semantic-violation",
                    "recovery step must depend on the earlier inverse step of the same resource",
                )

    resources = payload["resources"]
    _check_operation_resources(resources)
    for entry in resources:
        if (
            payload["status"] == "planned"
            and not set(entry["dependent_projects"]) <= root_set
        ):
            _fail("semantic-violation", "planned recovery omits a dependent project")
        if entry["resource_id"] != resource_id(entry["owner_kind"], entry["target"]):
            _fail(
                "id-mismatch",
                "recovery resource identity differs from its owner and target",
                exit_code=3,
            )
        expected = "directory" if entry["owner_kind"] == "directory" else "file"
        if entry["state"]["type"] not in {"absent", expected}:
            _fail("semantic-violation", "recovery snapshot has the wrong resource type")
    resource_ids = [entry["resource_id"] for entry in resources]
    if len(set(resource_ids)) != len(resource_ids):
        _fail("semantic-violation", "duplicate resource entry in recovery plan")
    resource_by_id = {entry["resource_id"]: entry for entry in resources}
    for resource, group in by_resource.items():
        entry = resource_by_id.get(resource)
        if entry is None:
            _fail(
                "semantic-violation", "recovery step references an undeclared resource"
            )
        if entry["state"] != group[0]["expected_current"]:
            _fail(
                "semantic-violation",
                "resource snapshot differs from its first inverse step",
            )
        declared_ops = sorted(op for step in group for op in step["operation_ids"])
        if sorted(entry["operation_ids"]) != declared_ops:
            _fail(
                "semantic-violation",
                "recovery resource operation_ids do not match its steps",
            )
        for step in group:
            expected = "directory" if entry["owner_kind"] == "directory" else "file"
            if any(
                step[field]["type"] not in {"absent", expected}
                for field in ("expected_current", "restore_to")
            ):
                _fail("semantic-violation", "recovery step has the wrong resource type")
            if not set(step["dependent_projects"]) <= set(entry["dependent_projects"]):
                _fail(
                    "semantic-violation",
                    "recovery step dependencies exceed the resource closure",
                )

    step_op_ids = {op for step in steps for op in step["operation_ids"]}
    declared_shared = set(payload["shared_operation_ids"])
    if not declared_shared <= step_op_ids:
        _fail(
            "semantic-violation",
            "recovery plan shared_operation_ids reference unknown operations",
        )
    for step in steps:
        if (
            len(step["dependent_projects"]) > 1
            and not set(step["operation_ids"]) <= declared_shared
        ):
            _fail(
                "semantic-violation",
                "operations of a multi-project resource must be listed in shared_operation_ids",
            )


def _check_recovery_receipt_payload(payload: Mapping[str, Any]) -> None:
    if (
        payload["status"] in {"failed", "blocked"}
        or payload["runtime_readiness"] == "blocked"
    ) and not payload["reason"].strip():
        _fail(
            "semantic-violation",
            "failed recovery or blocked readiness needs an explanation",
        )
    roots = [project["root"] for project in payload["projects"]]
    root_set = set(roots)
    if _paths_identify_same(roots):
        _fail("semantic-violation", "duplicate project root in recovery receipt")
    completed = set(payload["completed_step_ids"])
    pending = set(payload["pending_step_ids"])
    if completed & pending:
        _fail(
            "semantic-violation",
            "recovery step_ids cannot be both completed and pending",
        )

    results = payload["results"]
    _check_operation_resources(results)
    _check_reference_states(payload["report_refs"])
    result_by_step: dict[str, Mapping[str, Any]] = {}
    protections: dict[str, Any] = {}
    for result in results:
        if not set(result["dependent_projects"]) <= root_set:
            _fail("semantic-violation", "recovery result omits a dependent project")
        if result["step_id"] in result_by_step:
            _fail("semantic-violation", "duplicate recovery step result")
        result_by_step[result["step_id"]] = result
        if result["step_id"] != recovery_step_id(
            payload["manifest_id"], result["phase"], result["resource_id"]
        ):
            _fail(
                "id-mismatch",
                "recovery result step identity does not match",
                exit_code=3,
            )
        _check_original_reference(result, "protection_ref")
        protection = result["protection_ref"]
        if (
            protection is not None
            and protections.setdefault(protection["path"], protection["state"])
            != protection["state"]
        ):
            _fail(
                "semantic-violation", "protection path has conflicting original states"
            )
        if result["status"] == "succeeded" and result["step_id"] not in completed:
            _fail("semantic-violation", "a succeeded recovery step must be completed")
    report_paths = [reference["path"] for reference in payload["report_refs"]]
    evidence_paths = [
        reference["path"]
        for reference in payload["input_evidence"].values()
        if reference is not None
    ]
    readonly_paths = [*report_paths, *evidence_paths]
    if _paths_overlap(readonly_paths):
        _fail("semantic-violation", "recovery report or evidence file paths overlap")
    protection_paths = list(protections)
    if any(
        _paths_overlap((path, readonly))
        for path in protection_paths
        for readonly in readonly_paths
    ):
        _fail("semantic-violation", "recovery protection overlaps evidence or reports")
    if _paths_overlap(protection_paths):
        _fail("semantic-violation", "recovery protection objects overlap")
    if not set(result_by_step) <= completed | pending:
        _fail(
            "semantic-violation",
            "recovery step result references a step that is neither completed nor pending",
        )
    for step_id in completed:
        result = result_by_step.get(step_id)
        if result is None or result["status"] != "succeeded":
            _fail(
                "semantic-violation",
                "every completed recovery step needs a succeeded result",
            )

    shared_seen: set[str] = set()
    grouped_steps: set[str] = set()
    for shared in payload["shared_results"]:
        if shared["resource_id"] in shared_seen:
            _fail("semantic-violation", "duplicate shared recovery result")
        shared_seen.add(shared["resource_id"])
        step_dependents: set[str] = set()
        for step_id in shared["step_ids"]:
            result = result_by_step.get(step_id)
            if result is None or result["resource_id"] != shared["resource_id"]:
                _fail(
                    "semantic-violation",
                    "shared recovery result references an unknown or foreign step_id",
                )
            step_dependents.update(result["dependent_projects"])
            grouped_steps.add(step_id)
        if set(shared["dependent_projects"]) != step_dependents:
            _fail(
                "semantic-violation",
                "shared recovery dependencies differ from the recorded step union",
            )
    for result in results:
        if (
            len(result["dependent_projects"]) > 1
            and result["step_id"] not in grouped_steps
        ):
            _fail(
                "semantic-violation",
                "results of a multi-project resource must be grouped in shared_results",
            )
    if payload["status"] in {"restored", "already-complete"} and (
        pending or any(result["status"] != "succeeded" for result in results)
    ):
        _fail(
            "semantic-violation", "successful recovery cannot retain unfinished steps"
        )
    if payload["runtime_readiness"] == "verified" and not payload["report_refs"]:
        _fail(
            "semantic-violation", "verified runtime readiness needs report references"
        )
    for project in payload["projects"]:
        _check_project_dependencies(
            project,
            [
                result
                for result in results
                if project["root"] in result["dependent_projects"]
            ],
        )

    _check_temporal(payload)
    statuses = [project["status"] for project in payload["projects"]]
    expected = _aggregate(
        statuses, ("failed", "blocked"), "restored", "already-complete"
    )
    if payload["status"] != expected:
        _fail(
            "semantic-violation",
            "recovery status does not match the priority aggregation of project statuses",
        )


def _check_envelope(value: Mapping[str, Any], kind: str) -> None:
    mode = value["mode"]
    phase = value["phase"]
    roots = [project["root"] for project in value["projects"]]
    if _paths_identify_same(roots):
        _fail("semantic-violation", "duplicate project root in envelope")
    allowed = _ENVELOPE_PROJECT_STATUSES[(mode, phase)]
    severity = {"blocked": 1, "failed": 2}
    envelope_severity = severity.get(value["status"], 0)
    for project in value["projects"]:
        if project["status"] not in allowed:
            _fail(
                "semantic-violation",
                "envelope project status is not valid for this phase",
            )
        if severity.get(project["status"], 0) > envelope_severity:
            _fail(
                "semantic-violation",
                "envelope status masks a failed or blocked project",
            )

    holder, artifact_key, doc_kind = _ENVELOPE_ARTIFACT[(mode, phase)]
    artifact = value[holder]
    _, generated_id = _kind_info(doc_kind)
    if (
        not artifact
        and generated_id is not None
        and generated_id in value
        and value[generated_id] is not None
    ):
        _fail(
            "semantic-violation",
            "an absent artifact cannot have a generated identifier",
        )
    if artifact:
        document = artifact[artifact_key]
        validate_document(document, doc_kind)
        payload = document["payload"]
        if severity.get(payload.get("status"), 0) > envelope_severity:
            _fail("semantic-violation", "envelope status masks its artifact outcome")
        if envelope_severity == 0 and _artifact_success(value["status"]) != payload.get(
            "status", "planned"
        ):
            _fail(
                "semantic-violation",
                "envelope success variant differs from its artifact",
            )
        if doc_kind == "manifest":
            linked = value["manifest_id"] == document["manifest_id"]
        elif doc_kind == "apply_receipt":
            linked = value["manifest_id"] == payload["manifest_id"]
        elif doc_kind == "deployment_evidence":
            linked = (
                value["manifest_id"] == payload["manifest_id"]
                and value["verification_id"] is None
            )
        elif doc_kind == "verification":
            linked = (
                value["manifest_id"] == payload["manifest_id"]
                and value["verification_id"] == document["verification_id"]
            )
        elif doc_kind == "cleanup_receipt":
            linked = (
                value["manifest_id"] == payload["manifest_id"]
                and value["verification_id"] == payload["verification_id"]
            )
        elif doc_kind == "recovery_plan":
            linked = (
                value["manifest_id"] == payload["manifest_id"]
                and value["plan_id"] == document["plan_id"]
            )
        else:
            linked = (
                value["manifest_id"] == payload["manifest_id"]
                and value["plan_id"] == payload["plan_id"]
                and value["receipt_id"] == document["receipt_id"]
            )
        if not linked:
            _fail(
                "semantic-violation",
                "envelope identifiers do not match the embedded artifact",
            )
        if doc_kind == "deployment_evidence":
            reconciliation = payload.get("reconciliation")
            if value["status"] == "reconciled" and reconciliation is None:
                _fail(
                    "semantic-violation",
                    "a reconciled envelope must embed current-state reconciliation evidence",
                )
            output_path = artifact.get("deployment_evidence_path")
            if reconciliation is not None and output_path is not None:
                cited = [
                    reconciliation["manifest_ref"]["path"],
                    reconciliation["apply_receipt_ref"]["path"],
                    reconciliation["missing_deployment_evidence"]["path"],
                ]
                if any(_publication_paths_overlap(output_path, path) for path in cited):
                    _fail(
                        "semantic-violation",
                        "reconcile output path identifies a cited reconciliation input",
                    )
        artifact_roots = sorted(project["root"] for project in payload["projects"])
        if sorted(roots) != artifact_roots:
            _fail(
                "semantic-violation",
                "envelope project scope does not match the embedded artifact scope",
            )
        summaries = {project["root"]: project for project in value["projects"]}
        for project in payload["projects"]:
            summary = summaries[project["root"]]
            if (
                project.get("status") is not None
                and severity.get(summary["status"], 0) == 0
                and _artifact_success(summary["status"]) != project["status"]
            ):
                _fail(
                    "semantic-violation", "project summary changed the success variant"
                )
            if severity.get(project.get("status"), 0) > severity.get(
                summary["status"], 0
            ):
                _fail(
                    "semantic-violation", "project summary masks the artifact's outcome"
                )

    if value["status"] in ("blocked", "failed") and (
        not value["reason"].strip() or not value["nextStep"].strip()
    ):
        _fail(
            "semantic-violation",
            "blocked or failed envelopes must carry an explanatory reason and nextStep",
        )


# ---------------------------------------------------------------------------
# Document validation entry points
# ---------------------------------------------------------------------------


def _kind_info(kind: Any) -> tuple[str, str | None]:
    if not isinstance(kind, str) or kind not in _DOCUMENT_KINDS:
        _fail("unknown-kind", "unknown contract document kind")
    return _DOCUMENT_KINDS[kind]


def validate_document(value: Any, kind: str) -> Any:
    """Schema, semantic-invariant and canonical-ID validation for one document."""
    def_name, id_key = _kind_info(kind)
    if not isinstance(value, dict):
        _fail("unexpected-type", f"{kind} document must be a JSON object")
    _check_json_safe(value)
    _schema_validate(value, def_name, kind)
    record = value.get("payload", value)
    if kind in {"recovery_plan", "recovery_receipt"}:
        evidence_paths = [
            reference["path"]
            for reference in record["input_evidence"].values()
            if reference is not None
        ]
        if _paths_overlap(evidence_paths):
            _fail("semantic-violation", "input evidence file paths overlap")
    if kind in _CUMULATIVE_KINDS:
        _, previous_key = _CUMULATIVE_KINDS[kind]
        if record[previous_key] is None and (
            record["status"] == "already-complete"
            or any(
                project["status"] == "already-complete"
                for project in record["projects"]
            )
        ):
            _fail("semantic-violation", "already-complete needs a predecessor identity")
    for project in record.get("projects", []):
        if project.get("status") in {"failed", "blocked"} and (
            not project["reason"].strip() or not project["nextStep"].strip()
        ):
            _fail(
                "semantic-violation",
                "failed or blocked projects need a reason and nextStep",
            )
    if kind == "publication_decisions":
        _check_publication_items(value["items"])
    elif kind == "manifest":
        _check_publication_items(value["payload"]["publication_decisions"]["items"])
        _check_manifest_payload(value["payload"])
    elif kind in _STAGE_RECEIPT_PHASES:
        _check_stage_payload(kind, value["payload"])
    elif kind == "verification":
        _check_verification_payload(value["payload"])
    elif kind == "recovery_plan":
        _check_recovery_plan_payload(value["payload"])
    elif kind == "recovery_receipt":
        _check_recovery_receipt_payload(value["payload"])
    else:
        _check_envelope(value, kind)
    if id_key is not None and value[id_key] != _digest(value["payload"]):
        _fail(
            "id-mismatch",
            f"{kind} id does not match the canonical payload digest",
            exit_code=3,
        )
    return value


def load_document(raw: bytes | bytearray | str, kind: str) -> Any:
    """Strict UTF-8 JSON decode followed by full contract validation."""
    _kind_info(kind)
    return validate_document(_decode_strict(raw), kind)


def seal_document(kind: str, payload: Any) -> dict[str, Any]:
    """Wrap a payload as {schema_version, payload, <id>} and validate the result."""
    _, id_key = _kind_info(kind)
    if id_key is None:
        _fail("unknown-kind", f"{kind} documents are not sealed with a payload digest")
    document = {
        "schema_version": SCHEMA_VERSION,
        "payload": payload,
        id_key: _digest(payload),
    }
    validate_document(document, kind)
    return document


# ---------------------------------------------------------------------------
# Declared cross-document bindings
# ---------------------------------------------------------------------------


def _declared_resources(
    payload: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, dict[str, set[str]]]],
    dict[str, dict[str, set[str]]],
    dict[str, set[str]],
    dict[str, tuple[str, str]],
]:
    """Index manifest operations.

    Returns (private, shared, shared_dependents, resource_identity) where
    private maps root -> resource_id -> phase -> operation_ids, shared maps
    resource_id -> phase -> operation_ids, shared_dependents maps resource_id
    to the dependent project set, and resource_identity maps resource_id to
    (owner_kind, target).
    """
    private: dict[str, dict[str, dict[str, set[str]]]] = {}
    shared: dict[str, dict[str, set[str]]] = {}
    dependents: dict[str, set[str]] = {}
    identity: dict[str, tuple[str, str]] = {}

    def note(operation: Mapping[str, Any]) -> None:
        identity.setdefault(
            operation["resource_id"], (operation["owner_kind"], operation["target"])
        )

    for project in payload["projects"]:
        entry = private.setdefault(project["root"], {})
        for operation in project["private_operations"]:
            entry.setdefault(operation["resource_id"], {}).setdefault(
                operation["phase"], set()
            ).add(operation["operation_id"])
            note(operation)
    for operation in payload["shared_operations"]:
        shared.setdefault(operation["resource_id"], {}).setdefault(
            operation["phase"], set()
        ).add(operation["operation_id"])
        dependents.setdefault(operation["resource_id"], set()).update(
            operation["dependent_projects"]
        )
        note(operation)
    return private, shared, dependents, identity


def _check_raw_hash(kind: str, expected: str, raw_documents: Mapping[str, Any]) -> None:
    raw = raw_documents.get(kind)
    if raw is None:
        return
    if _raw_digest(raw) != expected:
        _fail(
            "binding-violation",
            f"{kind} raw bytes do not match the declared content digest",
            exit_code=3,
        )


def _immutable_stage_references(
    payload: Mapping[str, Any],
) -> Iterator[Mapping[str, Any]]:
    for project in payload["projects"]:
        yield from project.get("report_refs", ())
    groups = chain(
        (payload["shared_results"],),
        (project["private_results"] for project in payload["projects"]),
    )
    for results in groups:
        for result in results:
            if result["backup_ref"] is not None:
                yield result["backup_ref"]
    reconciliation = payload.get("reconciliation")
    if reconciliation is not None:
        # The cited missing historical receipt is a stage-cited snapshot too:
        # it stays reserved even though its state is exactly absent. The
        # manifest/apply input refs are not stage-produced artifacts and are
        # deliberately not yielded here.
        yield reconciliation["missing_deployment_evidence"]


def _source_object_references(
    kind: str, payload: Mapping[str, Any]
) -> Iterator[Mapping[str, Any]]:
    if kind == "manifest":
        yield from _manifest_input_references(payload)
        return
    if kind in _STAGE_RECEIPT_PHASES:
        yield from _immutable_stage_references(payload)
    for project in payload["projects"]:
        yield from project.get("retained_assets", ())


def _bind_input_evidence(
    input_evidence: Mapping[str, Any],
    raw_documents: Mapping[str, Any],
    documents: Mapping[str, Any],
) -> None:
    protected_paths = {
        reference["path"]
        for kind, document in documents.items()
        if kind in _STAGE_RECEIPT_PHASES
        for reference in _immutable_stage_references(document["payload"])
    }
    manifest = documents.get("manifest")
    if manifest is not None:
        protected_paths.update(
            reference["path"]
            for reference in _manifest_input_references(manifest["payload"])
        )
    for key, reference in input_evidence.items():
        raw = raw_documents.get(key)
        if raw is not None:
            if reference is None:
                _fail(
                    "binding-violation",
                    "raw evidence was supplied for a slot declared null",
                )
            if reference["state"]["checksum"] != _raw_digest(raw):
                _fail(
                    "binding-violation",
                    "input evidence file digest does not match the supplied raw bytes",
                    exit_code=3,
                )
        if reference is None:
            continue
        source = documents.get(key)
        nested_refs = (
            _source_object_references(key, source["payload"])
            if source is not None
            else ()
        )
        if any(
            _path_contains(reference["path"], path)
            or _path_contains(path, reference["path"])
            for path in chain(
                protected_paths, (nested["path"] for nested in nested_refs)
            )
        ):
            _fail(
                "binding-violation",
                "evidence file overlaps a protected object in supplied evidence",
            )


def _bind_stage_report_scope(
    manifest_payload: Mapping[str, Any], supplied: Mapping[str, Any]
) -> None:
    protected = {
        reference["path"] for reference in _manifest_input_references(manifest_payload)
    }
    protected.update(
        operation["target"] for operation in _manifest_operations(manifest_payload)
    )
    for kind in _STAGE_RECEIPT_PHASES:
        document = supplied.get(kind)
        if document is None:
            continue
        for project in document["payload"]["projects"]:
            for reference in project.get("report_refs", ()):
                if any(
                    _path_contains(reference["path"], protected_path)
                    or _path_contains(protected_path, reference["path"])
                    for protected_path in protected
                ):
                    _fail(
                        "binding-violation",
                        "a stage report reference overlaps a manifest-managed path",
                    )


def _expected_before(
    requirement: Mapping[str, Any],
    stage_results: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    if requirement["kind"] == "state":
        return requirement["state"]
    if requirement["phase"] not in stage_results:
        return None
    predecessor = stage_results[requirement["phase"]].get(requirement["resource_id"])
    if predecessor is None or predecessor["after"] is None:
        _fail(
            "binding-violation",
            "supplied predecessor does not prove the required state",
        )
    return predecessor["after"]


def resolution_stage_results(
    manifest_payload: Mapping[str, Any],
    stage_results: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    """Overlay a successor binding's embedded predecessor apply results.

    The overlay serves before-requirement resolution only; receipt-derived
    stage results stay authoritative for enumeration, state binding and
    backup overlap checks. The batch's own results win over embedded ones.
    """
    successor = manifest_payload.get("successor")
    if successor is None:
        return stage_results
    overlay = {phase: dict(results) for phase, results in stage_results.items()}
    embedded = overlay.setdefault("apply", {})
    for result in successor["apply_results"]:
        embedded.setdefault(result["resource_id"], result)
    return overlay


def _bind_stage_states(
    requirements: Mapping[tuple[str, str], Mapping[str, Any]],
    stage_results: Mapping[str, Mapping[str, Any]],
    resolution: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    resolution = stage_results if resolution is None else resolution
    for phase, results in stage_results.items():
        for rid, result in results.items():
            if result["before"] is None:
                continue
            expected = _expected_before(requirements[(phase, rid)], resolution)
            if expected is not None and result["before"] != expected:
                _fail(
                    "binding-violation",
                    "result before-state differs from its declared requirement",
                )


def _bind_success_gate(
    predecessor: Mapping[str, Any] | None, allowed: set[str]
) -> None:
    if predecessor is not None and predecessor["payload"]["status"] not in allowed:
        _fail(
            "binding-violation", "supplied predecessor did not pass the required phase"
        )


def _bind_resource_states_and_backups(
    manifest_payload: Mapping[str, Any],
    stage_results: Mapping[str, Mapping[str, Any]],
    source_documents: Mapping[str, Any],
) -> None:
    operations = {
        (operation["phase"], operation["resource_id"]): operation
        for operation in _manifest_operations(manifest_payload)
    }
    backups: dict[str, Any] = {}
    source_paths = {
        reference["path"] for reference in _manifest_input_references(manifest_payload)
    }
    source_paths.update(
        reference["path"]
        for kind, document in source_documents.items()
        if kind in _STAGE_RECEIPT_PHASES
        for project in document["payload"]["projects"]
        for reference in project.get("report_refs", ())
    )
    for phase, results in stage_results.items():
        for rid, result in results.items():
            backup = result["backup_ref"]
            if backup is not None:
                path = backup["path"]
                if any(
                    _path_contains(path, source) or _path_contains(source, path)
                    for source in source_paths
                ):
                    _fail(
                        "binding-violation",
                        "original backup overlaps a retained source",
                    )
                if _path_contains(
                    path, manifest_payload["backup_root"]
                ) or not _path_contains(manifest_payload["backup_root"], path):
                    _fail(
                        "binding-violation",
                        "original backup must be below the declared backup root",
                    )
                if backups.setdefault(path, backup["state"]) != backup["state"]:
                    _fail(
                        "binding-violation",
                        "backup path has conflicting original states",
                    )
            if result["status"] != "succeeded":
                continue
            operation = operations[(phase, rid)]
            expected = "directory" if operation["owner_kind"] == "directory" else "file"
            if result["before"]["type"] not in {"absent", expected}:
                _fail("binding-violation", "successful before-state has the wrong type")
            if operation["change"]["kind"] in {"copy-file", "copy-directory"} and (
                result["after"] != operation["change"]["source_ref"]["state"]
            ):
                _fail("binding-violation", "successful copy differs from its source")
            if operation["change"]["kind"] == "migrate-developer":
                content = f"name={operation['change']['name']}\n".encode()
                expected_identity = {
                    "type": "file",
                    "checksum": hashlib.sha256(content).hexdigest(),
                }
                if result["after"] != expected_identity:
                    _fail(
                        "binding-violation",
                        "developer extraction differs from its declared name",
                    )
            observed = result["after"]["type"]
            removed = operation["change"]["kind"] == "remove" and observed == "absent"
            kept_absent = (
                operation["change"]["kind"] == "configure-graft"
                and operation["selector"] == "graft-omp-mcp"
                and (manifest_payload.get("deployment") or {}).get("platform") == "omp"
                and result["before"]["type"] == "absent"
                and observed == "absent"
            )
            if (
                operation["change"]["kind"] == "remove"
                and operation["selector"] == "whole-resource"
                and not removed
            ):
                _fail(
                    "binding-violation",
                    "whole-resource removal must leave the resource absent",
                )
            if not removed and not kept_absent and observed != expected:
                _fail(
                    "binding-violation", "successful result has the wrong resource type"
                )
    if _paths_overlap(backups):
        _fail("binding-violation", "original backup objects overlap")


def _bind_stage_receipt(
    manifest_payload: Mapping[str, Any], document: Mapping[str, Any], phase: str
) -> None:
    private, shared, _, _ = _declared_resources(manifest_payload)
    payload = document["payload"]
    manifest_projects = {
        project["root"]: project for project in manifest_payload["projects"]
    }
    if {project["root"] for project in payload["projects"]} != set(manifest_projects):
        _fail(
            "binding-violation",
            "stage document project scope differs from the manifest",
        )

    shared_phase = {
        rid: phases[phase] for rid, phases in shared.items() if phase in phases
    }
    phase_operation_ids = {
        operation_id
        for operations in shared_phase.values()
        for operation_id in operations
    }
    shared_operations = {
        operation["operation_id"]: operation
        for operation in manifest_payload["shared_operations"]
    }
    phase_dependents: dict[str, set[str]] = {}
    for operation in manifest_payload["shared_operations"]:
        if operation["phase"] == phase:
            phase_dependents.setdefault(operation["resource_id"], set()).update(
                operation["dependent_projects"]
            )

    observed_shared: dict[str, set[str]] = {}
    for result in payload["shared_results"]:
        rid = result["resource_id"]
        if rid not in shared_phase:
            _fail("binding-violation", "shared result is not declared for this phase")
        if set(result["operation_ids"]) != shared_phase[rid]:
            _fail(
                "binding-violation",
                "shared result operation_ids differ from the manifest",
            )
        if set(result["dependent_projects"]) != phase_dependents[rid]:
            _fail(
                "binding-violation", "shared result dependencies differ from this phase"
            )
        for op_id in result["operation_ids"]:
            for root in shared_operations[op_id]["dependent_projects"]:
                observed_shared.setdefault(root, set()).add(op_id)

    for project in payload["projects"]:
        root = project["root"]
        declared = {
            rid: phases[phase]
            for rid, phases in private.get(root, {}).items()
            if phase in phases
        }
        seen: dict[str, Mapping[str, Any]] = {}
        for result in project["private_results"]:
            rid = result["resource_id"]
            if rid not in declared:
                _fail(
                    "binding-violation",
                    "result references a resource not declared for this project and phase",
                )
            if set(result["operation_ids"]) != declared[rid]:
                _fail(
                    "binding-violation",
                    "private result operation_ids differ from the manifest",
                )
            if set(result["dependent_projects"]) != {root}:
                _fail(
                    "binding-violation",
                    "private result dependencies differ from its project",
                )
            seen[rid] = result

        references = set(project["shared_operation_ids"])
        if references != observed_shared.get(root, set()):
            _fail(
                "binding-violation",
                "project references do not match observed shared results",
            )
        completed = project["status"] in _STAGE_SUCCESS_STATUSES[phase] or (
            phase == "deploy" and project["status"] == "not-verified"
        )
        if not completed:
            continue
        if any(
            project[field] != manifest_projects[root][field]
            for field in ("source_ref", "head")
        ):
            _fail(
                "binding-violation",
                "completed project revision differs from its manifest",
            )
        expected_shared = (
            set(manifest_projects[root]["shared_operation_ids"]) & phase_operation_ids
        )
        if references != expected_shared:
            _fail(
                "binding-violation",
                "completed project is missing a declared shared result",
            )
        for rid in declared:
            result = seen.get(rid)
            if result is None or result["status"] != "succeeded":
                _fail(
                    "binding-violation",
                    "a completed project must record every declared private resource",
                )


def _bind_reconciliation(
    metadata: Mapping[str, Any],
    raw_documents: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
) -> None:
    """Bind a current-state reconciliation record to its cited input bytes.

    Reconciled evidence is accepted only against the exact original manifest
    and apply receipt raw bytes its provenance cites; a caller that cannot
    supply both cannot bind the record, and a digest mismatch rejects
    corrupted or substituted inputs.
    """
    if metadata["runtime_versions"]["graft"] != manifest_payload["tool_versions"].get("graft"):
        _fail(
            "binding-violation",
            "reconciliation cannot change the manifest's pinned Graft version",
        )
    proof = metadata.get("observer_lineage")
    if proof is not None and (
        proof["predecessor"] != manifest_payload["tool_versions"]["onboard"]
        or proof["successor"] != metadata["runtime_versions"]["onboard"]
    ):
        _fail(
            "binding-violation",
            "the observer authorization does not bind this manifest and observer",
        )
    for kind, key in (
        ("manifest", "manifest_ref"),
        ("apply_receipt", "apply_receipt_ref"),
    ):
        raw = raw_documents.get(kind)
        if raw is None:
            _fail(
                "binding-violation",
                "reconciled deployment evidence requires the cited raw input bytes",
            )
        if _raw_digest(raw) != metadata[key]["state"]["checksum"]:
            _fail(
                "binding-violation",
                "reconciliation input reference does not match the supplied raw bytes",
                exit_code=3,
            )


def _bind_verification(
    manifest_payload: Mapping[str, Any],
    document: Mapping[str, Any],
    apply_document: Mapping[str, Any] | None,
    deployment_document: Mapping[str, Any] | None,
    requirements: Mapping[tuple[str, str], Mapping[str, Any]],
    stage_results: Mapping[str, Mapping[str, Any]],
    raw_documents: Mapping[str, Any],
) -> None:
    private, shared, dependents, identity = _declared_resources(manifest_payload)
    payload = document["payload"]
    if apply_document is not None and payload["apply_id"] != apply_document["apply_id"]:
        _fail(
            "binding-violation",
            "verification apply_id does not match the apply receipt",
        )
    _check_raw_hash(
        "deployment_evidence", payload["deployment_evidence_hash"], raw_documents
    )
    reconciled = (
        deployment_document is not None
        and deployment_document["payload"].get("reconciliation") is not None
    )
    if payload.get("acceptance_basis") == "current-state":
        if not reconciled:
            _fail(
                "binding-violation",
                "current-state acceptance requires reconciled deployment evidence",
            )
    elif reconciled:
        _fail(
            "binding-violation",
            "reconciled deployment evidence requires a current-state acceptance basis",
        )
    manifest_projects = {
        project["root"]: project for project in manifest_payload["projects"]
    }
    if {project["root"] for project in payload["projects"]} != set(manifest_projects):
        _fail(
            "binding-violation", "verification project scope differs from the manifest"
        )

    def check_candidate(
        candidate: Mapping[str, Any],
        declared_ops: set[str],
        declared_deps: set[str],
        verified: bool,
    ) -> None:
        if set(candidate["operation_ids"]) != declared_ops:
            _fail(
                "binding-violation",
                "cleanup candidate operation_ids do not exactly match the declared set",
            )
        if set(candidate["dependent_projects"]) != declared_deps:
            _fail(
                "binding-violation",
                "cleanup candidate dependent_projects do not match the manifest",
            )
        if candidate["target"] != identity[candidate["resource_id"]][1]:
            _fail(
                "binding-violation",
                "cleanup candidate target does not match the manifest resource",
            )
        if verified:
            owner_kind = identity[candidate["resource_id"]][0]
            expected_type = "directory" if owner_kind == "directory" else "file"
            if candidate["state"]["type"] not in {"absent", expected_type}:
                _fail(
                    "binding-violation",
                    "verified candidate has the wrong resource type",
                )
            expected = _expected_before(
                requirements[("cleanup", candidate["resource_id"])], stage_results
            )
            if expected is not None and candidate["state"] != expected:
                _fail(
                    "binding-violation",
                    "verified candidate differs from its predecessor",
                )

    shared_cleanup = {
        rid: phases["cleanup"] for rid, phases in shared.items() if "cleanup" in phases
    }
    cleanup_dependents: dict[str, set[str]] = {}
    for operation in manifest_payload["shared_operations"]:
        if operation["phase"] == "cleanup":
            cleanup_dependents.setdefault(operation["resource_id"], set()).update(
                operation["dependent_projects"]
            )
    covered_shared: set[str] = set()
    for candidate in payload["shared_cleanup_candidates"]:
        rid = candidate["resource_id"]
        if rid not in shared_cleanup:
            _fail(
                "binding-violation",
                "shared cleanup candidate is not a declared shared cleanup resource",
            )
        verified = any(
            project["status"] == "verified"
            and project["root"] in cleanup_dependents[rid]
            for project in payload["projects"]
        )
        check_candidate(
            candidate, shared_cleanup[rid], cleanup_dependents[rid], verified
        )
        covered_shared.add(rid)

    publications = {
        item["target_path"]: item["candidate_ref"]["state"]
        for item in manifest_payload["publication_decisions"]["items"]
        if item["decision"] != "private-only"
    }
    for project in payload["projects"]:
        root = project["root"]
        if project["status"] == "verified" and any(
            project[field] != manifest_projects[root][field]
            for field in ("source_ref", "head")
        ):
            _fail(
                "binding-violation",
                "verified project revision differs from its manifest",
            )
        declared = {
            rid: phases["cleanup"]
            for rid, phases in private.get(root, {}).items()
            if "cleanup" in phases
        }
        covered: set[str] = set()
        for candidate in project["cleanup_candidates"]:
            rid = candidate["resource_id"]
            if rid not in declared:
                _fail(
                    "binding-violation",
                    "cleanup candidate is not a declared cleanup resource for this project",
                )
            check_candidate(
                candidate, declared[rid], {root}, project["status"] == "verified"
            )
            covered.add(rid)
        if project["status"] == "verified" and covered != set(declared):
            _fail(
                "binding-violation",
                "a verified record must enumerate every declared cleanup candidate",
            )
        if project["status"] == "verified" and any(
            root in cleanup_dependents[rid] and rid not in covered_shared
            for rid in shared_cleanup
        ):
            _fail(
                "binding-violation",
                "verified project is missing a shared cleanup candidate",
            )
        if project["status"] != "verified":
            continue
        retained = {
            asset["path"]: asset["state"] for asset in project["retained_assets"]
        }
        retained_resources = {
            rid: phases
            for rid, phases in private.get(root, {}).items()
            if "cleanup" not in phases or identity[rid][1] in publications
        }
        retained_resources.update(
            {
                rid: phases
                for rid, phases in shared.items()
                if root in dependents[rid]
                and ("cleanup" not in phases or identity[rid][1] in publications)
            }
        )
        for rid, phases in retained_resources.items():
            owner_kind, target = identity[rid]
            state = retained.get(target)
            last_phase = max(
                (phase for phase in phases if phase != "cleanup"),
                key=_PHASE_ORDER.__getitem__,
            )
            result = stage_results.get(last_phase, {}).get(rid)
            if (
                state is None
                and target not in publications
                and result is not None
                and result["status"] == "succeeded"
                and result["after"] == {"type": "absent", "checksum": None}
            ):
                # An explicitly retired route is not a present retained asset.
                # Missing publications and unproven absences still fail below.
                continue
            expected_type = "directory" if owner_kind == "directory" else "file"
            if state is None or state["type"] != expected_type:
                _fail("binding-violation", "verified project omits a retained resource")
            if target in publications and state != publications[target]:
                _fail(
                    "binding-violation",
                    "retained publication differs from its approved candidate",
                )
            if last_phase in stage_results and (
                result is None
                or result["status"] != "succeeded"
                or result["after"] != state
            ):
                _fail(
                    "binding-violation",
                    "retained resource differs from its successful stage result",
                )
    if payload["status"] == "verified" and covered_shared != set(shared_cleanup):
        _fail(
            "binding-violation",
            "a verified record must enumerate every declared shared cleanup candidate",
        )


def _check_recovery_goal(
    manifest_payload: Mapping[str, Any],
    payload: Mapping[str, Any],
    stage_results: Mapping[str, Mapping[str, Any]],
    dependents: Mapping[str, set[str]],
    resource_observations: Mapping[str, Mapping[str, Any]],
) -> None:
    selected = {project["root"] for project in payload["projects"]}
    required_resources = {rid for rid, roots in dependents.items() if roots & selected}
    resources = {entry["resource_id"]: entry for entry in payload["resources"]}
    if set(resources) != required_resources:
        _fail(
            "binding-violation",
            "planned recovery must snapshot every selected resource",
        )
    if any(not dependents[rid] <= selected for rid in required_resources):
        _fail(
            "binding-violation", "planned recovery lacks the shared dependency closure"
        )

    initial: dict[str, Any] = {}
    target_resources: dict[str, str] = {}
    for operation in _manifest_operations(manifest_payload):
        rid = operation["resource_id"]
        target_resources[operation["target"]] = rid
        requirement = operation["before_requirement"]
        if requirement["kind"] == "state":
            initial[rid] = requirement["state"]
        elif manifest_payload.get("successor") is not None:
            resolved = _expected_before(
                requirement, resolution_stage_results(manifest_payload, stage_results)
            )
            if resolved is not None:
                initial[rid] = resolved
    latest = {rid: initial[rid] for rid in required_resources}
    required_steps: set[tuple[str, str]] = set()
    for phase in ("apply", "deploy", "verification", "cleanup"):
        for rid, result in stage_results.get(phase, {}).items():
            if rid not in required_resources:
                continue
            before, after = result["before"], result["after"]
            if before is None or after is None:
                _fail(
                    "binding-violation",
                    "unknown selected write prevents a recovery plan",
                )
            latest[rid] = after
            if before == after:
                continue
            if before["type"] != "absent" and result["backup_ref"] is None:
                _fail(
                    "binding-violation",
                    "changed selected resource lacks its original backup",
                )
            required_steps.add((phase, rid))
        kind = _PHASE_RECEIPTS.get(phase, phase)
        for path, state in resource_observations.get(kind, {}).items():
            rid = target_resources.get(path)
            if rid in required_resources:
                latest[rid] = state

    planned_steps = {(step["phase"], step["resource_id"]) for step in payload["steps"]}
    if planned_steps != required_steps:
        _fail(
            "binding-violation",
            "recovery plan does not cover all proven changed stages",
        )
    terminal = {rid: entry["state"] for rid, entry in resources.items()}
    for step in payload["steps"]:
        terminal[step["resource_id"]] = step["restore_to"]
    for rid, entry in resources.items():
        if entry["state"] != latest[rid]:
            _fail(
                "binding-violation",
                "recovery snapshot differs from the latest proven state",
            )
        if terminal[rid] != initial[rid]:
            _fail(
                "binding-violation", "recovery chain does not reach its pre-apply state"
            )


def _bind_recovery_plan(
    manifest_payload: Mapping[str, Any],
    document: Mapping[str, Any],
    stage_results: Mapping[str, Mapping[str, Any]],
    resource_observations: Mapping[str, Mapping[str, Any]],
) -> None:
    private, shared, dependents, identity = _declared_resources(manifest_payload)
    for root, resources in private.items():
        for resource in resources:
            dependents[resource] = {root}
    payload = document["payload"]
    manifest_roots = {project["root"] for project in manifest_payload["projects"]}
    selected = {project["root"] for project in payload["projects"]}
    if not selected <= manifest_roots:
        _fail(
            "binding-violation",
            "recovery plan selects projects outside the manifest batch",
        )

    all_ops: dict[str, dict[str, set[str]]] = {}
    for phases in private.values():
        for rid, phase_ops in phases.items():
            for phase, op_ids in phase_ops.items():
                all_ops.setdefault(rid, {}).setdefault(phase, set()).update(op_ids)
    for rid, phase_ops in shared.items():
        for phase, op_ids in phase_ops.items():
            all_ops.setdefault(rid, {}).setdefault(phase, set()).update(op_ids)
    phase_dependents: dict[tuple[str, str], set[str]] = {}
    for operation in _manifest_operations(manifest_payload):
        phase_dependents.setdefault(
            (operation["resource_id"], operation["phase"]), set()
        ).update(operation["dependent_projects"])

    for entry in payload["resources"]:
        rid = entry["resource_id"]
        if rid not in all_ops:
            _fail(
                "binding-violation", "recovery resource is not declared in the manifest"
            )
        declared_ops = {op for op_ids in all_ops[rid].values() for op in op_ids}
        if not set(entry["operation_ids"]) <= declared_ops:
            _fail(
                "binding-violation",
                "recovery resource operation_ids do not match the manifest",
            )
        if identity[rid] != (entry["owner_kind"], entry["target"]):
            _fail(
                "binding-violation",
                "recovery resource owner/target does not match the manifest",
            )
        if set(entry["dependent_projects"]) != dependents[rid]:
            _fail(
                "binding-violation",
                "recovery resource dependencies differ from the manifest",
            )
    for step in payload["steps"]:
        rid = step["resource_id"]
        declared = all_ops.get(rid, {}).get(step["phase"])
        if declared is None or set(step["operation_ids"]) != declared:
            _fail(
                "binding-violation",
                "recovery step operation_ids do not match the manifest for its phase",
            )
        if set(step["dependent_projects"]) != phase_dependents[(rid, step["phase"])]:
            _fail(
                "binding-violation",
                "recovery step dependencies differ from its phase operations",
            )
        result = stage_results.get(step["phase"], {}).get(rid)
        if (
            result is None
            or result["before"] is None
            or result["after"] is None
            or step["expected_current"] != result["after"]
            or step["restore_to"] != result["before"]
            or step["backup_ref"] != result["backup_ref"]
        ):
            _fail(
                "binding-violation",
                "recovery inverse lacks a matching supplied stage result",
            )
    expected_shared = {
        operation_id
        for step in payload["steps"]
        if step["resource_id"] in shared
        for operation_id in step["operation_ids"]
    }
    if set(payload["shared_operation_ids"]) != expected_shared:
        _fail("binding-violation", "recovery plan lost declared shared ownership")
    if payload["status"] == "planned":
        _check_recovery_goal(
            manifest_payload, payload, stage_results, dependents, resource_observations
        )


def _bind_recovery_receipt(
    document: Mapping[str, Any],
    plan_document: Mapping[str, Any] | None,
    manifest_payload: Mapping[str, Any],
    source_documents: Mapping[str, Any],
) -> None:
    payload = document["payload"]
    protected_paths = {
        reference["path"] for reference in _manifest_input_references(manifest_payload)
    }
    protected_paths.update(
        operation["target"] for operation in _manifest_operations(manifest_payload)
    )
    protected_paths.update(
        reference["path"]
        for kind, source in source_documents.items()
        if kind in _STAGE_RECEIPT_PHASES or kind == "verification"
        for reference in _source_object_references(kind, source["payload"])
    )
    if plan_document is not None:
        protected_paths.update(
            step["backup_ref"]["path"]
            for step in plan_document["payload"]["steps"]
            if step["backup_ref"] is not None
        )
    output_refs = chain(
        payload["report_refs"],
        (
            result["protection_ref"]
            for result in payload["results"]
            if result["protection_ref"] is not None
        ),
    )
    for output in output_refs:
        if any(
            _path_contains(output["path"], path) or _path_contains(path, output["path"])
            for path in protected_paths
        ):
            _fail("binding-violation", "recovery output overlaps a protected input")
    if plan_document is None:
        return
    if payload["plan_id"] != plan_document["plan_id"]:
        _fail("binding-violation", "recovery receipt plan_id does not match the plan")
    plan_payload = plan_document["payload"]
    _bind_success_gate(plan_document, {"planned"})
    if {project["root"] for project in payload["projects"]} != {
        project["root"] for project in plan_payload["projects"]
    } or payload["input_evidence"] != plan_payload["input_evidence"]:
        _fail(
            "binding-violation",
            "recovery receipt scope or evidence differs from its plan",
        )
    plan_projects = {project["root"]: project for project in plan_payload["projects"]}
    for project in payload["projects"]:
        if project["status"] in {"restored", "already-complete"} and any(
            project[field] != plan_projects[project["root"]][field]
            for field in ("source_ref", "head")
        ):
            _fail(
                "binding-violation",
                "successful recovery revision differs from its plan",
            )
    plan_steps = {step["step_id"]: step for step in plan_document["payload"]["steps"]}
    pending = set(payload["pending_step_ids"])
    for project in payload["projects"]:
        if project["status"] in {"restored", "already-complete"} and any(
            step["step_id"] in pending and project["root"] in step["dependent_projects"]
            for step in plan_steps.values()
        ):
            _fail(
                "binding-violation", "restored project retains dependent pending steps"
            )
    completed = set(payload["completed_step_ids"])
    recorded = completed | pending
    if recorded != set(plan_steps):
        _fail(
            "binding-violation",
            "completed plus pending step_ids must equal the plan's steps",
        )
    if any(
        not set(plan_steps[step_id]["depends_on"]) <= completed for step_id in completed
    ):
        _fail(
            "binding-violation", "completed recovery step has an unfinished dependency"
        )
    for result in payload["results"]:
        step = plan_steps.get(result["step_id"])
        if step is None:
            _fail(
                "binding-violation",
                "recovery result references a step outside the plan",
            )
        if (
            result["resource_id"] != step["resource_id"]
            or result["phase"] != step["phase"]
            or set(result["operation_ids"]) != set(step["operation_ids"])
            or set(result["dependent_projects"]) != set(step["dependent_projects"])
        ):
            _fail(
                "binding-violation",
                "recovery step result does not match the planned step",
            )
        if result["status"] == "succeeded" and (
            result["before"] != step["expected_current"]
            or result["after"] != step["restore_to"]
        ):
            _fail(
                "binding-violation",
                "successful recovery result differs from its planned states",
            )
    shared_operations = set(plan_document["payload"]["shared_operation_ids"])
    expected_groups: dict[str, set[str]] = {}
    for result in payload["results"]:
        if set(result["operation_ids"]) & shared_operations:
            expected_groups.setdefault(result["resource_id"], set()).add(
                result["step_id"]
            )
    actual_groups = {
        result["resource_id"]: set(result["step_ids"])
        for result in payload["shared_results"]
    }
    if actual_groups != expected_groups:
        _fail(
            "binding-violation",
            "recovery results lost declared shared resource grouping",
        )


def _bind_retained_assets(
    manifest_payload: Mapping[str, Any],
    verification: Mapping[str, Any] | None,
    cleanup: Mapping[str, Any],
) -> None:
    declaration = manifest_payload.get("deployment") or {}
    inputs = {item["path"]: item["state"] for item in declaration.get("inputs", ())}
    observed: set[str] = set()
    for item in cleanup["payload"].get("deployment_only_inputs", ()):
        path = item["path"]
        if (
            path in observed
            or inputs.get(path) != item["sealed_state"]
            or item["sealed_state"]["type"] not in {"file", "absent"}
            or item["live_state"]["type"] not in {"file", "absent"}
            or item["sealed_state"] == item["live_state"]
        ):
            _fail("binding-violation", "cleanup input observation differs from its declaration")
        observed.add(path)
    verified = (
        {
            project["root"]: {
                asset["path"]: asset["state"] for asset in project["retained_assets"]
            }
            for project in verification["payload"]["projects"]
        }
        if verification is not None
        else None
    )
    targets = {
        op["resource_id"]: op["target"] for op in _manifest_operations(manifest_payload)
    }
    results = _collect_stage_results(cleanup["payload"]).values()
    after = {targets[result["resource_id"]]: result["after"] for result in results}
    changed_targets = {
        targets[result["resource_id"]]
        for result in results
        if result["status"] == "succeeded" and result["before"] != result["after"]
    }
    for project in cleanup["payload"]["projects"]:
        if project["status"] not in {"cleaned", "already-complete"}:
            continue
        retained = {
            asset["path"]: asset["state"] for asset in project["retained_assets"]
        }
        if verified is not None and retained != verified[project["root"]]:
            _fail(
                "binding-violation", "cleanup retained assets differ from verification"
            )
        if any(
            path in after and after[path] != state for path, state in retained.items()
        ):
            _fail("binding-violation", "cleanup changed an asset declared retained")
        if any(
            _path_contains(target, path) or _path_contains(path, target)
            for target in changed_targets
            for path in retained
        ):
            _fail(
                "binding-violation", "cleanup write overlaps an asset declared retained"
            )


def _bind_declared_hashes(documents: Mapping[str, Any]) -> None:
    declared: dict[str, str] = {}
    apply_ids = {
        document["payload"]["apply_id"]
        for kind, document in documents.items()
        if kind in {"deployment_evidence", "verification", "cleanup_receipt"}
    }
    if "apply_receipt" in documents:
        apply_ids.add(documents["apply_receipt"]["apply_id"])
    if len(apply_ids) > 1:
        _fail("binding-violation", "supplied stages reference different apply runs")

    def note(kind: str, digest: str) -> None:
        if declared.setdefault(kind, digest) != digest:
            _fail(
                "binding-violation",
                "supplied records declare conflicting file digests",
                exit_code=3,
            )

    for kind, document in documents.items():
        payload = document["payload"]
        if kind in {"verification", "cleanup_receipt"}:
            note("deployment_evidence", payload["deployment_evidence_hash"])
        if kind in {"recovery_plan", "recovery_receipt"}:
            for source, reference in payload["input_evidence"].items():
                if reference is not None:
                    note(source, reference["state"]["checksum"])


def _bind_chronology(
    manifest_payload: Mapping[str, Any], documents: Mapping[str, Any]
) -> None:
    created = _parse_timestamp(manifest_payload["created_at"])
    windows: dict[str, tuple[tuple[datetime, str], tuple[datetime, str]]] = {}
    for kind, document in documents.items():
        payload = document["payload"]
        if kind == "verification":
            start = finish = _parse_timestamp(payload["verified_at"])
        elif kind == "recovery_plan":
            start = finish = _parse_timestamp(payload["created_at"])
        else:
            start = _parse_timestamp(payload["started_at"])
            finish = _parse_timestamp(payload["finished_at"])
        if start < created:
            _fail("binding-violation", "bound record predates its manifest")
        windows[kind] = (start, finish)
    for earlier, later in (
        ("apply_receipt", "deployment_evidence"),
        ("apply_receipt", "verification"),
        ("apply_receipt", "cleanup_receipt"),
        ("deployment_evidence", "verification"),
        ("deployment_evidence", "cleanup_receipt"),
        ("verification", "cleanup_receipt"),
        ("verification", "recovery_plan"),
        ("verification", "recovery_receipt"),
        ("recovery_plan", "recovery_receipt"),
    ):
        if (
            earlier in windows
            and later in windows
            and windows[earlier][1] > windows[later][0]
        ):
            _fail(
                "binding-violation", "bound phase predates its prerequisite completion"
            )
    for recovery_kind in ("recovery_plan", "recovery_receipt"):
        if recovery_kind not in windows:
            continue
        if any(
            kind in windows and windows[kind][1] > windows[recovery_kind][0]
            for kind in _STAGE_RECEIPT_PHASES
        ):
            _fail("binding-violation", "recovery predates its supplied source evidence")


def validate_declared_bindings(
    manifest: Any,
    documents: Mapping[str, Any],
    raw_documents: Mapping[str, bytes | bytearray] | None = None,
) -> dict[str, Any]:
    """Validate declared bindings between a manifest and supplied stage documents.

    Only caller-provided objects and raw bytes are checked. A supplied recovery
    plan requires the source stage for each inverse step; other absent kinds
    are not inferred as unexecuted. Deployment evidence carrying current-state
    reconciliation provenance additionally requires the exact raw manifest and
    apply receipt bytes it cites, and a bound verification must expose
    acceptance_basis "current-state" exactly when its deployment evidence is
    reconciled. No filesystem reads take place.
    """
    validate_document(manifest, "manifest")
    manifest_payload = manifest["payload"]
    manifest_id = manifest["manifest_id"]
    if raw_documents is not None and not isinstance(raw_documents, Mapping):
        _fail("unexpected-type", "raw_documents must be a mapping or None")
    raw = dict(raw_documents) if raw_documents is not None else {}

    supplied: dict[str, Any] = {}
    if not isinstance(documents, Mapping):
        _fail("unexpected-type", "documents must be a mapping of kind to document")
    for kind, document in documents.items():
        if kind not in _BINDABLE_KINDS:
            _fail("unknown-kind", "unsupported document kind for declared bindings")
        supplied[kind] = validate_document(document, kind)
    for kind, blob in raw.items():
        if kind not in _RAW_KINDS:
            _fail("unknown-kind", "unsupported raw document kind")
        if not isinstance(blob, (bytes, bytearray)):
            _fail("unexpected-type", "raw documents must be bytes")
        try:
            decoded = load_document(blob, kind)
        except ContractError:
            raise ContractError(
                "binding-violation",
                "supplied raw bytes do not form a valid bound document",
                exit_code=3,
            ) from None
        expected = manifest if kind == "manifest" else supplied.get(kind)
        if expected is not None and decoded != expected:
            _fail(
                "binding-violation",
                "raw bytes describe a different supplied document",
                exit_code=3,
            )
        if kind != "manifest":
            supplied.setdefault(kind, decoded)

    for kind, document in supplied.items():
        if document["payload"]["manifest_id"] != manifest_id:
            _fail("binding-violation", f"{kind} is not bound to the supplied manifest")

    stage_results = {
        phase: {
            result["resource_id"]: result
            for result in _collect_stage_results(supplied[kind]["payload"]).values()
        }
        for kind, phase in _STAGE_RECEIPT_PHASES.items()
        if kind in supplied
    }
    resource_observations: dict[str, Mapping[str, Any]] = {}
    if "verification" in supplied:
        resource_observations["verification"] = _verification_observations(
            supplied["verification"]["payload"]
        )
    if "cleanup_receipt" in supplied:
        resource_observations["cleanup_receipt"] = _retained_states(
            supplied["cleanup_receipt"]["payload"]
        )
    requirements = {
        (op["phase"], op["resource_id"]): op["before_requirement"]
        for project in manifest_payload["projects"]
        for op in project["private_operations"]
    }
    for operation in manifest_payload["shared_operations"]:
        requirements[(operation["phase"], operation["resource_id"])] = operation[
            "before_requirement"
        ]
    _bind_stage_report_scope(manifest_payload, supplied)
    apply_document = supplied.get("apply_receipt")
    if apply_document is not None:
        _bind_stage_receipt(manifest_payload, apply_document, "apply")
    deployment = supplied.get("deployment_evidence")
    if deployment is not None:
        _bind_success_gate(apply_document, {"applied", "already-complete"})
        if apply_document is not None and (
            deployment["payload"]["apply_id"] != apply_document["apply_id"]
        ):
            _fail(
                "binding-violation",
                "deployment evidence apply_id does not match the apply receipt",
            )
        _bind_stage_receipt(manifest_payload, deployment, "deploy")
        reconciliation = deployment["payload"].get("reconciliation")
        if reconciliation is not None:
            _bind_reconciliation(reconciliation, raw, manifest_payload)
    verification = supplied.get("verification")
    if verification is not None:
        _bind_success_gate(apply_document, {"applied", "already-complete"})
        _bind_success_gate(deployment, {"succeeded"})
        _bind_verification(
            manifest_payload,
            verification,
            apply_document,
            deployment,
            requirements,
            stage_results,
            raw,
        )
    cleanup = supplied.get("cleanup_receipt")
    if cleanup is not None:
        _bind_success_gate(apply_document, {"applied", "already-complete"})
        _bind_success_gate(deployment, {"succeeded"})
        _bind_success_gate(verification, {"verified"})
        if verification is not None and (
            cleanup["payload"]["verification_id"] != verification["verification_id"]
        ):
            _fail(
                "binding-violation",
                "cleanup receipt verification_id does not match the verification",
            )
        if apply_document is not None and (
            cleanup["payload"]["apply_id"] != apply_document["apply_id"]
        ):
            _fail(
                "binding-violation",
                "cleanup receipt apply_id does not match the apply receipt",
            )
        _check_raw_hash(
            "deployment_evidence",
            cleanup["payload"]["deployment_evidence_hash"],
            raw,
        )
        _bind_stage_receipt(manifest_payload, cleanup, "cleanup")
        _bind_retained_assets(manifest_payload, verification, cleanup)
    _bind_stage_states(
        requirements,
        stage_results,
        resolution_stage_results(manifest_payload, stage_results),
    )
    _bind_resource_states_and_backups(manifest_payload, stage_results, supplied)
    if "apply" in stage_results:
        _check_publication_links(manifest_payload, stage_results["apply"])
    evidence_documents = {"manifest": manifest, **supplied}
    plan = supplied.get("recovery_plan")
    if plan is not None:
        _bind_recovery_plan(
            manifest_payload, plan, stage_results, resource_observations
        )
        _bind_input_evidence(plan["payload"]["input_evidence"], raw, evidence_documents)
    receipt = supplied.get("recovery_receipt")
    if receipt is not None:
        _bind_recovery_receipt(receipt, plan, manifest_payload, supplied)
        _bind_input_evidence(
            receipt["payload"]["input_evidence"], raw, evidence_documents
        )
    _bind_declared_hashes(supplied)
    _bind_chronology(manifest_payload, supplied)
    return supplied


# ---------------------------------------------------------------------------
# Cumulative receipt preservation
# ---------------------------------------------------------------------------


def _collect_stage_results(payload: Mapping[str, Any]) -> dict[tuple[str, ...], Any]:
    collected: dict[tuple[str, ...], Any] = {}
    for project in payload["projects"]:
        for result in project["private_results"]:
            collected[
                ("private", project["root"], result["phase"], result["resource_id"])
            ] = result
    for result in payload["shared_results"]:
        collected[("shared", result["phase"], result["resource_id"])] = result
    return collected


def _valid_result_transition(
    old: Mapping[str, Any], new: Mapping[str, Any], reference_key: str
) -> bool:
    if (
        old["phase"] != new["phase"]
        or old["resource_id"] != new["resource_id"]
        or set(old["operation_ids"]) != set(new["operation_ids"])
        or set(old["dependent_projects"]) != set(new["dependent_projects"])
    ):
        return False
    if old["status"] == "succeeded" and (
        new["status"] != "succeeded" or new["after"] != old["after"]
    ):
        return False
    if (
        old["status"] != "succeeded"
        and (old["before"] is None or old["after"] != old["before"])
        and new != old
    ):
        return False
    before = old["before"]
    if new["before"] != before:
        return False
    original, replacement = old[reference_key], new[reference_key]
    if original == replacement:
        unprotected_change = (
            original is None
            and before is not None
            and before["type"] != "absent"
            and new["after"] != before
        )
        return not unprotected_change
    # A failed copy may be retried only while the recorded original is untouched.
    if original is not None or replacement is None or before is None:
        return False
    return (
        before["type"] != "absent"
        and old["after"] == before
        and replacement["state"] == before
    )


def _check_cumulative_report_artifacts(
    previous_reports: Iterable[Mapping[str, Any]],
    current_reports: Iterable[Mapping[str, Any]],
    previous_originals: Iterable[Mapping[str, Any] | None],
    current_originals: Iterable[Mapping[str, Any] | None],
) -> None:
    reserved = {reference["path"]: reference["state"] for reference in previous_reports}
    if not reserved:
        return
    for reference in current_reports:
        path = reference["path"]
        if path in reserved and reference["state"] == reserved[path]:
            continue
        if any(
            _path_contains(path, previous) or _path_contains(previous, path)
            for previous in reserved
        ):
            _fail(
                "cumulative-violation",
                "retry report overwrites a previous report artifact",
                exit_code=3,
            )
    existing_originals = {
        (reference["path"], reference["state"]["type"], reference["state"]["checksum"])
        for reference in previous_originals
        if reference is not None
    }
    for reference in current_originals:
        if reference is None:
            continue
        identity = (
            reference["path"],
            reference["state"]["type"],
            reference["state"]["checksum"],
        )
        if identity in existing_originals:
            continue
        if any(
            _path_contains(reference["path"], previous)
            or _path_contains(previous, reference["path"])
            for previous in reserved
        ):
            _fail(
                "cumulative-violation",
                "retry original reference overwrites a previous report artifact",
                exit_code=3,
            )


def validate_cumulative(previous: Any, current: Any, kind: str) -> Any:
    """Prove a retry receipt preserves prior success and original references.

    ``previous=None`` marks a first run: the current document must declare a
    null previous receipt reference. Otherwise the current document must link
    the previous document's ID and carry every previously succeeded result
    forward with its original before/after and backup (or protection) refs.
    Deployment evidence retries must carry their reconciliation provenance
    (or absence of it) forward unchanged, so a retry can never launder a
    current-state observation back into executed-origin evidence or vice
    versa. Report files in the supplied previous record stay reserved even
    when the current report list replaces them with fresh, disjoint report
    references.
    """
    if kind not in _CUMULATIVE_KINDS:
        _fail("unknown-kind", "kind does not support cumulative validation")
    id_key, previous_key = _CUMULATIVE_KINDS[kind]
    validate_document(current, kind)
    if previous is None:
        if current["payload"][previous_key] is not None:
            _fail(
                "cumulative-violation",
                "a first-run document must declare a null previous reference",
                exit_code=3,
            )
        return current
    validate_document(previous, kind)
    if _parse_timestamp(current["payload"]["started_at"]) < _parse_timestamp(
        previous["payload"]["finished_at"]
    ):
        _fail(
            "cumulative-violation", "retry predates its previous attempt", exit_code=3
        )
    if current["payload"][previous_key] != previous[id_key]:
        _fail(
            "cumulative-violation",
            "current document does not reference the supplied previous document",
            exit_code=3,
        )
    if current["payload"]["manifest_id"] != previous["payload"]["manifest_id"]:
        _fail(
            "cumulative-violation",
            "cumulative documents are bound to different manifests",
            exit_code=3,
        )

    binding_fields = {
        "apply_receipt": (),
        "deployment_evidence": ("apply_id",),
        "cleanup_receipt": ("apply_id", "verification_id", "deployment_evidence_hash"),
        "recovery_receipt": ("plan_id", "input_evidence"),
    }[kind]
    if any(
        current["payload"][key] != previous["payload"][key] for key in binding_fields
    ):
        _fail(
            "cumulative-violation",
            "retry changed its bound evidence chain",
            exit_code=3,
        )
    if kind == "deployment_evidence" and (
        current["payload"].get("reconciliation")
        != previous["payload"].get("reconciliation")
    ):
        _fail(
            "cumulative-violation",
            "retry changed its reconciliation provenance",
            exit_code=3,
        )
    if kind == "cleanup_receipt" and (
        current["payload"].get("upgrade_context")
        != previous["payload"].get("upgrade_context")
    ):
        _fail(
            "cumulative-violation",
            "retry changed its cleanup upgrade provenance",
            exit_code=3,
        )
    if {project["root"] for project in current["payload"]["projects"]} != {
        project["root"] for project in previous["payload"]["projects"]
    }:
        _fail("cumulative-violation", "retry changed its project scope", exit_code=3)

    previous_projects = {
        project["root"]: project for project in previous["payload"]["projects"]
    }
    completed_statuses = {"applied", "cleaned", "restored", "already-complete"}
    if current["payload"]["status"] == "already-complete" and (
        previous["payload"]["status"] not in completed_statuses
    ):
        _fail(
            "cumulative-violation",
            "already-complete requires prior phase success",
            exit_code=3,
        )
    for project in current["payload"]["projects"]:
        if project["status"] == "already-complete" and (
            previous_projects[project["root"]]["status"] not in completed_statuses
        ):
            _fail(
                "cumulative-violation",
                "project completion lacks prior success",
                exit_code=3,
            )

    if kind == "recovery_receipt":
        previous_steps = set(previous["payload"]["completed_step_ids"]) | set(
            previous["payload"]["pending_step_ids"]
        )
        current_steps = set(current["payload"]["completed_step_ids"]) | set(
            current["payload"]["pending_step_ids"]
        )
        if previous_steps != current_steps:
            _fail(
                "cumulative-violation",
                "retry changed the recovery step universe",
                exit_code=3,
            )
        previous_results = {
            result["step_id"]: result for result in previous["payload"]["results"]
        }
        current_results = {
            result["step_id"]: result for result in current["payload"]["results"]
        }
        if not set(previous["payload"]["completed_step_ids"]) <= set(
            current["payload"]["completed_step_ids"]
        ):
            _fail(
                "cumulative-violation",
                "previously completed recovery steps are missing from the retry",
                exit_code=3,
            )
        for step_id, old in previous_results.items():
            new = current_results.get(step_id)
            if new is None or not _valid_result_transition(old, new, "protection_ref"):
                _fail(
                    "cumulative-violation",
                    "retry changed preserved recovery identity/state or advanced an unsafe partial write",
                    exit_code=3,
                )
        _check_cumulative_report_artifacts(
            previous["payload"]["report_refs"],
            current["payload"]["report_refs"],
            (result["protection_ref"] for result in previous_results.values()),
            (result["protection_ref"] for result in current_results.values()),
        )
        return current

    previous_results = _collect_stage_results(previous["payload"])
    current_results = _collect_stage_results(current["payload"])
    for key, old in previous_results.items():
        new = current_results.get(key)
        if new is None or not _valid_result_transition(old, new, "backup_ref"):
            _fail(
                "cumulative-violation",
                "retry changed preserved resource identity/state or advanced an unsafe partial write",
                exit_code=3,
            )
    if kind == "deployment_evidence":
        _check_cumulative_report_artifacts(
            (
                reference
                for project in previous["payload"]["projects"]
                for reference in project["report_refs"]
            ),
            (
                reference
                for project in current["payload"]["projects"]
                for reference in project["report_refs"]
            ),
            (result["backup_ref"] for result in previous_results.values()),
            (result["backup_ref"] for result in current_results.values()),
        )
    return current


# ---------------------------------------------------------------------------
# Envelopes, deployment results and the single-JSON writer
# ---------------------------------------------------------------------------


def make_envelope(
    mode: str,
    phase: str,
    status: str,
    projects: list[dict[str, Any]],
    reason: str,
    next_step: str,
    artifact: Any = None,
    identifiers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a migration or recovery phase envelope.

    ``artifact`` is the stage document (for example the manifest for a
    migration plan phase); it is wrapped under the fixed phase key, or the
    holder stays an empty object. For the migration reconcile phase the
    artifact is the complete holder body carrying the bare deployment
    evidence document and its private output path. ``identifiers`` carries
    the honest id fields (null when not applicable).
    """
    if mode not in _ENVELOPE_IDENTIFIER_KEYS:
        _fail("unknown-kind", "mode must be migration or recovery")
    if (mode, phase) not in _ENVELOPE_ARTIFACT:
        _fail("unknown-kind", "phase is not valid for this mode")
    if identifiers is not None and not isinstance(identifiers, Mapping):
        _fail("unexpected-type", "identifiers must be a mapping or None")
    supplied = dict(identifiers) if identifiers is not None else {}
    if not set(supplied) <= _ENVELOPE_IDENTIFIER_KEYS[mode]:
        _fail("unknown-kind", "unexpected identifier field for this mode")
    holder, artifact_key, _ = _ENVELOPE_ARTIFACT[(mode, phase)]
    body: dict[str, Any] = {}
    if artifact is not None:
        if not isinstance(artifact, dict):
            _fail("unexpected-type", "artifact must be a contract document")
        if (mode, phase) == ("migration", "reconcile"):
            body.update(artifact)
        else:
            body[artifact_key] = artifact
    envelope: dict[str, Any] = {
        "mode": mode,
        "phase": phase,
        "status": status,
        "projects": projects,
        "reason": reason,
        "nextStep": next_step,
        holder: body,
    }
    for key in _ENVELOPE_IDENTIFIER_KEYS[mode]:
        envelope[key] = supplied.get(key)
    kind = "migration_envelope" if mode == "migration" else "recovery_envelope"
    return validate_document(envelope, kind)


def validate_deployment_result(value: Any) -> Any:
    """Validate the init deploymentEvidence field: null or {path, evidence}."""
    if value is None:
        return None
    if not isinstance(value, dict):
        _fail("unexpected-type", "deployment result must be null or an object")
    _check_json_safe(value)
    _schema_validate(value, "deployment_result", "deployment_result")
    validate_document(value["evidence"], "deployment_evidence")
    if any(
        _path_contains(value["path"], reference["path"])
        or _path_contains(reference["path"], value["path"])
        or (
            reference["state"]["type"] == "absent"
            and _publication_paths_overlap(value["path"], reference["path"])
        )
        for reference in _immutable_stage_references(value["evidence"]["payload"])
    ):
        _fail(
            "semantic-violation",
            "deployment result path overlaps its embedded evidence references",
        )
    return value


def write_json_response(value: Any, stream: Any = None) -> str:
    """Validate and emit exactly one JSON root object.

    Fixed migration/recovery phase envelopes are fully validated; retired
    top-level Trellis fields are refused rather than silently aliased. Other
    producer payload bodies keep their own runtime-owned semantics. Returns
    the serialized text.
    """
    if not isinstance(value, dict):
        _fail("unexpected-type", "JSON response must be a single root object")
    retired = _RETIRED_TOP_LEVEL_KEYS & set(value)
    if retired:
        _fail(
            "retired-field",
            "response contains a retired top-level Trellis field; use the current "
            "report fields instead",
        )
    mode = value.get("mode")
    if mode == "migration":
        validate_document(value, "migration_envelope")
    elif mode == "recovery":
        validate_document(value, "recovery_envelope")
    else:
        _check_json_safe(value, allow_numbers=True)
    text = canonical_json_bytes(value).decode("utf-8")
    out = sys.stdout if stream is None else stream
    out.write(text + "\n")
    return text

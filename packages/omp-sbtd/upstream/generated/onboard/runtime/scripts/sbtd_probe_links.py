r"""Precise linked Skill target authorization for isolated upgrade probes.

Default probe behavior is unchanged: fixture copies refuse links and never
access a link target. This module implements the only exception — an
explicit, content-bound local authorization for one exact linked Skill.

Phase 1 (``prepare_link_authorization``) requires the operator to supply the
physical target path explicitly. The supplied path is never ``resolve()``d:
the link text is walked component by component with per-component nofollow
lstat proofs (kernel-faithful, so ``..`` collapses never cross a hidden
link), and the supplied physical path must match both lexically and by
device/inode/ctime_ns object identity before any target content is read. The target
must additionally prove its Skill identity — a regular nofollow ``SKILL.md``
whose frontmatter ``name`` equals the logical Skill name (the link's own
basename). The output is a digest-pure, reusable local JSON document binding
the original upgrade plan id, host id, logical Skill path, exact link text,
the link object's own lstat identity, the physical approved directory, the
target object's identity and the whole-tree content digest. It is bound to
content, not to any keypair, and carries no issuance timestamps.

Phase 2 (``validate_link_authorization`` at ``verify`` time and
``materialize_authorized_skill`` inside the isolated probe copy) revalidates
the document against the sealed plan and scope, then re-proves link identity
+ text, target identity and content digest before AND after the safe copy.
The copy itself is the existing nofollow ``backup_reference`` primitive, so a
partial copy is rolled back and the host process is never spawned on any
mismatch. A replaced link object — even one carrying identical link text —
fails on its lstat identity, and a stale artifact is never refreshed: the
operator re-runs the prepare phase instead.

Generic nofollow filesystem policies, install/migration/cleanup link rules
and every old plan/receipt/evidence document are untouched by this module.
"""
from __future__ import annotations

import hashlib
import ntpath
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_migration_files import (
    _canonical,
    _is_reparse,
    _lstat,
    backup_reference,
    directory_snapshot,
    snapshot,
)

__all__ = [
    "AUTHORIZATION_SCHEMA",
    "materialize_authorized_skill",
    "prepare_link_authorization",
    "validate_link_authorization",
]

AUTHORIZATION_SCHEMA = "upgrade-probe-link-authorization"

_HEX = frozenset("0123456789abcdef")
_DOCUMENT_KEYS = {"schema_version", "authorization_id", "payload"}
_PAYLOAD_KEYS = {
    "authorization_schema",
    "plan_id",
    "host_id",
    "skill_name",
    "skill_path",
    "link",
    "target",
    "state",
}
_LINK_KEYS = {"text", "device", "inode", "ctime_ns"}
_TARGET_KEYS = {"path", "device", "inode", "ctime_ns"}
_STATE_KEYS = {"type", "checksum"}


def _fail(code: str, message: str, *, exit_code: int = 2) -> NoReturn:
    raise ContractError(code, message, exit_code=exit_code)


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


# ---------------------------------------------------------------------------
# Live filesystem proofs (never resolve() an operator-supplied path)
# ---------------------------------------------------------------------------


def _object_identity(info: os.stat_result, what: str) -> dict[str, int]:
    """Bind an inode version as well as its number: deleted inodes can be reused."""
    device = getattr(info, "st_dev", None)
    inode = getattr(info, "st_ino", None)
    ctime_ns = getattr(info, "st_ctime_ns", None)
    if (
        type(device) is not int or type(inode) is not int or inode <= 0
        or type(ctime_ns) is not int or ctime_ns < 0
    ):
        _fail(
            "identity-unprovable",
            f"{what} object identity cannot be proven on this filesystem",
        )
    return {"device": device, "inode": inode, "ctime_ns": ctime_ns}


def _real_directory(path: Path, what: str) -> os.stat_result:
    info = _lstat(path)
    if info is None:
        _fail("unsafe-path", f"{what} does not exist")
    if stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        _fail("unsafe-path", f"{what} is not a real directory")
    return info


def _target_comparison_key(path: Path | str) -> str:
    """Compare spellings without treating equality as a filesystem safety proof.

    This key is never used for filesystem access; raw link text is retained.
    Unsupported device namespaces and Win32-trimmed components stay refused.
    """
    value = str(path)
    if os.name != "nt":
        return os.path.normpath(value)
    value = ntpath.normpath(value)
    if value[:8].upper() == "\\\\?\\UNC\\":
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        ordinary = value[4:]
        if len(ordinary) < 3 or ordinary[0].upper() not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" or ordinary[1:3] != ":\\":
            _fail("unsafe-path", "unsupported Windows target namespace")
        value = ordinary
    elif value.startswith("\\\\.\\"):
        _fail("unsafe-path", "unsupported Windows target namespace")
    if any(part.endswith((".", " ")) for part in value.split("\\") if part):
        _fail("unsafe-path", "ambiguous Windows target spelling")
    return value


def _resolve_link_text(link: Path, text: str) -> Path:
    """Kernel-faithful one-link resolution with nofollow component proofs.

    Each traversed component — including every step contributed by relative
    ``..``/``.`` text — is lstat-proven a real directory before the next step
    is applied, so the lexical walk matches kernel resolution exactly. Any
    nested link, reparse point, missing or non-directory component fails
    closed; this function never follows the selected link itself nor any
    other link.
    """
    if not isinstance(text, str) or not text:
        _fail("unsafe-path", "the Skill link carries empty link text")
    if os.path.isabs(text):
        absolute = Path(text)
        current = Path(absolute.anchor)
        parts = absolute.parts[1:]
    else:
        current = link.parent
        parts = Path(text).parts
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            # The walk has proven every component of ``current`` physical, so
            # the lexical parent is exactly the kernel's parent step.
            current = current.parent
            continue
        current = current / part
        info = _lstat(current)
        if info is None:
            _fail("unsafe-path", "the Skill link target does not exist")
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            _fail(
                "unsafe-path",
                "the Skill link traverses a nested link or reparse point",
            )
        if not stat.S_ISDIR(info.st_mode):
            _fail("unsafe-path", "the Skill link traverses a non-directory component")
    return current


def _read_link(link: Path, *, prepare: bool) -> tuple[str, dict[str, int]]:
    """Exact link text plus the link object's own fail-closed lstat identity."""
    info = _lstat(link)
    if info is None:
        if prepare:
            _fail("invalid-argument", "the selected Skill path does not exist")
        _fail("link-mismatch", "the authorized Skill link is no longer present")
    if not stat.S_ISLNK(info.st_mode):
        if prepare:
            _fail(
                "invalid-argument",
                "the selected Skill path is not a link and needs no authorization",
            )
        _fail("link-mismatch", "the authorized Skill link was replaced by a non-link")
    identity = _object_identity(info, "the Skill link")
    try:
        text = os.readlink(link)
    except OSError:
        _fail("read-failed", "the selected Skill link cannot be read")
    return text, identity


def _skill_identity(target: Path, expected_name: str) -> dict[str, Any]:
    """The physical target must prove the logical Skill name via SKILL.md."""
    from sbtd_upgrade_inventory import _frontmatter_name

    skill_md = target / "SKILL.md"
    info = _lstat(skill_md)
    if info is None:
        _fail("skill-identity-unproven", "the link target carries no SKILL.md")
    if stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        _fail("unsafe-path", "the link target SKILL.md is not a regular file")
    before = snapshot(skill_md)
    actual = _frontmatter_name(skill_md)
    if actual != expected_name:
        _fail(
            "skill-identity-mismatch",
            "the link target SKILL.md name does not match the logical Skill name",
        )
    if snapshot(skill_md) != before:
        _fail("state-conflict", "the Skill identity changed while it was checked")
    return before


# ---------------------------------------------------------------------------
# Scope binding helpers
# ---------------------------------------------------------------------------


def _root_keys(host: Mapping[str, Any]) -> set[str]:
    return {os.path.normpath(root) for root in host["skills_roots"]}


def _find_host(hosts: Any, host_id: Any) -> dict[str, Any]:
    """Defensive re-validation of the sealed scope's host entries."""
    if not isinstance(host_id, str) or not host_id:
        _fail("invalid-argument", "host id must be a non-empty string")
    if isinstance(hosts, (str, bytes)) or not isinstance(hosts, Sequence):
        _fail("invalid-argument", "hosts must be a sequence of scope host entries")
    matches = [
        entry for entry in hosts if isinstance(entry, Mapping) and entry.get("id") == host_id
    ]
    if not matches:
        _fail(
            "authorization-mismatch",
            "the host is not part of the sealed upgrade plan scope",
        )
    if len(matches) != 1:
        _fail("invalid-argument", "the sealed scope carries duplicate host ids")
    entry = matches[0]
    roots = entry.get("skills_roots")
    if not isinstance(roots, list) or any(
        not isinstance(root, str) or not os.path.isabs(root) for root in roots
    ):
        _fail(
            "invalid-argument",
            "the bound host carries no absolute Skills roots in the sealed scope",
        )
    return {"id": host_id, "skills_roots": list(roots)}


def _operator_path(value: Any, what: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid-argument", f"{what} must be a non-empty path string")
    candidate = Path(value)
    if not candidate.is_absolute():
        _fail("invalid-argument", f"{what} must be an absolute path")
    # _canonical lstat-proves every existing component without following links.
    return _canonical(candidate)


def _logical_link(value: Any) -> tuple[Path, str]:
    """Operator-supplied logical link path; the parent chain is proven physical."""
    if not isinstance(value, str) or not value.strip():
        _fail("invalid-argument", "the Skill path must be a non-empty path string")
    raw = Path(value)
    if not raw.is_absolute():
        _fail("invalid-argument", "the Skill path must be an absolute path")
    name = raw.name
    if not name:
        _fail("invalid-argument", "the Skill path must name a link inside a Skills root")
    # The final component is expected to be the link itself, so only the
    # parent chain goes through the nofollow canonical walk here.
    return _canonical(raw.parent) / name, name


# ---------------------------------------------------------------------------
# Phase 1: prepare (explicit initial target access)
# ---------------------------------------------------------------------------


def prepare_link_authorization(
    *,
    plan_id: Any,
    hosts: Any,
    host_id: Any,
    skill_path: Any,
    target_path: Any,
) -> dict[str, Any]:
    """Seal one precise linked-Skill authorization; reads nothing beforehand.

    The operator-supplied physical target path is the explicit initial access
    authorization: only after it is proven — lexically and by object identity
    — to be exactly the link's target is any target content read (the Skill
    identity proof and the whole-tree digest).
    """
    if not (
        isinstance(plan_id, str) and len(plan_id) == 64 and _HEX.issuperset(plan_id)
    ):
        _fail("invalid-argument", "plan_id must be a lowercase SHA-256 hex digest")
    host = _find_host(hosts, host_id)
    link, name = _logical_link(skill_path)
    if os.path.normpath(str(link.parent)) not in _root_keys(host):
        _fail(
            "scope-violation",
            "the linked Skill is not a direct child of the bound host's selected Skills roots",
        )
    text, link_identity = _read_link(link, prepare=True)
    supplied = _operator_path(target_path, "the supplied physical target")
    lexical_target = os.path.join(str(link.parent), text)
    if _target_comparison_key(lexical_target) != _target_comparison_key(supplied):
        _fail("target-mismatch", "the supplied physical path is not the link target")
    # The lexical check only rejects: traverse the original text afterward so
    # a symlink before '..' cannot disappear through normalization.
    target = _resolve_link_text(link, text)
    target_info = _real_directory(target, "the link target")
    supplied_info = _real_directory(supplied, "the supplied physical target")
    if _target_comparison_key(target) != _target_comparison_key(supplied):
        _fail(
            "target-mismatch",
            "the supplied physical path is not the link target",
        )
    if _object_identity(supplied_info, "the supplied physical target") != _object_identity(
        target_info, "the link target"
    ):
        _fail(
            "target-mismatch",
            "the supplied physical path is not the link target object",
        )
    skill_state = _skill_identity(target, name)
    state, entries = directory_snapshot(target)
    skill_entry = next((entry for entry in entries if entry["path"] == "SKILL.md"), None)
    if skill_entry is None or {
        "type": skill_entry["type"], "checksum": skill_entry["checksum"]
    } != skill_state:
        _fail("state-conflict", "the sealed tree no longer contains the proven Skill identity")
    payload = {
        "authorization_schema": AUTHORIZATION_SCHEMA,
        "plan_id": plan_id,
        "host_id": host["id"],
        "skill_name": name,
        "skill_path": str(link),
        "link": {"text": text, **link_identity},
        "target": {"path": str(supplied), **_object_identity(target_info, "the link target")},
        "state": dict(state),
    }
    _validate_live(payload)
    return {
        "schema_version": 1,
        "authorization_id": _digest(payload),
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Document validation (structure, digest, plan/host/scope binding)
# ---------------------------------------------------------------------------


def _expect_exact(value: Any, keys: set[str], what: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid-document", f"{what} must be a JSON object")
    if set(value) != keys:
        _fail("invalid-document", f"{what} carries an unexpected or missing field")
    return dict(value)


def _expect_document_hex(value: Any, what: str) -> str:
    if not (
        isinstance(value, str) and len(value) == 64 and _HEX.issuperset(value)
    ):
        _fail("invalid-document", f"{what} is not a lowercase SHA-256 digest")
    return value


def _expect_document_identity(value: Any, keys: set[str], what: str) -> dict[str, Any]:
    identity = _expect_exact(value, keys, what)
    if any(type(identity[key]) is not int for key in ("device", "inode", "ctime_ns")):
        _fail("invalid-document", f"{what} identity must carry integer device, inode and ctime_ns")
    if identity["inode"] <= 0 or identity["ctime_ns"] < 0:
        _fail("invalid-document", f"{what} object identity is unproven")
    return identity


def _expect_payload(payload: Any) -> dict[str, Any]:
    """Full structural validation returning a freshly rebuilt payload."""
    sealed = _expect_exact(payload, _PAYLOAD_KEYS, "link authorization payload")
    if sealed["authorization_schema"] != AUTHORIZATION_SCHEMA:
        _fail("invalid-document", "document is not a probe link authorization")
    plan_id = _expect_document_hex(sealed["plan_id"], "authorization plan_id")
    host_id = sealed["host_id"]
    if not isinstance(host_id, str) or not host_id:
        _fail("invalid-document", "authorization host_id must be a non-empty string")
    skill_name = sealed["skill_name"]
    if not isinstance(skill_name, str) or not skill_name:
        _fail("invalid-document", "authorization skill_name must be a non-empty string")
    skill_path = sealed["skill_path"]
    if (
        not isinstance(skill_path, str)
        or not os.path.isabs(skill_path)
        or ".." in Path(skill_path).parts
        or Path(skill_path).name != skill_name
    ):
        _fail(
            "invalid-document",
            "authorization skill_path must be an absolute link-free path named by skill_name",
        )
    link = _expect_document_identity(sealed["link"], _LINK_KEYS, "authorization link")
    if not isinstance(link["text"], str) or not link["text"]:
        _fail("invalid-document", "authorization link text must be a non-empty string")
    target = _expect_document_identity(sealed["target"], _TARGET_KEYS, "authorization target")
    if not isinstance(target["path"], str) or not os.path.isabs(target["path"]) or (
        ".." in Path(target["path"]).parts
    ):
        _fail("invalid-document", "authorization target path must be absolute and link-free")
    state = _expect_exact(sealed["state"], _STATE_KEYS, "authorization state")
    if state["type"] != "directory":
        _fail("invalid-document", "authorization state must describe a directory")
    state["checksum"] = _expect_document_hex(state["checksum"], "authorization state checksum")
    return {
        "authorization_schema": AUTHORIZATION_SCHEMA,
        "plan_id": plan_id,
        "host_id": host_id,
        "skill_name": skill_name,
        "skill_path": skill_path,
        "link": {
            "text": link["text"], "device": link["device"],
            "inode": link["inode"], "ctime_ns": link["ctime_ns"],
        },
        "target": {
            "path": target["path"],
            "device": target["device"],
            "inode": target["inode"],
            "ctime_ns": target["ctime_ns"],
        },
        "state": {"type": "directory", "checksum": state["checksum"]},
    }


def validate_link_authorization(
    document: Any, *, plan_id: str, hosts: Any
) -> dict[str, Any]:
    """Validate one artifact and bind it to this plan, host and Skills roots."""
    doc = _expect_exact(document, _DOCUMENT_KEYS, "link authorization document")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        _fail("invalid-document", "link authorization schema_version must be 1")
    authorization_id = _expect_document_hex(doc["authorization_id"], "authorization_id")
    payload = _expect_payload(doc["payload"])
    if _digest(payload) != authorization_id:
        _fail(
            "authorization-id-mismatch",
            "authorization id does not match the canonical payload digest",
            exit_code=3,
        )
    if payload["plan_id"] != plan_id:
        _fail(
            "authorization-mismatch",
            "the authorization is bound to a different upgrade plan",
        )
    host = _find_host(hosts, payload["host_id"])
    parent = Path(payload["skill_path"]).parent
    if os.path.normpath(str(parent)) not in _root_keys(host):
        _fail(
            "authorization-mismatch",
            "the authorized Skill path is outside the bound host's selected Skills roots",
        )
    return payload


# ---------------------------------------------------------------------------
# Phase 2: live revalidation and safe materialization
# ---------------------------------------------------------------------------


def _validate_live(payload: Mapping[str, Any]) -> None:
    """Re-prove link identity+text, target identity and content digest."""
    skill_path = Path(payload["skill_path"])
    # The sealed parent chain must still be physical; an ancestor swap must
    # never silently redirect the lstat/readlink below.
    link = _canonical(skill_path.parent) / skill_path.name
    info = _lstat(link)
    if info is None or not stat.S_ISLNK(info.st_mode):
        _fail("link-mismatch", "the authorized Skill link is no longer a link")
    sealed_link = payload["link"]
    if _object_identity(info, "the authorized Skill link") != {
        "device": sealed_link["device"],
        "inode": sealed_link["inode"],
        "ctime_ns": sealed_link["ctime_ns"],
    }:
        _fail("identity-mismatch", "the authorized Skill link identity changed")
    try:
        text = os.readlink(link)
    except OSError:
        _fail("read-failed", "the authorized Skill link cannot be read")
    if text != sealed_link["text"]:
        _fail("link-mismatch", "the authorized Skill link text changed")
    lexical_target = os.path.join(str(link.parent), text)
    if _target_comparison_key(lexical_target) != _target_comparison_key(payload["target"]["path"]):
        _fail("link-mismatch", "the authorized Skill link names a different target")
    target = _resolve_link_text(link, text)
    if _target_comparison_key(target) != _target_comparison_key(payload["target"]["path"]):
        _fail("link-mismatch", "the authorized Skill link resolves to a different target")
    target_info = _real_directory(target, "the authorized link target")
    if _object_identity(target_info, "the authorized link target") != {
        "device": payload["target"]["device"],
        "inode": payload["target"]["inode"],
        "ctime_ns": payload["target"]["ctime_ns"],
    }:
        _fail("identity-mismatch", "the authorized link target identity changed")
    state, _entries = directory_snapshot(target)
    if state != {"type": "directory", "checksum": payload["state"]["checksum"]}:
        _fail("state-conflict", "the authorized link target content changed")


def materialize_authorized_skill(
    payload: Mapping[str, Any], *, destination: Any, private_root: Any
) -> dict[str, Any]:
    """Copy the authorized physical target as a plain fixture directory.

    The sealed payload is structurally re-asserted, every live binding is
    revalidated, the existing nofollow backup primitive performs the copy
    with its own source-state check and readback, and the live bindings are
    revalidated again after the copy — any drift before or during the copy
    refuses the materialization before the probe host is ever spawned.
    """
    sealed = _expect_payload(payload)
    _validate_live(sealed)
    result = backup_reference(
        {"path": sealed["target"]["path"], "state": dict(sealed["state"])},
        Path(destination),
        private_root=Path(private_root),
    )
    _validate_live(sealed)
    _skill_identity(Path(destination), sealed["skill_name"])
    return result

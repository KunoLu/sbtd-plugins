from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from onboard_contracts import ContractError
from sbtd_migration_legacy import (
    read_legacy_identity,
    validate_projection_graph,
    validate_task_projection,
)

SOURCE_PATH = ".trellis/tasks/09-01-alpha/task.json"
DONE_EVENT = {
    "at": "unknown",
    "from": "unknown",
    "to": "done",
    "reason": "legacy completion fact",
    "evidence": "legacy task.json status",
}
CANCELLED_EVENT = {
    "at": "unknown",
    "from": "unknown",
    "to": "cancelled",
    "reason": "legacy cancellation fact",
    "evidence": "legacy task.json status",
}
BLOCKED_EVENT = {
    "at": "unknown",
    "from": "unknown",
    "to": "blocked",
    "reason": "legacy blocked fact",
    "evidence": "legacy task.json status",
}
NO_RECORDED_REASON = "legacy task.json status=blocked; reason not recorded"
ARCHIVED_PATH = ".trellis/tasks/archive/2026-09/09-01-alpha/task.json"


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _legacy_source(**overrides):
    base = {
        "id": "alpha",
        "name": "alpha",
        "title": "Alpha task",
        "description": "legacy description",
        "status": "planning",
        "createdAt": "2026-09-01",
        "completedAt": None,
        "branch": None,
        "base_branch": "main",
        "parent": None,
        "children": [],
        "subtasks": [],
        "meta": {"votes": 3, "score": 1.5, "flag": True},
        "custom_unknown": {"nested": ["x", 2]},
    }
    base.update(overrides)
    return base


def _task_md(
    *,
    identity="alpha",
    status="planned",
    parent=None,
    branch=None,
    created_at=None,
    updated_at=None,
    completed_at=None,
    workflow_mode=None,
    mode_source="migration-unknown",
    blocked_reason=None,
    extra=(),
    events=(),
):
    fields = [
        ("schema_version", 1),
        ("id", identity),
        ("workflow_mode", workflow_mode),
        ("mode_source", mode_source),
        ("mode_note", "legacy Trellis task without mode proof"),
        ("status", status),
        ("branch", branch),
        ("created_at", created_at),
        ("updated_at", updated_at),
        ("completed_at", completed_at),
    ]
    if parent is not None:
        fields.append(("parent", parent))
    if blocked_reason is not None:
        fields.append(("blocked_reason", blocked_reason))
    fields.extend(extra)
    lines = ["---"]
    lines.extend(
        key + ": " + json.dumps(value, ensure_ascii=False) for key, value in fields
    )
    lines.append("---")
    lines.append("")
    lines.append("# task " + identity)
    lines.append("")
    provenance = {
        field: {"source": source, "status": "unproven"}
        for field, value, source in (
            ("created_at", created_at, "legacy task.json: createdAt (sidecar or private original)"),
            ("updated_at", updated_at, "legacy task.json: no recorded update time"),
            ("completed_at", completed_at, "legacy task.json: completedAt (sidecar or private original)"),
        )
        if value is None
    }
    lines.extend((
        "```sbtd-legacy-time-provenance",
        json.dumps(provenance),
        "```",
        "",
    ))
    if events:
        lines.append("## 状态事件")
        lines.append("")
        lines.append("| at | from | to | reason | evidence |")
        lines.append("|---|---|---|---|---|")
        for event in events:
            lines.append(
                "| {at} | {from} | {to} | {reason} | {evidence} |".format(**event)
            )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _sidecar(
    source_raw,
    *,
    original="auto",
    source_path=SOURCE_PATH,
    sha="auto",
    redacted=(),
    parse_status="valid",
):
    if original == "auto":
        original = json.loads(source_raw.decode("utf-8"))
    if sha == "auto":
        sha = hashlib.sha256(source_raw).hexdigest()
    return _json_bytes(
        {
            "schema_version": 1,
            "source_path": source_path,
            "source_sha256": sha,
            "original": original,
            "redacted_paths": list(redacted),
            "parse_status": parse_status,
        }
    )


def _projection(
    source=None,
    *,
    source_path=SOURCE_PATH,
    decision="share",
    task_raw=None,
    sidecar_raw=None,
):
    source = _legacy_source() if source is None else source
    source_raw = _json_bytes(source)
    if task_raw is None:
        task_raw = _task_md()
    if sidecar_raw is None:
        sidecar_raw = _sidecar(source_raw, source_path=source_path)
    return validate_task_projection(
        source_raw, task_raw, sidecar_raw, source_path=source_path, decision=decision
    )


def _done_projection(source_path, **source_overrides):
    source = _legacy_source(
        status="completed", completedAt="2026-09-05", **source_overrides
    )
    return _projection(
        source,
        source_path=source_path,
        task_raw=_task_md(identity=source["id"], status="done", events=[DONE_EVENT]),
    )


def _suspension(**overrides):
    # Exact old observed shape: state/reason/since/resumeWhen, all synthetic.
    base = {
        "state": "suspended",
        "reason": "waiting on the upstream API key",
        "since": "2026-08-20T09:30:00Z",
        "resumeWhen": "the upstream key is issued",
    }
    base.update(overrides)
    return base


def _cancelled_projection(
    source_path=SOURCE_PATH,
    *,
    cancelled_at="2026-02-10T15:30:00Z",
    event_at=None,
    **source_overrides,
):
    source_overrides.setdefault("createdAt", "2026-01-01")
    source = _legacy_source(status="cancelled", **source_overrides)
    if cancelled_at is not None:
        source["cancelledAt"] = cancelled_at
    if event_at is None:
        event_at = cancelled_at if cancelled_at is not None else "unknown"
    return _projection(
        source,
        source_path=source_path,
        task_raw=_task_md(
            identity=source["id"],
            status="cancelled",
            events=[dict(CANCELLED_EVENT, at=event_at)],
        ),
    )


def _blocked_projection(
    source_path=SOURCE_PATH,
    *,
    suspension=None,
    document_reason=NO_RECORDED_REASON,
    event_at="unknown",
    **source_overrides,
):
    source_overrides.setdefault("createdAt", "2026-01-01")
    source = _legacy_source(status="blocked", **source_overrides)
    if suspension is not None:
        source["meta"] = {**source["meta"], "suspension": suspension}
    return _projection(
        source,
        source_path=source_path,
        task_raw=_task_md(
            identity=source["id"],
            status="blocked",
            blocked_reason=document_reason,
            events=[dict(BLOCKED_EVENT, at=event_at)],
        ),
    )


class LegacyIdentityTests(unittest.TestCase):
    def test_pinned_metadata_is_not_a_second_name_or_normalization_permission(self):
        raw = b"name=dev01\ninitialized_at=2026-09-01T12:00:00\n"
        self.assertEqual(read_legacy_identity(raw), "dev01")
        for invalid in (
            b"name=dev01\nname=dev01\n",
            b"name=Alice\ninitialized_at=2026-09-01T12:00:00\n",
            b"name=dev_01\ninitialized_at=2026-09-01T12:00:00\n",
        ):
            with self.subTest(raw=invalid), self.assertRaises(ContractError):
                read_legacy_identity(invalid)

    def test_unparseable_or_missing_identity_facts_are_rejected(self):
        self.assertEqual(read_legacy_identity(b"name=dev01\n"), "dev01")
        for invalid in (
            b"initialized_at=2026-09-01T12:00:00\n",
            b"name=dev01\ninitialized_at=one\ninitialized_at=two\n",
            b"name=dev01\nnot-a-declaration\n",
            b"name = dev01\n",
            b"\xff\xfe",
        ):
            with self.subTest(raw=invalid), self.assertRaises(ContractError):
                read_legacy_identity(invalid)


class TaskProjectionTests(unittest.TestCase):
    def test_high_precision_json_cannot_be_rounded_in_the_shared_snapshot(self):
        source_raw = _json_bytes(_legacy_source()).replace(
            b'"score": 1.5', b'"score": 1.0000000000000001'
        )
        rounded = _sidecar(source_raw)
        with self.assertRaises(ContractError):
            validate_task_projection(
                source_raw,
                _task_md(),
                rounded,
                source_path=SOURCE_PATH,
                decision="share",
            )
        exact = rounded.replace(b'"score": 1.0', b'"score": 1.0000000000000001')
        validate_task_projection(
            source_raw, _task_md(), exact, source_path=SOURCE_PATH, decision="share"
        )

    def test_share_projection_preserves_identity_mode_time_and_unknown_fields(self):
        projection = _projection()
        self.assertEqual(projection.legacy_id, "alpha")
        self.assertIsNone(projection.parent)
        self.assertEqual(projection.children, ())
        self.assertEqual(projection.aliases, ("09-01-alpha",))
        frontmatter = projection.document.frontmatter
        self.assertEqual(frontmatter["status"], "planned")
        self.assertIsNone(frontmatter["workflow_mode"])
        self.assertEqual(frontmatter["mode_source"], "migration-unknown")
        self.assertIsNone(frontmatter["created_at"])
        self.assertIsNone(frontmatter["updated_at"])
        self.assertIsNone(frontmatter["completed_at"])
        self.assertEqual(projection.document.events, ())

    def test_done_task_with_date_only_completion_records_unknown_history(self):
        projection = _done_projection(SOURCE_PATH)
        frontmatter = projection.document.frontmatter
        self.assertEqual(frontmatter["status"], "done")
        self.assertIsNone(frontmatter["completed_at"])
        self.assertEqual(len(projection.document.events), 1)
        self.assertEqual(projection.document.events[0]["at"], "unknown")

    def test_full_timezone_timestamps_are_preserved_not_fabricated(self):
        source = _legacy_source(
            status="completed",
            createdAt="2026-09-01T12:00:00Z",
            completedAt="2026-09-05T10:00:00+08:00",
        )
        event = dict(DONE_EVENT, at="2026-09-05T10:00:00+08:00")
        projection = _projection(
            source,
            task_raw=_task_md(
                status="done",
                created_at="2026-09-01T12:00:00Z",
                completed_at="2026-09-05T10:00:00+08:00",
                events=[event],
            ),
        )
        frontmatter = projection.document.frontmatter
        self.assertEqual(frontmatter["created_at"], "2026-09-01T12:00:00Z")
        self.assertEqual(frontmatter["completed_at"], "2026-09-05T10:00:00+08:00")

    def test_redact_decision_keeps_private_truth_but_hides_raw_hash(self):
        source = _legacy_source(meta={"token": "s3cr3t", "votes": 3})
        source_raw = _json_bytes(source)
        original = json.loads(source_raw.decode("utf-8"))
        original["meta"]["token"] = None
        projection = _projection(
            source,
            decision="redact",
            sidecar_raw=_sidecar(
                source_raw, original=original, sha=None, redacted=["/meta/token"]
            ),
        )
        self.assertEqual(projection.legacy_id, "alpha")
        root_private = _projection(
            source,
            decision="redact",
            sidecar_raw=_sidecar(source_raw, original=None, sha=None, redacted=[""]),
        )
        self.assertEqual(root_private.legacy_id, "alpha")

    def test_invalid_source_never_becomes_a_normal_task(self):
        task_raw = _task_md()
        duplicate = b'{"id": "alpha", "id": "alpha", "status": "planning"}'
        non_finite = b'{"id": "alpha", "status": "planning", "meta": NaN}'
        broken = b'{"id": "alpha", '
        for source_raw in (duplicate, non_finite, broken):
            sidecar_raw = _sidecar(
                b"{}", original=None, sha=None, redacted=[""], parse_status="invalid"
            )
            with self.subTest(source_raw=source_raw), self.assertRaises(ContractError):
                validate_task_projection(
                    source_raw,
                    task_raw,
                    sidecar_raw,
                    source_path=SOURCE_PATH,
                    decision="redact",
                )
        source_raw = _json_bytes(_legacy_source())
        dishonest = _sidecar(
            source_raw, original=None, sha=None, redacted=[""], parse_status="invalid"
        )
        with self.assertRaises(ContractError):
            validate_task_projection(
                source_raw,
                task_raw,
                dishonest,
                source_path=SOURCE_PATH,
                decision="redact",
            )

    def test_unmapped_status_and_archive_position_alone_never_prove_done(self):
        for status in ("archived", "mystery"):
            with self.subTest(status=status), self.assertRaises(ContractError):
                _projection(_legacy_source(status=status))
        archived_path = ".trellis/tasks/archive/2026-09/09-01-alpha/task.json"
        with self.assertRaises(ContractError):
            _projection(_legacy_source(), source_path=archived_path)
        projection = _done_projection(archived_path)
        self.assertEqual(projection.document.frontmatter["status"], "done")

    def test_unfinished_task_with_completion_facts_is_rejected(self):
        with self.assertRaises(ContractError):
            _projection(_legacy_source(completedAt="2026-09-05"))
        with self.assertRaises(ContractError):
            _projection(task_raw=_task_md(events=[DONE_EVENT]))

    def test_done_task_requires_truthful_completion_event(self):
        source = _legacy_source(status="completed", completedAt="2026-09-05")
        with self.assertRaises(ContractError):
            _projection(source, task_raw=_task_md(status="done"))
        fabricated = dict(DONE_EVENT, at="2026-09-05T00:00:00Z")
        with self.assertRaises(ContractError):
            _projection(source, task_raw=_task_md(status="done", events=[fabricated]))
        wrong_from = dict(DONE_EVENT, **{"from": "planned"})
        with self.assertRaises(ContractError):
            _projection(source, task_raw=_task_md(status="done", events=[wrong_from]))

    def test_unknown_time_semantics_are_rejected(self):
        for created in ("2026-09-01T12:00:00", "2026-02-30", 20260901):
            with self.subTest(createdAt=created), self.assertRaises(ContractError):
                _projection(_legacy_source(createdAt=created))
        with self.assertRaises(ContractError):
            _projection(task_raw=_task_md(created_at="2026-09-01T00:00:00Z"))

    def test_unprovable_mode_and_update_time_stay_empty(self):
        with self.assertRaises(ContractError):
            _projection(task_raw=_task_md(workflow_mode="strict", mode_source="user"))
        with self.assertRaises(ContractError):
            _projection(task_raw=_task_md(updated_at="2026-09-01T12:00:00Z"))

    def test_ambiguous_identity_and_inferred_parent_are_rejected(self):
        with self.assertRaises(ContractError):
            _projection(_legacy_source(name="alpha-renamed"))
        with self.assertRaises(ContractError):
            _projection(task_raw=_task_md(parent="beta"))
        with self.assertRaises(ContractError):
            _projection(_legacy_source(parent=5))
        with self.assertRaises(ContractError):
            _projection(_legacy_source(children="09-02-beta"))

    def test_frontmatter_must_not_absorb_legacy_field_spellings(self):
        with self.assertRaises(ContractError):
            _projection(task_raw=_task_md(extra=(("meta", {"x": 1}),)))
        with self.assertRaises(ContractError):
            _projection(task_raw=_task_md(extra=(("createdAt", "2026-09-01"),)))

    def test_shared_snapshot_must_preserve_unknown_fields_and_types(self):
        source_raw = _json_bytes(_legacy_source())
        lossy_unknown = json.loads(source_raw.decode("utf-8"))
        del lossy_unknown["custom_unknown"]
        type_changed = json.loads(source_raw.decode("utf-8"))
        type_changed["meta"]["votes"] = 3.0
        bool_changed = json.loads(source_raw.decode("utf-8"))
        bool_changed["meta"]["flag"] = 1
        extra_key = json.loads(source_raw.decode("utf-8"))
        extra_key["invented"] = None
        for original in (lossy_unknown, type_changed, bool_changed, extra_key):
            with self.subTest(original=original), self.assertRaises(ContractError):
                _projection(sidecar_raw=_sidecar(source_raw, original=original))

    def test_hash_visibility_follows_full_shareability(self):
        source_raw = _json_bytes(_legacy_source())
        with self.assertRaises(ContractError):
            _projection(sidecar_raw=_sidecar(source_raw, sha="0" * 64))
        with self.assertRaises(ContractError):
            _projection(sidecar_raw=_sidecar(source_raw, sha=None))
        private_path = _projection(
            sidecar_raw=_sidecar(source_raw, source_path=None, sha=None)
        )
        self.assertEqual(private_path.legacy_id, "alpha")
        with self.assertRaises(ContractError):
            _projection(
                sidecar_raw=_sidecar(
                    source_raw,
                    source_path=None,
                    sha=hashlib.sha256(source_raw).hexdigest(),
                )
            )
        with self.assertRaises(ContractError):
            _projection(
                decision="redact",
                sidecar_raw=_sidecar(
                    source_raw, sha=hashlib.sha256(source_raw).hexdigest()
                ),
            )
        with self.assertRaises(ContractError):
            _projection(sidecar_raw=_sidecar(source_raw, redacted=["/meta"]))

    def test_redaction_form_is_exact(self):
        source_raw = _json_bytes(_legacy_source())
        exact = json.loads(source_raw.decode("utf-8"))
        exact["meta"]["score"] = None
        not_nulled = json.loads(source_raw.decode("utf-8"))
        for redacted, original in (
            (["/meta/nope"], exact),
            (["/meta", "/meta/score"], exact),
            (["/meta/score", "/meta/score"], exact),
            (["/custom_unknown/nested/9"], exact),
            (["/meta/score"], not_nulled),
            (["/meta/score"], None),
            ([""], exact),
        ):
            with self.subTest(redacted=redacted), self.assertRaises(ContractError):
                _projection(
                    decision="redact",
                    sidecar_raw=_sidecar(
                        source_raw, original=original, sha=None, redacted=redacted
                    ),
                )

    def test_completion_event_cannot_invent_source_evidence(self):
        event = {**DONE_EVENT, "evidence": "invented acceptance record"}
        with self.assertRaises(ContractError):
            _projection(
                _legacy_source(status="completed"),
                task_raw=_task_md(status="done", events=(event,)),
            )

    def test_null_legacy_times_require_source_provenance_in_body(self):
        candidate = _task_md()
        marker = b"```sbtd-legacy-time-provenance\n"
        start = candidate.index(marker)
        end = candidate.index(b"```\n", start + len(marker)) + len(b"```\n")
        with self.assertRaises(ContractError):
            _projection(task_raw=candidate[:start] + candidate[end:])
        with self.assertRaises(ContractError):
            _projection(task_raw=candidate.replace(
                b"legacy task.json: createdAt (sidecar or private original)", b"unrelated-source"
            ))

    def test_old_unknown_fixed_field_does_not_replace_current_schema_field(self):
        projection = _projection(_legacy_source(schema_version="old-custom-value"))
        self.assertEqual(projection.document.frontmatter["schema_version"], 1)

    def test_sidecar_schema_version_is_exactly_an_integer_one(self):
        source_raw = _json_bytes(_legacy_source())
        for version in (b"1.0", b"1e0", b"true", b'"1"'):
            sidecar = _sidecar(source_raw).replace(b'"schema_version": 1', b'"schema_version": ' + version)
            with self.subTest(version=version), self.assertRaises(ContractError):
                _projection(sidecar_raw=sidecar)

    def test_unknown_legacy_source_keys_cannot_become_live_extensions(self):
        with self.assertRaises(ContractError):
            _projection(
                task_raw=_task_md(extra=(("custom_unknown", {"nested": ["x", 2]}),))
            )
        _projection(task_raw=_task_md(extra=(("current_extension", {"ok": True}),)))

    def test_archive_root_blocks_unfinished_tasks(self):
        archive_root = ".trellis/tasks/archive/task.json"
        with self.assertRaises(ContractError):
            _projection(source_path=archive_root)
        self.assertEqual(
            _done_projection(archive_root).document.frontmatter["status"], "done"
        )

    def test_sidecar_shape_and_source_binding(self):
        source_raw = _json_bytes(_legacy_source())
        sidecar = json.loads(_sidecar(source_raw).decode("utf-8"))
        for mutate in (
            lambda value: value.update(extra=1),
            lambda value: value.pop("original"),
            lambda value: value.update(schema_version="1"),
            lambda value: value.update(source_sha256="ABCDEF" + "0" * 58),
        ):
            candidate = copy.deepcopy(sidecar)
            mutate(candidate)
            with (
                self.subTest(candidate=sorted(candidate)),
                self.assertRaises(ContractError),
            ):
                _projection(sidecar_raw=_json_bytes(candidate))
        with self.assertRaises(ContractError):
            _projection(
                sidecar_raw=_sidecar(
                    source_raw, source_path=".trellis/tasks/09-01-other/task.json"
                )
            )

    def test_cancelled_projection_preserves_terminal_cancellation_fact(self):
        projection = _cancelled_projection()
        frontmatter = projection.document.frontmatter
        self.assertEqual(frontmatter["status"], "cancelled")
        self.assertIsNone(frontmatter["completed_at"])
        self.assertIsNone(frontmatter["workflow_mode"])
        self.assertEqual(frontmatter["mode_source"], "migration-unknown")
        self.assertIsNone(projection.archive_bucket)
        self.assertEqual(len(projection.document.events), 1)
        event = projection.document.events[0]
        self.assertEqual(event["from"], "unknown")
        self.assertEqual(event["to"], "cancelled")
        self.assertEqual(event["at"], "2026-02-10T15:30:00Z")
        self.assertEqual(event["reason"], "legacy cancellation fact")
        self.assertEqual(event["evidence"], "legacy task.json status")

    def test_cancelled_archive_bucket_uses_proven_cancellation_not_folder_date(self):
        # The archive folder month (2026-09, Q3) is not a cancellation proof.
        projection = _cancelled_projection(ARCHIVED_PATH)
        self.assertEqual(projection.archive_bucket, "2026-Q1")
        date_only = _cancelled_projection(
            ARCHIVED_PATH, cancelled_at="2026-02-10", event_at="unknown"
        )
        # A date-only cancelledAt never becomes a quarter: the event time is
        # unknown, so a re-archived import must derive the same undated bucket.
        self.assertEqual(date_only.archive_bucket, "undated")
        self.assertEqual(date_only.document.events[0]["at"], "unknown")
        self.assertIsNone(date_only.document.frontmatter["completed_at"])

    def test_cancelled_archive_without_cancellation_time_is_undated(self):
        projection = _cancelled_projection(ARCHIVED_PATH, cancelled_at=None)
        self.assertEqual(projection.archive_bucket, "undated")
        event = projection.document.events[0]
        self.assertEqual(event["at"], "unknown")
        self.assertEqual(event["to"], "cancelled")
        self.assertIsNone(projection.document.frontmatter["completed_at"])

    def test_cancelled_completion_facts_and_alias_spellings_are_rejected(self):
        with self.assertRaises(ContractError):
            _cancelled_projection(completedAt="2026-02-10")
        with self.assertRaises(ContractError):
            _cancelled_projection(cancelled_at="not-a-time")
        with self.assertRaises(ContractError):
            _projection(
                _legacy_source(
                    status="cancelled", createdAt="2026-01-01",
                    cancelledAt="2026-02-10T15:30:00Z",
                ),
                task_raw=_task_md(
                    status="cancelled",
                    completed_at="2026-02-10T15:30:00Z",
                    events=[dict(CANCELLED_EVENT, at="2026-02-10T15:30:00Z")],
                ),
            )
        with self.assertRaises(ContractError):
            _projection(
                _legacy_source(status="cancelled"),
                task_raw=_task_md(status="cancelled", events=[DONE_EVENT]),
            )
        with self.assertRaises(ContractError):
            _projection(
                _legacy_source(status="cancelled"),
                task_raw=_task_md(
                    status="cancelled",
                    events=[CANCELLED_EVENT],
                    extra=(("cancelledAt", "2026-02-10T15:30:00Z"),),
                ),
            )
        for spelling in ("canceled", "Cancelled"):
            with self.subTest(spelling=spelling), self.assertRaises(ContractError):
                _projection(_legacy_source(status=spelling))

    def test_blocked_projection_uses_proven_suspension_reason_and_time(self):
        projection = _blocked_projection(
            suspension=_suspension(), event_at="2026-08-20T09:30:00Z",
            document_reason="waiting on the upstream API key",
        )
        frontmatter = projection.document.frontmatter
        self.assertEqual(frontmatter["status"], "blocked")
        self.assertEqual(
            frontmatter["blocked_reason"], "waiting on the upstream API key"
        )
        self.assertIsNone(frontmatter["completed_at"])
        self.assertIsNone(frontmatter["updated_at"])
        self.assertIsNone(projection.archive_bucket)
        self.assertEqual(len(projection.document.events), 1)
        event = projection.document.events[0]
        self.assertEqual(event["from"], "unknown")
        self.assertEqual(event["to"], "blocked")
        self.assertEqual(event["at"], "2026-08-20T09:30:00Z")
        self.assertEqual(event["reason"], "legacy blocked fact")
        self.assertEqual(event["evidence"], "legacy task.json status")

    def test_blocked_reason_from_source_field_or_suspension_unambiguously(self):
        field_only = _blocked_projection(
            blocked_reason="waiting on reviewer sign-off",
            document_reason="waiting on reviewer sign-off",
        )
        self.assertEqual(
            field_only.document.frontmatter["blocked_reason"],
            "waiting on reviewer sign-off",
        )
        self.assertEqual(field_only.document.events[0]["at"], "unknown")
        agreeing = _blocked_projection(
            suspension=_suspension(reason="waiting on reviewer sign-off"),
            blocked_reason="waiting on reviewer sign-off",
            document_reason="waiting on reviewer sign-off",
            event_at="2026-08-20T09:30:00Z",
        )
        self.assertEqual(
            agreeing.document.frontmatter["blocked_reason"],
            "waiting on reviewer sign-off",
        )

    def test_blocked_without_recorded_reason_states_canonical_uncertainty(self):
        for source in (
            {},
            {"meta": {"suspension": {"state": "suspended", "resumeWhen": "later"}}},
        ):
            with self.subTest(source=source):
                projection = _blocked_projection(**source)
                self.assertEqual(
                    projection.document.frontmatter["blocked_reason"],
                    NO_RECORDED_REASON,
                )
                self.assertEqual(projection.document.events[0]["at"], "unknown")

    def test_blocked_suspension_date_only_since_keeps_time_unknown(self):
        projection = _blocked_projection(
            suspension=_suspension(since="2026-08-20"),
            document_reason="waiting on the upstream API key",
        )
        self.assertEqual(
            projection.document.frontmatter["blocked_reason"],
            "waiting on the upstream API key",
        )
        self.assertEqual(projection.document.events[0]["at"], "unknown")

    def test_blocked_malformed_or_contradictory_metadata_is_rejected(self):
        for suspension in (
            "suspended",
            _suspension(reason=""),
            _suspension(reason=42),
            _suspension(since="last week"),
        ):
            with self.subTest(suspension=suspension), self.assertRaises(ContractError):
                _blocked_projection(
                    suspension=suspension,
                    document_reason="waiting on the upstream API key",
                )
        with self.assertRaises(ContractError):
            _blocked_projection(blocked_reason="")
        with self.assertRaises(ContractError):
            _blocked_projection(
                suspension=_suspension(),
                blocked_reason="a different recorded cause",
                document_reason="waiting on the upstream API key",
            )
        with self.assertRaises(ContractError):
            _blocked_projection(
                suspension=_suspension(), document_reason="an invented cause"
            )

    def test_blocked_recovery_history_stays_unknown(self):
        source = _legacy_source(
            status="blocked", createdAt="2026-01-01",
            meta={"suspension": _suspension()},
        )
        resumed = {
            "at": "unknown",
            "from": "blocked",
            "to": "planned",
            "reason": "resumed after suspension",
            "evidence": "legacy task.json status",
        }
        with self.assertRaises(ContractError):
            _projection(
                source,
                task_raw=_task_md(
                    status="blocked",
                    blocked_reason="waiting on the upstream API key",
                    events=[dict(BLOCKED_EVENT, at="2026-08-20T09:30:00Z"), resumed],
                ),
            )
        with self.assertRaises(ContractError):
            _projection(
                source,
                task_raw=_task_md(
                    status="blocked",
                    blocked_reason="waiting on the upstream API key",
                ),
            )
        with self.assertRaises(ContractError):
            _projection(
                source,
                task_raw=_task_md(
                    status="blocked",
                    blocked_reason="waiting on the upstream API key",
                    events=[
                        dict(
                            BLOCKED_EVENT,
                            at="2026-08-20T09:30:00Z",
                            reason="the recorded suspension cause",
                        )
                    ],
                ),
            )

    def test_raw_blocked_and_cancelled_never_become_done(self):
        for raw_status in ("blocked", "cancelled"):
            with self.subTest(status=raw_status), self.assertRaises(ContractError):
                _projection(
                    _legacy_source(status=raw_status),
                    task_raw=_task_md(status="done", events=[DONE_EVENT]),
                )

    def test_archived_blocked_task_is_rejected(self):
        with self.assertRaises(ContractError):
            _blocked_projection(
                ARCHIVED_PATH,
                suspension=_suspension(),
                document_reason="waiting on the upstream API key",
                event_at="2026-08-20T09:30:00Z",
            )

    def test_redacted_blocker_reason_cannot_reappear_in_shared_frontmatter(self):
        secret_reason = "confidential acquisition decision"
        source = _legacy_source(
            status="blocked", createdAt="2026-01-01",
            meta={"suspension": _suspension(reason=secret_reason)},
        )
        redacted = copy.deepcopy(source)
        redacted["meta"]["suspension"]["reason"] = None
        raw = _json_bytes(source)
        sidecar = _sidecar(
            raw, original=redacted, sha=None,
            redacted=("/meta/suspension/reason",),
        )
        with self.assertRaises(ContractError):
            _projection(
                source, decision="redact", sidecar_raw=sidecar,
                task_raw=_task_md(
                    status="blocked", blocked_reason=secret_reason,
                    events=[dict(BLOCKED_EVENT, at="2026-08-20T09:30:00Z")],
                ),
            )

    def test_top_level_blocker_redaction_is_preserved_in_frontmatter(self):
        source = _legacy_source(
            status="blocked", blocked_reason="private coordinator assignment"
        )
        redacted = copy.deepcopy(source)
        redacted["blocked_reason"] = None
        sidecar = _sidecar(
            _json_bytes(source), original=redacted, sha=None,
            redacted=("/blocked_reason",),
        )
        projection = _projection(
            source, decision="redact", sidecar_raw=sidecar,
            task_raw=_task_md(
                status="blocked",
                blocked_reason="legacy task.json status=blocked; reason redacted",
                events=[BLOCKED_EVENT],
            ),
        )
        self.assertNotIn("private coordinator assignment", projection.document.text)
        with self.assertRaises(ContractError):
            _projection(
                source, decision="redact", sidecar_raw=sidecar,
                task_raw=_task_md(
                    status="blocked", blocked_reason=source["blocked_reason"],
                    events=[BLOCKED_EVENT],
                ),
            )

    def test_redacted_blocker_details_keep_truth_private_and_status_visible(self):
        source = _legacy_source(
            status="blocked", createdAt="2026-01-01",
            meta={"suspension": _suspension(reason="confidential acquisition decision")},
        )
        raw = _json_bytes(source)
        for pointer in ("", "/meta", "/meta/suspension", "/meta/suspension/reason"):
            redacted = copy.deepcopy(source)
            if pointer == "":
                redacted = None
            elif pointer == "/meta":
                redacted["meta"] = None
            elif pointer == "/meta/suspension":
                redacted["meta"]["suspension"] = None
            else:
                redacted["meta"]["suspension"]["reason"] = None
            at = "2026-08-20T09:30:00Z" if pointer.endswith("/reason") else "unknown"
            with self.subTest(pointer=pointer):
                projection = _projection(
                    source, decision="redact",
                    sidecar_raw=_sidecar(
                        raw, original=redacted, sha=None, redacted=(pointer,),
                    ),
                    task_raw=_task_md(
                        status="blocked",
                        blocked_reason="legacy task.json status=blocked; reason redacted",
                        events=[dict(BLOCKED_EVENT, at=at)],
                    ),
                )
                self.assertEqual(projection.document.frontmatter["status"], "blocked")
                self.assertNotIn(
                    "confidential acquisition decision", projection.document.text
                )
                self.assertEqual(projection.document.events[0]["at"], at)

    def test_redacted_cancellation_time_does_not_leak_through_event_or_archive(self):
        source = _legacy_source(
            status="cancelled", createdAt="2026-01-01",
            cancelledAt="2026-02-10T15:30:00Z",
        )
        redacted = copy.deepcopy(source)
        redacted["cancelledAt"] = None
        sidecar = _sidecar(
            _json_bytes(source), source_path=ARCHIVED_PATH,
            original=redacted, sha=None, redacted=("/cancelledAt",),
        )
        with self.assertRaises(ContractError):
            _projection(
                source, source_path=ARCHIVED_PATH, decision="redact",
                sidecar_raw=sidecar,
                task_raw=_task_md(
                    status="cancelled",
                    events=[dict(CANCELLED_EVENT, at="2026-02-10T15:30:00Z")],
                ),
            )
        projection = _projection(
            source, source_path=ARCHIVED_PATH, decision="redact", sidecar_raw=sidecar,
            task_raw=_task_md(status="cancelled", events=[CANCELLED_EVENT]),
        )
        self.assertEqual(projection.document.events[0]["at"], "unknown")
        self.assertEqual(projection.archive_bucket, "undated")

    def test_proven_cancellation_and_suspension_cannot_predate_creation(self):
        created_at = "2026-09-10T12:00:00Z"
        earlier = "2026-09-09T12:00:00Z"
        for status, event in (("cancelled", CANCELLED_EVENT), ("blocked", BLOCKED_EVENT)):
            source = _legacy_source(status=status, createdAt=created_at)
            kwargs = {}
            if status == "cancelled":
                source["cancelledAt"] = earlier
            else:
                source["meta"]["suspension"] = _suspension(since=earlier)
                kwargs["blocked_reason"] = "waiting on the upstream API key"
            with self.subTest(status=status), self.assertRaises(ContractError):
                _projection(
                    source,
                    task_raw=_task_md(
                        status=status, created_at=created_at,
                        events=[dict(event, at=earlier)], **kwargs,
                    ),
                )

    def test_proven_status_time_cannot_predate_date_only_creation_day(self):
        for status, event in (("cancelled", CANCELLED_EVENT), ("blocked", BLOCKED_EVENT)):
            for day in ("09", "10"):
                source = _legacy_source(status=status, createdAt="2026-09-10")
                timestamp = f"2026-09-{day}T12:00:00Z"
                kwargs = {}
                if status == "cancelled":
                    source["cancelledAt"] = timestamp
                else:
                    source["meta"]["suspension"] = _suspension(since=timestamp)
                    kwargs["blocked_reason"] = "waiting on the upstream API key"
                task = _task_md(
                    status=status, events=[dict(event, at=timestamp)], **kwargs
                )
                with self.subTest(status=status, day=day):
                    if day == "09":
                        with self.assertRaises(ContractError):
                            _projection(source, task_raw=task)
                    else:
                        projection = _projection(source, task_raw=task)
                        self.assertIsNone(projection.document.frontmatter["created_at"])
                        self.assertEqual(projection.document.events[0]["at"], timestamp)


def _beta_projection(children=("09-01-alpha",), parent=None, parent_id=None):
    source = _legacy_source(
        id="beta", name="beta", children=list(children), parent=parent
    )
    path = ".trellis/tasks/08-15-beta/task.json"
    raw = _json_bytes(source)
    document = _task_md(identity="beta", parent=parent_id)
    return validate_task_projection(
        raw,
        document,
        _sidecar(raw, source_path=path),
        source_path=path,
        decision="share",
    )


def _alpha_projection(parent=None, parent_id=None, children=()):
    source = _legacy_source(parent=parent, children=list(children))
    raw = _json_bytes(source)
    document = _task_md(parent=parent_id)
    return validate_task_projection(
        raw,
        document,
        _sidecar(raw, source_path=SOURCE_PATH),
        source_path=SOURCE_PATH,
        decision="share",
    )


def _cancelled_alpha(children=(), parent=None, parent_id=None):
    source = _legacy_source(
        status="cancelled",
        createdAt="2026-01-01",
        cancelledAt="2026-02-10T15:30:00Z",
        parent=parent,
        children=list(children),
    )
    path = ".trellis/tasks/archive/2026-02/09-01-alpha/task.json"
    document = _task_md(
        identity="alpha",
        status="cancelled",
        parent=parent_id,
        events=[dict(CANCELLED_EVENT, at="2026-02-10T15:30:00Z")],
    )
    raw = _json_bytes(source)
    return validate_task_projection(
        raw, document, _sidecar(raw, source_path=path),
        source_path=path, decision="share",
    )


def _blocked_beta(children=(), parent=None, parent_id=None):
    source = _legacy_source(
        id="beta",
        name="beta",
        status="blocked",
        meta={"suspension": _suspension()},
        createdAt="2026-01-01",
        parent=parent,
        children=list(children),
    )
    path = ".trellis/tasks/08-15-beta/task.json"
    document = _task_md(
        identity="beta",
        status="blocked",
        parent=parent_id,
        blocked_reason="waiting on the upstream API key",
        events=[dict(BLOCKED_EVENT, at="2026-08-20T09:30:00Z")],
    )
    raw = _json_bytes(source)
    return validate_task_projection(
        raw, document, _sidecar(raw, source_path=path),
        source_path=path, decision="share",
    )


class ProjectionGraphTests(unittest.TestCase):
    def test_parent_child_graph_resolves_through_real_legacy_names(self):
        alpha = _alpha_projection(parent="08-15-beta", parent_id="beta")
        beta = _beta_projection()
        validate_projection_graph({"alpha": alpha, "beta": beta})

    def test_missing_parent_and_half_links_are_rejected(self):
        alpha = _alpha_projection(parent="09-99-ghost", parent_id="ghost")
        with self.assertRaises(ContractError):
            validate_projection_graph({"alpha": alpha})
        child_without_link = _alpha_projection(parent="08-15-beta", parent_id="beta")
        with self.assertRaises(ContractError):
            validate_projection_graph(
                {"alpha": child_without_link, "beta": _beta_projection(children=())}
            )
        with self.assertRaises(ContractError):
            validate_projection_graph(
                {"alpha": _alpha_projection(), "beta": _beta_projection()}
            )
        mismatched_document = _alpha_projection(parent="08-15-beta", parent_id="gamma")
        with self.assertRaises(ContractError):
            validate_projection_graph(
                {"alpha": mismatched_document, "beta": _beta_projection()}
            )

    def test_relationship_cycles_are_rejected(self):
        alpha = _alpha_projection(
            parent="08-15-beta", parent_id="beta", children=("08-15-beta",)
        )
        beta = _beta_projection(
            children=("09-01-alpha",), parent="09-01-alpha", parent_id="alpha"
        )
        with self.assertRaises(ContractError):
            validate_projection_graph({"alpha": alpha, "beta": beta})

    def test_duplicate_names_and_mapping_mismatch_are_rejected(self):
        alpha = _alpha_projection()
        archived_twin = _done_projection(
            ".trellis/tasks/archive/2026-08/09-01-alpha/task.json",
            id="alpha-old",
            name="alpha-old",
        )
        with self.assertRaises(ContractError):
            validate_projection_graph({"alpha": alpha, "alpha-old": archived_twin})
        with self.assertRaises(ContractError):
            validate_projection_graph({"other": alpha})

    def test_parent_child_closure_across_cancelled_blocked_and_done(self):
        gamma_source = _legacy_source(
            id="gamma",
            name="gamma",
            status="completed",
            completedAt="2026-09-05",
            parent="09-01-alpha",
        )
        gamma_path = ".trellis/tasks/archive/2026-09/07-15-gamma/task.json"
        gamma_raw = _json_bytes(gamma_source)
        gamma = validate_task_projection(
            gamma_raw,
            _task_md(identity="gamma", status="done", parent="alpha",
                     events=[DONE_EVENT]),
            _sidecar(gamma_raw, source_path=gamma_path),
            source_path=gamma_path,
            decision="share",
        )
        alpha = _cancelled_alpha(children=("08-15-beta", "07-15-gamma"))
        beta = _blocked_beta(parent="09-01-alpha", parent_id="alpha")
        validate_projection_graph({"alpha": alpha, "beta": beta, "gamma": gamma})
        self.assertEqual(alpha.archive_bucket, "2026-Q1")
        with self.assertRaises(ContractError):
            validate_projection_graph(
                {"alpha": _cancelled_alpha(), "beta": beta, "gamma": gamma}
            )
        cyclic_alpha = _cancelled_alpha(
            children=("08-15-beta",), parent="08-15-beta", parent_id="beta"
        )
        cyclic_beta = _blocked_beta(
            children=("09-01-alpha",), parent="09-01-alpha", parent_id="alpha"
        )
        with self.assertRaises(ContractError):
            validate_projection_graph({"alpha": cyclic_alpha, "beta": cyclic_beta})


if __name__ == "__main__":
    unittest.main()

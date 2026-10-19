"""Historical observer authority across runtime-lineage rotation.

Regression coverage for late PR review finding 4236584337 (P2): cross-runtime
reconciled evidence produced while the installed signed pair authorized the
A→B observer must remain consumable after the installed pair rotates to B→C
under the unchanged trust key. The producer preserves the exact signed
object it was authorized by inside ``payload.reconciliation.observer_lineage``
(schema_version/purpose/predecessor/successor/signature; no trust key); the
consumer validates that embedded signature against the installed trusted key
and binds its endpoints to exactly manifest→observer, independent of the
current pair file. Legacy records without embedded proof keep the
same-runtime/current-pair fallback — and nothing more.

Everything runs on the genuine producer (``reconcile_deployment``) and the
genuine consumer (``verify_migration``) with real Ed25519 signatures under an
isolated per-test trust key. Signature verification and the authority guard
are never mocked; only the three native boundaries stay deterministic fixture
doubles, exactly as in ``tests.test_sbtd_reconciliation``.
"""

from __future__ import annotations

# ruff: noqa: I001 -- approved fixture imports bootstrap the local script path.

import base64
import contextlib
import dataclasses
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tests import test_sbtd_approved_agents_deployment as approved
from tests.test_sbtd_reconciliation import (
    _interrupted_deployment,
    _reconcile,
    _reseal_deployment_evidence,
)

import onboard_contracts as contracts
import sbtd_migration as migration
from onboard_contracts import canonical_json_bytes
from sbtd_migration_verify import verify_migration


def setUpModule():
    approved.setUpModule()


def tearDownModule():
    approved.tearDownModule()


def _runtime(base: dict, tag: str) -> dict:
    """One format-valid, distinct Onboard fingerprint over the sealed set."""
    return {**base, "onboard": "runtime-sha256:" + tag * 64}


class _LineageAuthority:
    """One isolated Ed25519 trust key whose pair document can rotate.

    Rotation re-signs a new pair under the SAME key, so the installed trust
    anchor never changes — only the pair document moves, exactly the rotation
    the finding describes. Signed bytes come from the production constructor
    ``migration._lineage_signed_bytes``, never a test-local shape.
    """

    def __init__(self, directory: Path) -> None:
        self._key = Ed25519PrivateKey.generate()
        self.public_path = directory / "lineage.pub"
        self.public_path.write_bytes(
            self._key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        self.pair_path = directory / "lineage.json"

    def sign(self, predecessor: str, successor: str) -> dict:
        signed = migration._lineage_signed_bytes(predecessor, successor)
        document = json.loads(signed)
        document["signature"] = base64.b64encode(self._key.sign(signed)).decode("ascii")
        return document

    def install(self, predecessor: str, successor: str) -> dict:
        document = self.sign(predecessor, successor)
        self.pair_path.write_bytes(canonical_json_bytes(document))
        return document


@contextlib.contextmanager
def _installed(authority: _LineageAuthority):
    """Point the consumer at this authority's trust key and pair document."""
    with (
        mock.patch.object(migration, "_LINEAGE_PUBLIC_KEY", authority.public_path),
        mock.patch.object(migration, "_LINEAGE_DOCUMENT", authority.pair_path),
    ):
        yield


def _verify(batch, manifest_path, apply_path, output_path):
    """The genuine read-only consumer, inside the batch environment."""
    with mock.patch.dict(os.environ, batch.environment):
        return verify_migration(manifest_path, apply_path, output_path)


@dataclasses.dataclass
class _Produced:
    """One genuinely produced cross-runtime observation and its context."""

    batch: approved._SignedBatch
    manifest_path: Path
    apply_path: Path
    missing_path: Path
    output_path: Path
    sealed: dict
    observer: dict
    successor: dict
    authority: _LineageAuthority
    pair_ab: dict
    reconciliation: dict


class HistoricalObserverLineageTests(unittest.TestCase):
    def _produce_cross_runtime_observation(self) -> _Produced:
        """Genuinely reconcile A-sealed history observed by successor B.

        The real producer runs while the installed pair authorizes A→B, so on
        a fixed producer the emitted evidence preserves that exact signed
        object in ``reconciliation.observer_lineage``.
        """
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        sealed = manifest["payload"]["tool_versions"]
        observer = _runtime(sealed, "a")
        successor = _runtime(sealed, "c")
        self.assertNotEqual(observer["onboard"], sealed["onboard"])
        self.assertNotEqual(successor["onboard"], observer["onboard"])
        authority = _LineageAuthority(batch.evidence)
        pair_ab = authority.install(sealed["onboard"], observer["onboard"])
        output_path = batch.evidence / "successor-observation.json"
        with (
            _installed(authority),
            mock.patch.object(migration, "runtime_versions", return_value=observer),
        ):
            result = _reconcile(
                batch, manifest, manifest_path, apply_path, missing_path, output_path
            )
        self.assertEqual(result["path"], str(output_path))
        reconciliation = json.loads(output_path.read_bytes())["payload"][
            "reconciliation"
        ]
        self.assertEqual(reconciliation["runtime_versions"], observer)
        return _Produced(
            batch=batch,
            manifest_path=manifest_path,
            apply_path=apply_path,
            missing_path=missing_path,
            output_path=output_path,
            sealed=sealed,
            observer=observer,
            successor=successor,
            authority=authority,
            pair_ab=pair_ab,
            reconciliation=reconciliation,
        )

    def test_rotated_pair_keeps_embedded_historical_observer_authority(self):
        produced = self._produce_cross_runtime_observation()

        # Rotation: the installed pair now authorizes B→C under the SAME,
        # unchanged trust key; the historical A→B authorization is gone from
        # the pair file.
        key_bytes = produced.authority.public_path.read_bytes()
        produced.authority.install(
            produced.observer["onboard"], produced.successor["onboard"]
        )
        self.assertEqual(produced.authority.public_path.read_bytes(), key_bytes)
        installed = json.loads(produced.authority.pair_path.read_bytes())
        self.assertEqual(
            (installed["predecessor"], installed["successor"]),
            (produced.observer["onboard"], produced.successor["onboard"]),
        )

        # Consumption as historical predecessor: the embedded proof, not the
        # rotated pair, must carry the observer's authority. The consumer
        # runs at the sealed manifest runtime, so no other lineage gate
        # intervenes; under the rotated pair the legacy fallback alone would
        # compare (B, C) against (A, B) and fail closed.
        with _installed(produced.authority):
            verified, code = _verify(
                produced.batch,
                produced.manifest_path,
                produced.apply_path,
                produced.output_path,
            )
        self.assertEqual(code, 0, verified)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(
            verified["migration"]["verification"]["payload"]["acceptance_basis"],
            "current-state",
        )
        self.assertFalse(produced.missing_path.exists())

    def test_tampered_embedded_observer_lineage_is_rejected(self):
        produced = self._produce_cross_runtime_observation()
        embedded = produced.reconciliation.get("observer_lineage")
        self.assertEqual(embedded, produced.pair_ab)
        observer_onboard = produced.observer["onboard"]
        successor_onboard = produced.successor["onboard"]
        foreign_onboard = "runtime-sha256:" + "d" * 64
        genuine_bytes = produced.output_path.read_bytes()
        manifest_before = produced.manifest_path.read_bytes()
        apply_before = produced.apply_path.read_bytes()

        def foreign_signature(document: dict) -> str:
            attacker = Ed25519PrivateKey.generate()
            signed = migration._lineage_signed_bytes(
                document["predecessor"], document["successor"]
            )
            return base64.b64encode(attacker.sign(signed)).decode("ascii")

        # Every mutation keeps the embedded object shape-valid; only its
        # truth changes. The installed pair stays A→B throughout, so the
        # current-pair fallback alone WOULD authorize the observer — each
        # rejection can only come from embedded-proof validation.
        mutations = {
            # Same endpoints, signature from an untrusted key: the installed
            # key is the only trust anchor.
            "foreign-key signature": lambda document: document.update(
                {"signature": foreign_signature(document)}
            ),
            # Well-formed but wrong signature bytes.
            "garbage signature": lambda document: document.update(
                {"signature": base64.b64encode(bytes(64)).decode("ascii")}
            ),
            # A GENUINE object signed by the trusted key, but for the rotated
            # B→C transition: valid signature, wrong endpoints for this
            # manifest→observer pair.
            "genuine signature, rotated endpoints": lambda document: document.update(
                produced.authority.sign(observer_onboard, successor_onboard)
            ),
            # Trusted-key signature over a foreign predecessor endpoint.
            "trusted key, foreign predecessor": lambda document: document.update(
                produced.authority.sign(foreign_onboard, observer_onboard)
            ),
        }

        # Baseline: the genuine record verifies under the still-installed
        # A→B pair, so each rejection below is caused by the tamper alone.
        with _installed(produced.authority):
            verified, code = _verify(
                produced.batch,
                produced.manifest_path,
                produced.apply_path,
                produced.output_path,
            )
        self.assertEqual(code, 0, verified)

        for name, mutate in mutations.items():
            with self.subTest(case=name):
                produced.output_path.write_bytes(genuine_bytes)

                def forge(payload: dict, mutate=mutate) -> None:
                    mutate(payload["reconciliation"]["observer_lineage"])

                _reseal_deployment_evidence(produced.output_path, forge)
                forged_bytes = produced.output_path.read_bytes()
                with (
                    _installed(produced.authority),
                    self.assertRaises(contracts.ContractError),
                ):
                    _verify(
                        produced.batch,
                        produced.manifest_path,
                        produced.apply_path,
                        produced.output_path,
                    )
                # Rejection is read-only: forged evidence stays as submitted,
                # cited inputs keep their bytes, the historical path stays
                # absent.
                self.assertEqual(produced.output_path.read_bytes(), forged_bytes)
                self.assertEqual(produced.manifest_path.read_bytes(), manifest_before)
                self.assertEqual(produced.apply_path.read_bytes(), apply_before)
                self.assertFalse(produced.missing_path.exists())

    def test_same_runtime_record_consumes_without_lineage_assets(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        result = _reconcile(
            batch, manifest, manifest_path, apply_path, missing_path, output_path
        )
        self.assertEqual(result["path"], str(output_path))
        reconciliation = json.loads(output_path.read_bytes())["payload"][
            "reconciliation"
        ]
        # The observer IS the manifest runtime: no cross-runtime
        # authorization exists to preserve, so nothing is embedded.
        self.assertEqual(
            reconciliation["runtime_versions"], manifest["payload"]["tool_versions"]
        )
        self.assertIsNone(reconciliation.get("observer_lineage"))

        # Both lineage assets point at never-created paths: consumption of a
        # same-runtime record must not consult them at all.
        with (
            mock.patch.object(
                migration, "_LINEAGE_PUBLIC_KEY", batch.evidence / "never.pub"
            ),
            mock.patch.object(
                migration, "_LINEAGE_DOCUMENT", batch.evidence / "never.json"
            ),
        ):
            verified, code = _verify(batch, manifest_path, apply_path, output_path)
        self.assertEqual(code, 0, verified)
        self.assertEqual(verified["status"], "verified")
        self.assertFalse(missing_path.exists())

    def test_legacy_record_without_proof_keeps_bounded_pair_fallback(self):
        produced = self._produce_cross_runtime_observation()
        # Strip the preserved proof and honestly reseal: exactly the legacy
        # pre-embedding record shape (the pop is a no-op against current
        # producers, which never embed).
        _reseal_deployment_evidence(
            produced.output_path,
            lambda payload: payload["reconciliation"].pop("observer_lineage", None),
        )
        legacy_bytes = produced.output_path.read_bytes()
        stripped = json.loads(legacy_bytes)["payload"]["reconciliation"]
        self.assertNotIn("observer_lineage", stripped)

        # Fallback retained: the still-installed A→B pair authorizes the
        # historical observer for a proof-less record.
        with _installed(produced.authority):
            verified, code = _verify(
                produced.batch,
                produced.manifest_path,
                produced.apply_path,
                produced.output_path,
            )
        self.assertEqual(code, 0, verified)
        self.assertEqual(verified["status"], "verified")

        # But the fallback stays bounded by the current pair: after rotation
        # a proof-less record has no authority left and must fail closed,
        # leaving the submitted bytes untouched.
        produced.authority.install(
            produced.observer["onboard"], produced.successor["onboard"]
        )
        with (
            _installed(produced.authority),
            self.assertRaises(contracts.ContractError) as failure,
        ):
            _verify(
                produced.batch,
                produced.manifest_path,
                produced.apply_path,
                produced.output_path,
            )
        self.assertEqual(failure.exception.code, "version-conflict")
        self.assertEqual(produced.output_path.read_bytes(), legacy_bytes)
        self.assertFalse(produced.missing_path.exists())


if __name__ == "__main__":
    unittest.main()

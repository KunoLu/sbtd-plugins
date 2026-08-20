from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "sbtd-workflow-onboard" / "templates" / "skills"
PROJECT_VALIDATION = SKILLS / "project-validation"
FIXTURES = ROOT / "tests" / "fixtures" / "validation-evidence" / "validation-evidence-v2"
VALIDATOR_PATH = PROJECT_VALIDATION / "scripts" / "validate_validation_evidence.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_validation_evidence", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load_validator()


class ValidationEvidenceV2Tests(unittest.TestCase):
    def test_v1_schema_and_ci_envelope_remain_valid(self) -> None:
        schema_path = PROJECT_VALIDATION / "references" / "validation-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "urn:sbtd:validation-evidence:schema:1")
        self.assertEqual(schema["properties"]["schemaVersion"], {"const": 1})
        envelope = {
            "schemaVersion": 1,
            "runId": "ci-smart-web-pr-123",
            "createdAt": "2026-07-17T00:00:00Z",
            "evidenceSource": "ci",
            "trigger": "pull-request",
            "repository": {
                "repositoryKey": "smart-web",
                "sourceRef": "refs/pull/123/head",
                "sourceCommit": "a" * 40,
                "worktreeState": "clean",
            },
            "sourceRevision": "exact",
            "environmentAlignment": "verified",
            "e2eMode": "full-stack",
            "mockStrategy": "none",
            "featureSources": [],
            "reports": [
                {
                    "testType": "web",
                    "path": "reports/web.html",
                    "summaryMd": "reports/web.md",
                    "sha256": "b" * 64,
                    "status": "passed",
                    "mode": "full-stack",
                }
            ],
            "evidencePublication": "published",
            "secretsRedacted": True,
        }
        jsonschema.Draft202012Validator(schema).validate(envelope)
        validator.validate_v1(envelope)

    def test_v2_schema_is_valid_draft_2020_12(self) -> None:
        schema = json.loads(
            (PROJECT_VALIDATION / "references" / "validation-evidence.v2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        self.assertEqual(schema["$id"], "urn:sbtd:validation-evidence:schema:2")

    def test_positive_fixtures_pass(self) -> None:
        for case in sorted(path for path in FIXTURES.iterdir() if path.name.startswith("positive-")):
            with self.subTest(case=case.name):
                envelope = json.loads((case / "envelope.json").read_text(encoding="utf-8"))
                validator.validate_v2(envelope, case)

    def test_negative_fixtures_fail_closed(self) -> None:
        expected = {
            "negative-dangling-locator": "DANGLING_LOCATOR",
            "negative-fabricated-label": "SELECTOR_ZERO_MATCH",
            "negative-failed-case": "CASE_NOT_PASSED",
            "negative-feature-directory": "FEATURE_NOT_FILE",
            "negative-missing-binding": "BINDING_MISSING",
            "negative-real-unrelated-passed-case": "BINDING_MISMATCH",
            "negative-tampered-hash": "REPORT_HASH_MISMATCH",
            "negative-unsafe-path": "UNSAFE_PATH",
            "negative-unsupported-html": "UNSUPPORTED_FORMAT",
            "negative-xxe-doctype": "XXE_OR_MALFORMED",
            "negative-xxe-entity": "XXE_OR_MALFORMED",
            "negative-xxe-junit": "XXE_OR_MALFORMED",
        }
        self.assertEqual(
            set(expected),
            {path.name for path in FIXTURES.iterdir() if path.name.startswith("negative-")},
        )
        for name, code in expected.items():
            case = FIXTURES / name
            envelope = json.loads((case / "envelope.json").read_text(encoding="utf-8"))
            with self.subTest(case=name):
                with self.assertRaises(validator.EvidenceError) as raised:
                    validator.validate_v2(envelope, case)
                self.assertEqual(raised.exception.code, code)

    def test_parse_junit_rejects_doctype_and_entity(self) -> None:
        digest = "a" * 64
        samples = {
            "doctype": b'<?xml version="1.0"?><!DOCTYPE testsuite><testsuite name="login"><testcase name="x"/></testsuite>',
            "internal_entity": b'<?xml version="1.0"?><!DOCTYPE testsuite [<!ENTITY hello "world">]><testsuite name="login"><testcase name="&hello;"/></testsuite>',
            "external_entity": b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><testsuite name="login"><testcase name="&xxe;"/></testsuite>',
        }
        for name, data in samples.items():
            with self.subTest(sample=name):
                with self.assertRaises(validator.EvidenceError) as raised:
                    validator.parse_junit(data)
                self.assertEqual(raised.exception.code, "XXE_OR_MALFORMED")

    def test_cli_positive_junit(self) -> None:
        case = FIXTURES / "positive-changed-junit"
        exit_code = validator.main(
            ["--envelope", str(case / "envelope.json"), "--root", str(case)]
        )
        self.assertEqual(exit_code, 0)

    def test_producer_skills_document_v1_v2_split(self) -> None:
        project = (PROJECT_VALIDATION / "SKILL.md").read_text(encoding="utf-8")
        contract = (
            PROJECT_VALIDATION / "references" / "validation-evidence-contract.md"
        ).read_text(encoding="utf-8")
        maestro = (SKILLS / "maestro-mobile-e2e" / "SKILL.md").read_text(encoding="utf-8")
        knowledge = (SKILLS / "knowledge-base-integration" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("validation-evidence.v2.schema.json", project)
        self.assertIn("validate_validation_evidence.py", project)
        self.assertIn("co-membership is not BDD traceability", project)
        self.assertIn("VALIDATOR_UNAVAILABLE", contract)
        self.assertIn("requirements.txt", contract)
        self.assertIn("sbtd.sourceLocatorDigest", contract)
        self.assertIn("drop empty and `.` segments", contract)
        self.assertIn("stripped and lowercased before hashing", contract)
        self.assertIn('serialize as JSON `null`, not `""`', contract)
        self.assertIn("hash this normalized payload", contract)
        self.assertIn("sbtd.sourceLocatorDigest", maestro)
        self.assertIn("from the installed `project-validation` Skill root", maestro)
        self.assertIn("mark v2 scenario execution evidence `blocked`", maestro)
        self.assertFalse((PROJECT_VALIDATION / "references" / "fixtures").exists())
        self.assertTrue(FIXTURES.is_dir())
        self.assertIn("schemaVersion: 1", knowledge)
        self.assertIn("must not be treated as BDD scenario coverage", knowledge)

    def test_missing_jsonschema_is_validator_unavailable(self) -> None:
        case = FIXTURES / "positive-changed-junit"
        envelope = json.loads((case / "envelope.json").read_text(encoding="utf-8"))
        original = validator.jsonschema
        validator.jsonschema = None
        try:
            with self.assertRaises(validator.EvidenceError) as raised:
                validator.validate_v2(envelope, case)
            self.assertEqual(raised.exception.code, "VALIDATOR_UNAVAILABLE")
        finally:
            validator.jsonschema = original

    def test_bundled_skill_copy_excludes_repo_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / "project-validation"
            shutil.copytree(PROJECT_VALIDATION, installed)
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue(
                (installed / "scripts" / "validate_validation_evidence.py").is_file()
            )
            self.assertFalse((installed / "references" / "fixtures").exists())
            self.assertFalse(
                any(installed.rglob("validation-evidence-v2"))
            )


if __name__ == "__main__":
    unittest.main()

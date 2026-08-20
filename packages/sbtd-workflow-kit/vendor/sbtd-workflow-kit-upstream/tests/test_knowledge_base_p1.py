from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "sbtd-workflow-onboard"
    / "templates"
    / "skills"
    / "knowledge-base-integration"
    / "scripts"
    / "knowledge_base_p1.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("knowledge_base_p1", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repo), *args),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def create_repo(root: Path, name: str, feature_text: str) -> tuple[Path, str]:
    repo = root / name
    repo.mkdir(parents=True)
    subprocess.run(
        ("git", "init", "-b", "main", str(repo)),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    git(repo, "config", "user.name", "P1 Test")
    git(repo, "config", "user.email", "p1-test@example.invalid")
    (repo / "features").mkdir()
    (repo / "features" / "behavior.feature").write_text(feature_text, encoding="utf-8")
    git(repo, "add", "features/behavior.feature")
    git(repo, "commit", "-m", "add behavior")
    staging_sha = git(repo, "rev-parse", "HEAD")
    git(repo, "branch", "staging", staging_sha)
    return repo, staging_sha


class KnowledgeBaseP1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def write_yaml(self, path: Path, value: str) -> Path:
        path.write_text(value.strip() + "\n", encoding="utf-8")
        return path

    def test_policy_resolver_keeps_product_requirement_and_adds_explicit_target(
        self,
    ) -> None:
        product = {
            "schema_version": 1,
            "product_key": "smart",
            "repositories": [
                {
                    "key": "smart-web",
                    "remote": "unused",
                    "role": "web",
                    "target_ref": "refs/heads/staging",
                    "feature_roots": ["features"],
                    "evidence_policy": {"pull_request": {"required": False}},
                }
            ],
            "evidence_policy": {
                "defaults": {
                    "pull_request": {
                        "required": True,
                        "targets": ["pull-request"],
                        "require_clean_worktree": True,
                        "require_exact_head_sha": True,
                    }
                }
            },
        }

        decision = self.module.resolve_evidence_decision(
            product,
            repository_key="smart-web",
            trigger="pull-request",
            execution_profile="developer-local",
            explicit_targets=["knowledge-base"],
        )

        self.assertEqual(decision["evidence_contract"], "required")
        self.assertEqual(
            decision["evidence_targets"], ["knowledge-base", "pull-request"]
        )
        self.assertTrue(decision["requirements"]["clean_worktree"])
        self.assertTrue(decision["requirements"]["exact_head_sha"])
        self.assertEqual(decision["decision_source"]["level"], "product-policy")
        self.assertRegex(decision["decision_digest"], r"^sha256:[0-9a-f]{64}$")

    def test_local_diagnostic_is_not_required_without_policy_or_target(self) -> None:
        product = {
            "schema_version": 1,
            "product_key": "smart",
            "repositories": [
                {
                    "key": "smart-web",
                    "remote": "unused",
                    "role": "web",
                    "target_ref": "refs/heads/staging",
                    "feature_roots": ["features"],
                }
            ],
        }

        decision = self.module.resolve_evidence_decision(
            product,
            repository_key="smart-web",
            trigger="local",
            execution_profile="developer-local",
        )

        self.assertEqual(decision["evidence_contract"], "not-required")
        self.assertEqual(decision["evidence_intent"], "not-needed")
        self.assertEqual(decision["evidence_targets"], [])

    def test_ci_profile_resolves_pull_request_evidence_policy(self) -> None:
        product = {
            "schema_version": 1,
            "product_key": "smart",
            "repositories": [
                {
                    "key": "smart-web",
                    "remote": "unused",
                    "role": "web",
                    "target_ref": "refs/heads/staging",
                    "feature_roots": ["features"],
                }
            ],
            "evidence_policy": {
                "defaults": {
                    "ci": {
                        "required": True,
                        "targets": ["pull-request"],
                        "require_clean_worktree": True,
                        "require_exact_head_sha": True,
                    }
                }
            },
        }

        decision = self.module.resolve_evidence_decision(
            product,
            repository_key="smart-web",
            trigger="pull-request",
            execution_profile="ci",
        )

        self.assertEqual(decision["execution_profile"], "ci")
        self.assertEqual(decision["evidence_contract"], "required")
        self.assertEqual(decision["evidence_targets"], ["pull-request"])
        self.assertTrue(decision["requirements"]["clean_worktree"])
        self.assertTrue(decision["requirements"]["exact_head_sha"])

    def test_ingest_reads_configured_ref_without_switching_active_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, staging_sha = create_repo(
                root,
                "web",
                """
# language: zh-CN
@smoke
功能: 处方订单
  场景: 缺少处方时拒绝提交
    假如 用户没有有效处方
    当 用户提交订单
    那么 系统拒绝创建订单
""".strip()
                + "\n",
            )
            (repo / "features" / "behavior.feature").write_text(
                "Feature: 当前工作区内容\n  Scenario: 不应被摄取\n    Given 当前分支已变化\n    When 读取 staging\n    Then 不应看见本场景\n",
                encoding="utf-8",
            )
            git(repo, "add", "features/behavior.feature")
            git(repo, "commit", "-m", "main changed")
            branch_before = git(repo, "branch", "--show-current")

            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-web
    remote: {repo.as_posix()}
    role: web
    target_ref: refs/heads/staging
    feature_roots:
      - features
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-web: web
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )
            output = root / "generated"

            summary = self.module.run_ingest(
                product_path,
                workspace_path,
                output,
                fetch=False,
                run_id="ingest-test",
            )

            self.assertEqual(summary["status"], "run")
            self.assertEqual(git(repo, "branch", "--show-current"), branch_before)
            self.assertEqual(summary["mutation"], "none")
            revision_set = json.loads((output / "revision-set.json").read_text())
            self.assertEqual(
                revision_set["repositories"][0]["resolved_commit"], staging_sha
            )
            scenarios = json.loads((output / "scenarios.json").read_text())
            self.assertEqual(len(scenarios), 1)
            self.assertEqual(scenarios[0]["name"], "缺少处方时拒绝提交")
            self.assertNotIn("feature_id", json.dumps(scenarios))
            self.assertNotIn("scenario_id", json.dumps(scenarios))
            locator = json.loads((output / "source-locators.json").read_text())[0]
            self.assertEqual(locator["source_commit"], staging_sha)
            self.assertEqual(locator["path"], "features/behavior.feature")
            self.assertTrue((output / "features.json").is_file())
            self.assertTrue((output / "overlaps.json").is_file())
            self.assertTrue((output / "conflicts.json").is_file())
            self.assertTrue((output / "ingest-summary.json").is_file())

    def test_parser_preserves_background_doc_strings_step_tables_and_examples(
        self,
    ) -> None:
        source = {
            "repository_key": "smart-web",
            "source_ref": "refs/heads/staging",
            "source_commit": "a" * 40,
            "path": "features/orders.feature",
        }
        features, scenarios, gaps = self.module.parse_gherkin(
            '''Feature: 订单提交
  Background: 已登录用户
    Given 用户已经登录
    And 用户拥有以下权限
      | permission | enabled |
      | order      | true    |

  Rule: 订单数据必须完整
    Scenario Outline: 缺少字段时拒绝提交
      Given 请求体为
        """application/json
        {"missing": "<field>"}
        """
      When 用户提交订单
      Then 返回参数错误

      @negative
      Examples: 必填字段
        | field |
        | name  |
''',
            source,
        )

        self.assertEqual(gaps, [])
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["backgrounds"][0]["name"], "已登录用户")
        background_step = features[0]["backgrounds"][0]["steps"][1]
        self.assertEqual(background_step["data_table"][1], ["order", "true"])
        self.assertEqual(len(scenarios), 1)
        self.assertEqual(scenarios[0]["background"], "已登录用户")
        self.assertEqual(
            scenarios[0]["steps"][0]["doc_string"]["media_type"], "application/json"
        )
        self.assertIn(
            '{"missing": "<field>"}', scenarios[0]["steps"][0]["doc_string"]["content"]
        )
        self.assertEqual(scenarios[0]["examples"][0]["tags"], ["@negative"])
        self.assertRegex(scenarios[0]["examples_fingerprint"], r"^sha256:[0-9a-f]{64}$")

    def test_ingest_reads_existing_binding_manifest_without_feature_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "web",
                "Feature: 登录\n  Scenario: 已注册用户登录\n    Given 用户存在\n    When 用户登录\n    Then 显示首页\n",
            )
            manifest = repo / "tests" / "e2e" / "manifest" / "ui-test-manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "tests": [
                            {
                                "scenario": "已注册用户登录",
                                "featurePath": "features/behavior.feature",
                                "testPath": "tests/e2e/login.spec.ts",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            git(repo, "add", manifest.relative_to(repo).as_posix())
            git(repo, "commit", "-m", "add binding manifest")
            staging_sha = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "-f", "staging", staging_sha)
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-web
    remote: {repo.as_posix()}
    role: web
    target_ref: refs/heads/staging
    feature_roots: [features]
    binding_manifests:
      - tests/e2e/manifest/ui-test-manifest.json
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-web: web
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )

            self.module.run_ingest(
                product_path,
                workspace_path,
                root / "generated",
                fetch=False,
                run_id="binding-manifest",
            )

            bindings = json.loads((root / "generated" / "bindings.json").read_text())
            self.assertEqual(len(bindings), 1)
            self.assertEqual(bindings[0]["method"], "manifest")
            self.assertEqual(bindings[0]["test_path"], "tests/e2e/login.spec.ts")
            self.assertEqual(bindings[0]["source"]["scenario"], "已注册用户登录")

    def test_ingest_reuses_deterministic_idempotency_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "web",
                "Feature: 登录\n  Scenario: 登录成功\n    Given 用户存在\n    When 用户登录\n    Then 显示首页\n",
            )
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-web
    remote: {repo.as_posix()}
    role: web
    target_ref: refs/heads/staging
    feature_roots: [features]
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-web: web
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )
            output = root / "generated"
            first = self.module.run_ingest(
                product_path, workspace_path, output, fetch=False, run_id="event-one"
            )
            second = self.module.run_ingest(
                product_path,
                workspace_path,
                root / "other-output",
                fetch=False,
                run_id="event-two",
            )

            self.assertRegex(first["idempotency_key"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(first["idempotency_key"], second["idempotency_key"])
            self.assertEqual(first["parser_version"], self.module.PARSER_VERSION)
            self.assertTrue(second["reused"])
            self.assertEqual(second["original_run_id"], "event-one")

    def test_smoke_retries_infrastructure_failure_and_deduplicates_same_attempt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "backend",
                "Feature: 健康检查\n  Scenario: 服务可用\n    Given 服务启动\n    When 检查服务\n    Then 返回成功\n",
            )
            counter = root / "counter.txt"
            script = repo / "retry_smoke.py"
            script.write_text(
                "from pathlib import Path\n"
                f"counter=Path({str(counter)!r})\n"
                "count=int(counter.read_text()) if counter.exists() else 0\n"
                "count += 1\n"
                "counter.write_text(str(count))\n"
                "if count == 1: raise SystemExit(75)\n"
                "p=Path('reports'); p.mkdir(exist_ok=True)\n"
                "(p/'api.xml').write_text('<testsuite/>', encoding='utf-8')\n"
                "(p/'api.md').write_text('# 测试汇总\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            git(repo, "add", "retry_smoke.py")
            git(repo, "commit", "-m", "add retry smoke")
            staging_sha = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "-f", "staging", staging_sha)
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-backend
    remote: {repo.as_posix()}
    role: backend
    target_ref: refs/heads/staging
    feature_roots: [features]
smoke:
  retry_policy:
    infrastructure: 1
  commands:
    smart-backend:
      - key: api-smoke
        command: [python3, retry_smoke.py]
        infrastructure_exit_codes: [75]
        reports:
          - path: reports/*.xml
            summary_md: reports/*.md
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-backend: backend
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )
            first = self.module.run_smoke(
                product_path,
                workspace_path,
                root / "output-one",
                trigger="schedule",
                execution_profile="knowledge-server",
                fetch=False,
                run_id="event-one",
                suite_key="smoke",
                attempt=1,
            )
            second = self.module.run_smoke(
                product_path,
                workspace_path,
                root / "output-two",
                trigger="schedule",
                execution_profile="knowledge-server",
                fetch=False,
                run_id="event-two",
                suite_key="smoke",
                attempt=1,
            )

            self.assertEqual(first["status"], "passed")
            self.assertEqual(counter.read_text(), "2")
            attempts = first["runs"][0]["commands"][0]["attempts"]
            self.assertEqual(
                [item["failure_class"] for item in attempts], ["infrastructure", "none"]
            )
            self.assertTrue(second["reused"])
            self.assertEqual(counter.read_text(), "2")

    def test_required_repository_with_missing_ref_blocks_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "web",
                "Feature: 登录\n  Scenario: 登录成功\n    Given 用户存在\n    When 用户登录\n    Then 显示首页\n",
            )
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-web
    remote: {repo.as_posix()}
    role: web
    target_ref: refs/heads/missing
    feature_roots: [features]
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-web: web
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )

            summary = self.module.run_ingest(
                product_path,
                workspace_path,
                root / "generated",
                fetch=False,
                run_id="missing-ref",
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(summary["repositories"][0]["status"], "blocked")
            self.assertNotEqual(
                summary["repositories"][0].get("resolved_commit"),
                git(repo, "rev-parse", "HEAD"),
            )

    def test_optional_repository_without_workspace_mapping_makes_ingest_partial(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "web",
                "Feature: 登录\n  Scenario: 登录成功\n    Given 用户存在\n    When 用户登录\n    Then 显示首页\n",
            )
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-web
    remote: {repo.as_posix()}
    role: web
    target_ref: refs/heads/staging
    feature_roots: [features]
  - key: smart-mobile
    remote: ssh://git.example/smart/mobile.git
    role: mobile
    target_ref: refs/heads/staging
    feature_roots: [features]
    optional: true
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-web: web
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )

            result = self.module.run_ingest(
                product_path, workspace_path, root / "output", fetch=False
            )

            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["repositories"][1]["status"], "blocked")

    def test_required_environment_alignment_rejects_untrusted_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "backend",
                "Feature: 健康检查\n  Scenario: 服务可用\n    Given 服务启动\n    When 检查服务\n    Then 返回成功\n",
            )
            script = repo / "smoke.py"
            script.write_text(
                "from pathlib import Path\n"
                "p=Path('reports'); p.mkdir(exist_ok=True)\n"
                "(p/'api.xml').write_text('<testsuite/>', encoding='utf-8')\n"
                "(p/'api.md').write_text('# 测试汇总\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            git(repo, "add", "smoke.py")
            git(repo, "commit", "-m", "add smoke")
            staging_sha = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "-f", "staging", staging_sha)
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-backend
    remote: {repo.as_posix()}
    role: backend
    target_ref: refs/heads/staging
    feature_roots: [features]
evidence_policy:
  defaults:
    knowledge_server:
      required: true
      targets: [knowledge-base]
      require_environment_alignment: true
smoke:
  commands:
    smart-backend:
      - key: api
        command: [python3, smoke.py]
        reports:
          - path: reports/api.xml
            summary_md: reports/api.md
""",
            )
            trusted = root / "trusted"
            trusted.mkdir()
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-backend: backend
runtime_root: {(root / ".kb-runtime").as_posix()}
trust:
  deployment_metadata_roots: [{trusted.as_posix()}]
  allowed_issuers: [deployment-controller]
local_runner:
  id: local-linux
  version: '1.0.0'
  image_digest: sha256:{"1" * 64}
  labels: []
  tools: {{}}
""",
            )
            base = {
                "schema_version": 1,
                "repositories": {"smart-backend": staging_sha},
                "runners": {
                    "local": {
                        "id": "local-linux",
                        "version": "1.0.0",
                        "image_digest": "sha256:" + "1" * 64,
                        "labels": [],
                        "tools": {},
                    }
                },
                "attestation": {
                    "issuer": "deployment-controller",
                    "issued_at": "2026-07-17T00:00:00Z",
                },
            }
            manifest = {
                **base,
                "attestation": {
                    **base["attestation"],
                    "manifest_digest": self.module.canonical_digest(base),
                },
            }
            untrusted_manifest = root / "untrusted.json"
            untrusted_manifest.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.module.run_smoke(
                product_path,
                workspace_path,
                root / "output",
                trigger="schedule",
                fetch=False,
                deployment_manifest_path=untrusted_manifest,
            )

            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["runs"][0]["environment_alignment"], "unverified")

    def test_smoke_uses_detached_worktree_and_generates_evidence_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, staging_sha = create_repo(
                root,
                "backend",
                "Feature: 健康检查\n  Scenario: 服务可用\n    Given 服务已经启动\n    When 调用健康检查\n    Then 返回成功\n",
            )
            script = repo / "smoke.py"
            script.write_text(
                "from pathlib import Path\n"
                "p=Path('reports'); p.mkdir(exist_ok=True)\n"
                "(p/'api.xml').write_text('<testsuite tests=\"1\" failures=\"0\"/>', encoding='utf-8')\n"
                "(p/'api.md').write_text('# 测试汇总\\n\\n- 状态：passed\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            git(repo, "add", "smoke.py")
            git(repo, "commit", "-m", "add smoke command")
            staging_sha = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "-f", "staging", staging_sha)
            branch_before = git(repo, "branch", "--show-current")

            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-backend
    remote: {repo.as_posix()}
    role: backend
    target_ref: refs/heads/staging
    feature_roots: [features]
evidence_policy:
  defaults:
    knowledge_server:
      required: true
      targets: [knowledge-base]
      require_revision_set: true
      require_environment_alignment: true
smoke:
  commands:
    smart-backend:
      - key: api-smoke
        command: [python3, smoke.py]
        test_type: api
        mode: smoke-only
        reports:
          - path: reports/*.xml
            summary_md: reports/*.md
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-backend: backend
runtime_root: {(root / ".kb-runtime").as_posix()}
trust:
  deployment_metadata_roots: [{root.as_posix()}]
  allowed_issuers: [deployment-controller]
local_runner:
  id: local-linux
  version: '1.0.0'
  image_digest: sha256:{"1" * 64}
  labels: [api, linux]
  tools:
    python: '3'
""",
            )
            output = root / "smoke-output"
            deployment_base = {
                "schema_version": 1,
                "environment": "staging",
                "repositories": {"smart-backend": staging_sha},
                "runners": {
                    "local": {
                        "id": "local-linux",
                        "version": "1.0.0",
                        "image_digest": "sha256:" + "1" * 64,
                        "labels": ["api", "linux"],
                        "tools": {"python": "3"},
                    }
                },
                "attestation": {
                    "issuer": "deployment-controller",
                    "issued_at": "2026-07-17T00:00:00Z",
                },
            }
            deployment_manifest_value = {
                **deployment_base,
                "attestation": {
                    **deployment_base["attestation"],
                    "manifest_digest": self.module.canonical_digest(deployment_base),
                },
            }
            deployment_manifest = root / "deployment.json"
            deployment_manifest.write_text(
                json.dumps(deployment_manifest_value), encoding="utf-8"
            )

            result = self.module.run_smoke(
                product_path,
                workspace_path,
                output,
                trigger="schedule",
                execution_profile="knowledge-server",
                fetch=False,
                run_id="smoke-test",
                deployment_manifest_path=deployment_manifest,
            )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(git(repo, "branch", "--show-current"), branch_before)
            self.assertEqual(
                result["revision_set"]["repositories"][0]["resolved_commit"],
                staging_sha,
            )
            envelope_path = output / "evidence-smart-backend.json"
            envelope = json.loads(envelope_path.read_text())
            self.assertEqual(envelope["evidenceSource"], "knowledge-server")
            self.assertEqual(envelope["sourceRevision"], "exact")
            self.assertEqual(envelope["repository"]["sourceCommit"], staging_sha)
            self.assertEqual(envelope["evidenceTargets"], ["knowledge-base"])
            self.assertEqual(envelope["environmentAlignment"], "verified")
            self.assertEqual(envelope["runnerAttestations"][0]["id"], "local-linux")
            self.assertEqual(envelope["evidencePublication"], "not-configured")
            self.assertEqual(envelope["reports"][0]["testType"], "api")
            self.assertTrue((output / envelope["reports"][0]["path"]).is_file())
            self.assertTrue((output / envelope["reports"][0]["summaryMd"]).is_file())
            self.assertRegex(
                envelope["artifactManifestDigest"], r"^sha256:[0-9a-f]{64}$"
            )
            artifact_manifest = json.loads(
                (output / envelope["artifactManifest"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                artifact_manifest["manifest_digest"], envelope["artifactManifestDigest"]
            )
            self.assertEqual(len(artifact_manifest["artifacts"]), 2)
            self.assertTrue(
                all(item["size"] > 0 for item in artifact_manifest["artifacts"])
            )
            checksums = (output / envelope["checksumsFile"]).read_text(encoding="utf-8")
            self.assertIn(envelope["reports"][0]["sha256"], checksums)
            self.assertFalse(
                (root / ".kb-runtime" / "worktrees" / "smoke-test").exists()
            )

            ci_output = root / "smoke-ci-output"
            ci_result = self.module.run_smoke(
                product_path,
                workspace_path,
                ci_output,
                trigger="pull-request",
                execution_profile="ci",
                fetch=False,
                run_id="smoke-ci-test",
                deployment_manifest_path=deployment_manifest,
            )
            self.assertEqual(ci_result["status"], "passed")
            ci_envelope = json.loads(
                (ci_output / "evidence-smart-backend.json").read_text()
            )
            self.assertEqual(ci_envelope["evidenceSource"], "ci")
            self.assertEqual(ci_envelope["sourceRevision"], "exact")
            self.assertEqual(ci_envelope["repository"]["worktreeState"], "clean")

            broken_product = root / "product-broken.yaml"
            broken_product.write_text(
                product_path.read_text(encoding="utf-8")
                .replace("reports/*.xml", "reports/missing*.xml")
                .replace("reports/*.md", "reports/missing*.md"),
                encoding="utf-8",
            )
            blocked = self.module.run_smoke(
                broken_product,
                workspace_path,
                root / "smoke-blocked",
                trigger="schedule",
                execution_profile="knowledge-server",
                fetch=False,
                run_id="smoke-blocked",
                deployment_manifest_path=deployment_manifest,
                attempt=2,
            )
            self.assertEqual(blocked["status"], "blocked")
            self.assertIn("current command", blocked["runs"][0]["reason"])
            self.assertFalse(
                (root / ".kb-runtime" / "worktrees" / "smoke-blocked").exists()
            )

    def test_smoke_rejects_stale_or_non_chinese_report_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "backend",
                "Feature: 健康检查\n  Scenario: 服务可用\n    Given 服务启动\n    When 检查服务\n    Then 返回成功\n",
            )
            reports = repo / "reports"
            reports.mkdir()
            (reports / "api.xml").write_text("<testsuite/>", encoding="utf-8")
            (reports / "api.md").write_text(
                "# Test summary\n\n- Status: passed\n", encoding="utf-8"
            )
            git(repo, "add", "reports/api.xml", "reports/api.md")
            git(repo, "commit", "-m", "add stale reports")
            staging_sha = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "-f", "staging", staging_sha)
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-backend
    remote: {repo.as_posix()}
    role: backend
    target_ref: refs/heads/staging
    feature_roots: [features]
evidence_policy:
  defaults:
    knowledge_server:
      required: true
      targets: [knowledge-base]
smoke:
  commands:
    smart-backend:
      - key: api-smoke
        command: [python3, -c, "pass"]
        reports:
          - path: reports/*.xml
            summary_md: reports/*.md
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-backend: backend
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )

            result = self.module.run_smoke(
                product_path,
                workspace_path,
                root / "output",
                trigger="schedule",
                execution_profile="knowledge-server",
                fetch=False,
                run_id="stale-report",
            )

            self.assertEqual(result["status"], "blocked")
            self.assertIn("current command", result["runs"][0]["reason"])
            self.assertFalse(
                (root / "output" / "artifact-manifest-smart-backend.json").exists()
            )

    def test_command_runner_adapter_dispatches_exact_revision_and_collects_mobile_report(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, staging_sha = create_repo(
                root,
                "mobile",
                "Feature: 移动端登录\n  Scenario: 用户登录\n    Given App 已启动\n    When 用户登录\n    Then 显示首页\n",
            )
            bridge = root / "runner_bridge.py"
            bridge.write_text(
                "import json, sys\n"
                "from pathlib import Path\n"
                "job=Path(sys.argv[1]); result=Path(sys.argv[2]); artifacts=Path(sys.argv[3])\n"
                "payload=json.loads(job.read_text())\n"
                "assert payload['revision_set']['repositories'][0]['resolved_commit'] == payload['repository']['resolved_commit']\n"
                "artifacts.mkdir(parents=True, exist_ok=True)\n"
                "(artifacts/'mobile.xml').write_text('<testsuite/>', encoding='utf-8')\n"
                "(artifacts/'mobile.md').write_text('# 移动测试汇总\\n', encoding='utf-8')\n"
                "result.write_text(json.dumps({\n"
                " 'schema_version': 1, 'status': 'passed', 'failure_class': 'none', 'exit_code': 0,\n"
                " 'queue_latency_ms': 12,\n"
                " 'runner': {'id':'android-01','version':'2.1.0','image_digest':'sha256:'+'2'*64,'labels':['android','java17','maestro'],'tools':{'maestro':'2.0.0'}},\n"
                " 'reports': [{'path':'artifacts/mobile.xml','summary_md':'artifacts/mobile.md','test_type':'mobile','mode':'smoke-only'}]\n"
                "}), encoding='utf-8')\n",
                encoding="utf-8",
            )
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-mobile
    remote: {repo.as_posix()}
    role: mobile
    target_ref: refs/heads/staging
    feature_roots: [features]
evidence_policy:
  defaults:
    knowledge_server:
      required: true
      targets: [knowledge-base]
smoke:
  commands:
    smart-mobile:
      - key: mobile-smoke
        runner: android
        command: [maestro, test, maestro/flow/smoke.yml]
        required_runner_labels: [android, java17, maestro]
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-mobile: mobile
runtime_root: {(root / ".kb-runtime").as_posix()}
runners:
  android:
    adapter: command
    labels: [android, java17, maestro]
    command:
      - python3
      - {bridge.as_posix()}
      - '{{job_manifest}}'
      - '{{result_manifest}}'
      - '{{artifact_dir}}'
""",
            )

            result = self.module.run_smoke(
                product_path,
                workspace_path,
                root / "output",
                trigger="schedule",
                execution_profile="knowledge-server",
                fetch=False,
                run_id="mobile-runner",
            )

            self.assertEqual(result["status"], "passed")
            command = result["runs"][0]["commands"][0]
            self.assertEqual(command["runner"], "android")
            self.assertEqual(command["queue_latency_ms"], 12)
            envelope = json.loads(
                (root / "output" / "evidence-smart-mobile.json").read_text()
            )
            self.assertEqual(envelope["runnerAttestations"][0]["id"], "android-01")
            self.assertEqual(envelope["reports"][0]["testType"], "mobile")
            job = json.loads(
                next(
                    (root / "output" / "jobs" / "smart-mobile" / "mobile-smoke").glob(
                        "*/job.json"
                    )
                ).read_text()
            )
            self.assertEqual(job["repository"]["resolved_commit"], staging_sha)
            metrics = json.loads((root / "output" / "metrics.json").read_text())
            self.assertEqual(metrics["counters"]["remote_runner_commands"], 1)

    def test_smoke_phase_failure_skips_tests_but_always_runs_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "backend",
                "Feature: 健康检查\n  Scenario: 服务可用\n    Given 服务启动\n    When 检查服务\n    Then 返回成功\n",
            )
            lifecycle = root / "lifecycle.txt"
            test_marker = root / "test-ran.txt"
            phase = repo / "phase.py"
            phase.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                f"log=Path({str(lifecycle)!r})\n"
                "log.write_text(log.read_text() + sys.argv[1] + '\\n' if log.exists() else sys.argv[1] + '\\n')\n"
                f"marker=Path({str(test_marker)!r})\n"
                "if sys.argv[1] == 'preflight': raise SystemExit(75)\n"
                "if sys.argv[1] == 'test': marker.write_text('ran')\n",
                encoding="utf-8",
            )
            git(repo, "add", "phase.py")
            git(repo, "commit", "-m", "add phases")
            staging_sha = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "-f", "staging", staging_sha)
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-backend
    remote: {repo.as_posix()}
    role: backend
    target_ref: refs/heads/staging
    feature_roots: [features]
smoke:
  commands:
    smart-backend:
      - key: test
        stage: test
        command: [python3, phase.py, test]
      - key: cleanup
        stage: cleanup
        command: [python3, phase.py, cleanup]
      - key: preflight
        stage: preflight
        command: [python3, phase.py, preflight]
        infrastructure_exit_codes: [75]
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-backend: backend
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )

            result = self.module.run_smoke(
                product_path,
                workspace_path,
                root / "output",
                trigger="schedule",
                fetch=False,
                run_id="phase-test",
            )

            self.assertEqual(result["status"], "blocked")
            commands = result["runs"][0]["commands"]
            self.assertEqual(
                [(item["stage"], item["status"]) for item in commands],
                [("preflight", "blocked"), ("test", "skipped"), ("cleanup", "passed")],
            )
            self.assertEqual(
                lifecycle.read_text().splitlines(), ["preflight", "cleanup"]
            )
            self.assertFalse(test_marker.exists())

    def test_multi_repository_ingest_and_api_web_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            web, web_sha = create_repo(
                root,
                "web",
                "Feature: 订单提交\n  Scenario: 提交订单\n    Given 订单完整\n    When 用户提交\n    Then 页面显示成功\n",
            )
            backend, backend_sha = create_repo(
                root,
                "backend",
                "Feature: 订单提交接口\n  Scenario: 提交订单\n    Given 订单完整\n    When 用户提交\n    Then API 返回订单编号\n",
            )
            for repo, test_type in ((web, "web"), (backend, "api")):
                script = repo / "smoke.py"
                script.write_text(
                    "from pathlib import Path\n"
                    "p=Path('reports'); p.mkdir(exist_ok=True)\n"
                    f"(p/'{test_type}.xml').write_text('<testsuite/>', encoding='utf-8')\n"
                    f"(p/'{test_type}.md').write_text('# {test_type} 测试汇总\\n', encoding='utf-8')\n",
                    encoding="utf-8",
                )
                git(repo, "add", "smoke.py")
                git(repo, "commit", "-m", "add smoke")
                sha = git(repo, "rev-parse", "HEAD")
                git(repo, "branch", "-f", "staging", sha)
                if repo == web:
                    web_sha = sha
                else:
                    backend_sha = sha
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-web
    remote: {web.as_posix()}
    role: web
    target_ref: refs/heads/staging
    feature_roots: [features]
  - key: smart-backend
    remote: {backend.as_posix()}
    role: backend
    target_ref: refs/heads/staging
    feature_roots: [features]
evidence_policy:
  defaults:
    knowledge_server:
      required: true
      targets: [knowledge-base]
smoke:
  commands:
    smart-web:
      - key: web-smoke
        command: [python3, smoke.py]
        test_type: web
        reports:
          - path: reports/web.xml
            summary_md: reports/web.md
    smart-backend:
      - key: api-smoke
        command: [python3, smoke.py]
        test_type: api
        reports:
          - path: reports/api.xml
            summary_md: reports/api.md
""",
            )
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-web: web
  smart-backend: backend
runtime_root: {(root / ".kb-runtime").as_posix()}
""",
            )
            ingest_output = root / "ingest"
            ingest = self.module.run_ingest(
                product_path,
                workspace_path,
                ingest_output,
                fetch=False,
                run_id="multi-ingest",
            )
            self.assertEqual(ingest["status"], "run")
            revisions = json.loads((ingest_output / "revision-set.json").read_text())[
                "repositories"
            ]
            self.assertEqual(
                {item["repository_key"]: item["resolved_commit"] for item in revisions},
                {"smart-web": web_sha, "smart-backend": backend_sha},
            )
            self.assertEqual(ingest["overlap_count"], 1)
            self.assertEqual(ingest["conflict_count"], 1)

            smoke_output = root / "smoke"
            smoke = self.module.run_smoke(
                product_path,
                workspace_path,
                smoke_output,
                trigger="schedule",
                fetch=False,
                run_id="api-web-smoke",
            )
            self.assertEqual(smoke["status"], "passed")
            web_envelope = json.loads(
                (smoke_output / "evidence-smart-web.json").read_text()
            )
            api_envelope = json.loads(
                (smoke_output / "evidence-smart-backend.json").read_text()
            )
            self.assertEqual(web_envelope["reports"][0]["testType"], "web")
            self.assertEqual(api_envelope["reports"][0]["testType"], "api")

    def test_smoke_reclaims_stale_run_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = create_repo(
                root,
                "backend",
                "Feature: 健康检查\n  Scenario: 服务可用\n    Given 服务启动\n    When 检查服务\n    Then 返回成功\n",
            )
            product_path = self.write_yaml(
                root / "product.yaml",
                f"""
schema_version: 1
product_key: smart
repositories:
  - key: smart-backend
    remote: {repo.as_posix()}
    role: backend
    target_ref: refs/heads/staging
    feature_roots: [features]
""",
            )
            runtime = root / ".kb-runtime"
            workspace_path = self.write_yaml(
                root / "workspace.local.yaml",
                f"""
schema_version: 1
product_key: smart
product_root: {root.as_posix()}
paths:
  smart-backend: backend
runtime_root: {runtime.as_posix()}
""",
            )
            stale_lock = runtime / "locks" / "stale-run"
            stale_lock.mkdir(parents=True)
            (stale_lock / "owner.json").write_text(
                json.dumps({"schema_version": 1, "pid": 99999999}), encoding="utf-8"
            )
            orphan = runtime / "worktrees" / "stale-run" / "smart-backend"
            orphan.mkdir(parents=True)

            result = self.module.run_smoke(
                product_path,
                workspace_path,
                root / "output",
                trigger="schedule",
                fetch=False,
                run_id="stale-run",
            )

            self.assertEqual(result["status"], "passed")
            self.assertFalse(stale_lock.exists())
            self.assertFalse(orphan.exists())

    def test_smoke_does_not_reclaim_a_live_run_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = root / "locks" / "live-run"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps({"schema_version": 1, "pid": os.getpid()}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(self.module.P1Error, "already locked"):
                self.module.acquire_run_lock(
                    lock,
                    root / "worktrees" / "live-run",
                    {"product_key": "smart"},
                    {"runtime_root": str(root)},
                )

            self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()

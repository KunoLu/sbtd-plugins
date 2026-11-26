import { createHash } from "node:crypto";
import {
  cp,
  lstat,
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  createNodeFileSystem,
  inspectPackageMetadata,
  type P0FileSystem,
  verifyEmbeddedKitReleaseIntegrity,
  verifyPluginReleaseArtifacts,
  writePluginSpdxSbom,
} from "../scripts/p0/release-validator.ts";
import type { EmbeddedKitManifestV2 } from "../src/kit/manifest.ts";
import { readReleaseFixture } from "./fixtures/release-fixtures.ts";

const packageRoot = fileURLToPath(new URL("../", import.meta.url));
const workspaceRoot = fileURLToPath(new URL("../../../", import.meta.url));
const stableRoot = "onboard/runtime/assets/external-skills/stable";
const ledgerPath = `${stableRoot}/MANIFEST.json`;
const stableNoticePath = `${stableRoot}/THIRD_PARTY_NOTICES.md`;
const adrPath = `${stableRoot}/skills/domain-modeling/ADR-FORMAT.md`;
const r1Repository = "mattpocock-skills-r1-manuals";
const r1Root =
  "871756771756195451b3c2343e05a3cdf5c04c0d8033a1352f59584b03212e63";
const r1RawLedger =
  "4eed938088d7415f2dbcac7a2a576baa9cbbc179184fca484493f54ef60e13ad";
const r1SemanticLedger =
  "b4cc88099e80ac0a7f20909d30fc2cbfaa8deaeef1ca4fd443ef1aef7c08f3d4";
const pairedMessage =
  "The complete asset/overlay identity is not paired with its reviewed ledger/profile.";
const semanticMessage =
  "The complete retained source ledger is not the reviewed R1 identity.";
const overlayMessage =
  "The R1 overlay set is not the exact reviewed first-party identity.";
const canonicalMessage =
  "The R1 canonical source or projection contract is not the exact reviewed identity.";
const mhMessage =
  "Embedded Kit does not satisfy the schema-v2 projection integrity contract.";
const temporaryRoots: string[] = [];
const sha256 = (bytes: string | Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
const jsonBytes = (value: unknown) =>
  Buffer.from(`${JSON.stringify(value, null, 2)}\n`);

// Independent reviewed 2133 full-asset map (reviewy-r1-two-skills-review §3/§5).
// This is inert expected data, not imported from the production trust profile.
const expectedKitLicenses: Readonly<Record<string, "Apache-2.0" | "MIT">> = {
  "AGENTS.global.md": "Apache-2.0",
  "AGENTS.project-omp.md": "Apache-2.0",
  "AGENTS.project-root.md": "Apache-2.0",
  "catalog.json": "Apache-2.0",
  LICENSE: "Apache-2.0",
  "onboard/runtime/assets/external-skills/stable/licenses/mattpocock-skills-LICENSE":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/licenses/ponytail-LICENSE":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/licenses/ui-ux-pro-max-skill-LICENSE":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/MANIFEST.json": "Apache-2.0",
  "onboard/runtime/assets/external-skills/stable/skills/codebase-design/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/codebase-design/DEEPENING.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/codebase-design/DESIGN-IT-TWICE.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/codebase-design/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/scripts/hitl-loop.template.sh":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/diagnosing-bugs/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/ADR-FORMAT.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/GLOSSARY-FORMAT.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/grill-me/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/grill-me/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/grill-with-docs/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/grill-with-docs/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/grilling/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/grilling/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/handoff/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/handoff/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ponytail-audit/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ponytail-debt/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ponytail-review/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ponytail/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/tdd/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/tdd/mocking.md": "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/tdd/SKILL.md": "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/tdd/tests.md": "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/to-spec/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/to-spec/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/to-tickets/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/to-tickets/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/app-interface.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/catalog-summary.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/charts.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/colors.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/data-provenance.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/google-font-licenses.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/google-fonts.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/icons.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/landing.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/motion.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/phosphor-icons-upstream.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/products.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/react-performance.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/angular.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/astro.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/avalonia.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/flutter.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/html-tailwind.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/javafx.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/jetpack-compose.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/laravel.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nextjs.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nuxt-ui.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/nuxtjs.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/react-native.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/react.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/shadcn.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/svelte.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/swiftui.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/threejs.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/uno.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/uwp.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/vue.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/winui.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/stacks/wpf.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/styles.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/typography.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/ui-reasoning.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/ux-guidelines.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/references/pro-rules.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/references/quick-reference.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/core.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/design_system.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/reasoning_contract.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/search.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-api.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-catalog.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-existing.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-metadata.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-overrides.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/icons-curated.csv":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-core.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-package.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-exports.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-package.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-baseline.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-cases.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/fixtures/relevance-thresholds.json":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_catalog_refresh.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_catalog_summary_line_endings.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_core_data_quality.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_core.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_data_contracts.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_design_system_mode.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_design_system_stack.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_native_desktop_stack_freshness.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_relevance_evaluator.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_skill_script_paths.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_style_taxonomy.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_text_layout_resilience.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_web_stack_freshness.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/validate_data.py":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/agents/openai.yaml":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/SKILL-MECHANICS.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/skills/writing-for-agents/SKILL.md":
    "MIT",
  "onboard/runtime/assets/external-skills/stable/THIRD_PARTY_NOTICES.md":
    "Apache-2.0",
  "onboard/runtime/assets/graft-build-policy.json": "Apache-2.0",
  "onboard/runtime/assets/graft-hook-entry.mjs": "Apache-2.0",
  "onboard/runtime/assets/graft-instructions.txt": "Apache-2.0",
  "onboard/runtime/assets/migration-legacy-ownership.json": "Apache-2.0",
  "onboard/runtime/assets/migration-local-ignore.txt": "Apache-2.0",
  "onboard/runtime/assets/migration-paused-agents.txt": "Apache-2.0",
  "onboard/runtime/assets/routing-approval.pub": "Apache-2.0",
  "onboard/runtime/assets/runtime-lineage.json": "Apache-2.0",
  "onboard/runtime/assets/runtime-lineage.pub": "Apache-2.0",
  "onboard/runtime/catalog.json": "Apache-2.0",
  "onboard/runtime/catalog.schema.json": "Apache-2.0",
  "onboard/runtime/examples/catalog.minimal.json": "Apache-2.0",
  "onboard/runtime/LICENSE": "Apache-2.0",
  "onboard/runtime/NOTICE": "Apache-2.0",
  "onboard/runtime/onboard-contracts.schema.json": "Apache-2.0",
  "onboard/runtime/requirements.txt": "Apache-2.0",
  "onboard/runtime/scripts/graft_runtime.py": "Apache-2.0",
  "onboard/runtime/scripts/onboard_arguments.py": "Apache-2.0",
  "onboard/runtime/scripts/onboard_contracts.py": "Apache-2.0",
  "onboard/runtime/scripts/onboard.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_backup_retention.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_cleanup_legacy.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_cleanup_targets.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_cleanup_upgrade.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_codex_wiring.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_graft_deployment.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_graft_entry.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_handoff.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_identity.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_migration_files.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_migration_legacy.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_migration_plan.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_migration_verify.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_migration.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_omp_sources.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_omp_wiring.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_probe_links.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_project.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_reconciliation.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_recovery.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_task_document.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_task_routing.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_task_state.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_trellis_uninstall.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_upgrade_cli.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_upgrade_hosts.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_upgrade_inventory.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_upgrade_paths.py": "Apache-2.0",
  "onboard/runtime/scripts/sbtd_upgrade.py": "Apache-2.0",
  "onboard/runtime/templates/project/gitignore.template": "Apache-2.0",
  "onboard/runtime/templates/skills/book-ddd-distilled-modeling/LICENSE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-ddd-distilled-modeling/NOTICE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-ddd-distilled-modeling/SKILL.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-ddia-data-design/LICENSE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-ddia-data-design/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/book-ddia-data-design/SKILL.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-legacy-change-safety/LICENSE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-legacy-change-safety/NOTICE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-legacy-change-safety/SKILL.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-refactoring-pass/LICENSE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-refactoring-pass/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/book-refactoring-pass/SKILL.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-release-readiness/LICENSE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-release-readiness/NOTICE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/book-release-readiness/SKILL.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/gherkin-bdd/LICENSE": "Apache-2.0",
  "onboard/runtime/templates/skills/gherkin-bdd/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/gherkin-bdd/SKILL.md": "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/LICENSE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/NOTICE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/artifact-manifest.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/deployment-manifest.example.yaml":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/deployment-manifest.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/evidence-decision.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/metrics.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/product.example.yaml":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/product.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/revision-set.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/runner-job.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/runner-result.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/runtime-contract.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/workspace.local.example.yaml":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/references/workspace.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/requirements.txt":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/scripts/knowledge_base_p1.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/knowledge-base-integration/SKILL.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/lessons-record/LICENSE": "Apache-2.0",
  "onboard/runtime/templates/skills/lessons-record/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/lessons-record/references/identity-migration.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/lessons-record/SKILL.md": "Apache-2.0",
  "onboard/runtime/templates/skills/maestro-mobile-e2e/LICENSE": "Apache-2.0",
  "onboard/runtime/templates/skills/maestro-mobile-e2e/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/maestro-mobile-e2e/references/ios-real-device-setup.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/maestro-mobile-e2e/references/lessons-index.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/maestro-mobile-e2e/SKILL.md": "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/LICENSE": "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/references/run-summary.zh-CN.md.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/references/validation-evidence-contract.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/references/validation-evidence.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/references/validation-evidence.v2.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/requirements.txt":
    "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/scripts/validate_validation_evidence.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/project-validation/SKILL.md": "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/LICENSE": "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/references/handoff.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/references/methods.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/references/presentation.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/references/state.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/references/strict.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/references/task-data.schema.json":
    "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/references/tooling.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/sbtd-task/SKILL.md": "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/LICENSE": "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/NOTICE": "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/references/geo-research.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/references/google-docs-summary.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/references/platform-algorithms.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/references/schema-templates.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/references/seo-checklist.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/references/tools-and-apis.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/autocomplete_ideas.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/backlinks.py": "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/competitor_gap.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/credential.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/dataforseo_api.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/domain_overview.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/keyword_research.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/related_keywords.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/seo_audit.py": "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/scripts/serp_analysis.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/seo-geo/SKILL.md": "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/agents/openai.yaml":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/auth-fixture.ts.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/github-actions-e2e.yml.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/package-scripts.json.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/page-object.ts.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/page-spec.ts.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/playwright.config.ts.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/assets/templates/summary.zh-CN.md.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/gitignore.template":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/LICENSE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/NOTICE":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/README.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/README.zh-CN.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/references/coverage-rubric.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/references/output-contract.md":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/analyze_failures.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/audit_selectors.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/check_coverage.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/scripts/generate_manifest.py":
    "Apache-2.0",
  "onboard/runtime/templates/skills/web-ui-autotest-generator/SKILL.md":
    "Apache-2.0",
  "onboard/runtime/upgrade.schema.json": "Apache-2.0",
  "THIRD_PARTY_NOTICES.md": "Apache-2.0",
  "third-party/sbtd-workflow-onboard/LICENSE": "Apache-2.0",
  "third-party/sbtd-workflow-onboard/NOTICE": "Apache-2.0",
};

type Provenance = EmbeddedKitManifestV2["retainedProvenance"];
interface Ledger {
  schemaVersion: number;
  stableSet: string;
  promotedAt: string;
  repositories: Record<
    string,
    Provenance["repositories"][string] & {
      licenseFiles: Array<{ source: string; stablePath: string }>;
    }
  >;
  skills: Provenance["skills"];
  sourceSelection?: {
    inputSha256: string;
    domain: {
      role: string;
      receipt: { record: { target: { repositoryKey: string } } };
    };
  };
}
interface Candidate {
  kit: Map<string, Buffer>;
  manifest: EmbeddedKitManifestV2;
  ledger: Ledger;
  report: Record<string, unknown>;
}
interface Mutation {
  operation: string;
  path: string;
  to?: string;
}

function required<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("Missing reviewed R1 test input");
  return value;
}
function ordered(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(ordered);
  if (value !== null && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, nested]) => [key, ordered(nested)]),
    );
  return value;
}
function semantic(value: unknown): string {
  return sha256(jsonBytes(ordered(value)));
}
function projectionClaim(manifest: EmbeddedKitManifestV2): string {
  return sha256(
    [
      ...Object.entries(manifest.assets)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([path, hash]) => `${path}\0${hash}`),
      ...Object.entries(manifest.overlayDigests)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([path, hash]) => `overlay:${path}\0${hash}`),
    ].join("\n"),
  );
}
function fromKit(kit: Map<string, Buffer>): Candidate {
  return {
    kit,
    manifest: JSON.parse(required(kit.get("manifest.json")).toString("utf8")),
    ledger: JSON.parse(required(kit.get(ledgerPath)).toString("utf8")),
    report: JSON.parse(
      required(kit.get("projection-report.json")).toString("utf8"),
    ),
  };
}
async function filePaths(root: string, prefix = ""): Promise<string[]> {
  const paths: string[] = [];
  for (const entry of await readdir(join(root, prefix), {
    withFileTypes: true,
  })) {
    const path = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) paths.push(...(await filePaths(root, path)));
    else {
      expect(entry.isFile(), `regular fixture file: ${path}`).toBe(true);
      paths.push(path);
    }
  }
  return paths.sort();
}
async function actualR1Candidate(): Promise<Candidate> {
  const kitRoot = join(packageRoot, "kit");
  const manifestBytes = await readFile(join(kitRoot, "manifest.json"));
  // Fixed independent output-vector seals, not candidate-derived expected values.
  expect(sha256(manifestBytes)).toBe(
    "86d4e5cfd8b1b0e4d5c4046c95587ba3d3a92fa3e3a39fa6df36b906e98d0347",
  );
  const manifest: EmbeddedKitManifestV2 = JSON.parse(
    manifestBytes.toString("utf8"),
  );
  expect(manifest.projection.generatedSha256).toBe(r1Root);
  expect(projectionClaim(manifest)).toBe(r1Root);
  expect(Object.keys(manifest.assets).sort()).toEqual(
    Object.keys(expectedKitLicenses).sort(),
  );
  expect(await filePaths(kitRoot)).toEqual(
    [
      ...Object.keys(expectedKitLicenses),
      "manifest.json",
      "projection-report.json",
    ].sort(),
  );
  const kit = new Map<string, Buffer>();
  for (const [path, expected] of Object.entries(manifest.assets)) {
    const bytes = await readFile(join(kitRoot, path));
    expect(sha256(bytes), path).toBe(expected);
    expect((await lstat(join(kitRoot, path))).mode & 0o777).toBe(0o644);
    kit.set(path, bytes);
  }
  const report = await readFile(join(kitRoot, "projection-report.json"));
  expect(sha256(report)).toBe(
    "07c689383e2bae90555b2c2a699c482ddbf37aebc51691a0ce3aef464cac8fac",
  );
  kit.set("manifest.json", manifestBytes);
  kit.set("projection-report.json", report);
  const candidate = fromKit(kit);
  expect(sha256(required(kit.get(ledgerPath)))).toBe(r1RawLedger);
  expect(semantic(candidate.ledger)).toBe(r1SemanticLedger);
  expect(candidate.ledger.sourceSelection?.inputSha256).toBe(
    "290bdc6379f3f55376ac24ac660598c3013408f376834d6d96ca92b739cd90c4",
  );
  expect(Object.keys(candidate.ledger.repositories)).toHaveLength(4);
  expect(Object.keys(candidate.ledger.skills)).toHaveLength(16);
  expect(
    Object.entries(candidate.ledger.skills)
      .filter(([, value]) => value.repository === r1Repository)
      .map(([name]) => name)
      .sort(),
  ).toEqual(["domain-modeling", "grilling", "to-tickets"]);
  expect(
    Object.entries(candidate.ledger.skills)
      .filter(([, value]) => value.repository === "mattpocock-skills")
      .map(([name]) => name)
      .sort(),
  ).toEqual([
    "codebase-design",
    "diagnosing-bugs",
    "grill-me",
    "grill-with-docs",
    "handoff",
    "tdd",
    "to-spec",
    "writing-for-agents",
  ]);
  return candidate;
}

// Recompute attacker claims only. Neither this helper nor a production renderer
// supplies expected trusted identities or expected SPDX licenses.
function rebindClaims(
  candidate: Candidate,
  ledgerBytes = jsonBytes(candidate.ledger),
): void {
  const { kit, manifest, ledger, report } = candidate;
  kit.set(ledgerPath, ledgerBytes);
  manifest.assets = Object.fromEntries(
    [...kit]
      .filter(
        ([path]) =>
          path !== "manifest.json" && path !== "projection-report.json",
      )
      .map(([path, bytes]) => [path, sha256(bytes)]),
  );
  for (const path of Object.keys(manifest.overlayDigests))
    manifest.overlayDigests[path] = required(manifest.assets[path]);
  for (const path of Object.keys(manifest.targets))
    manifest.targets[path] = required(manifest.assets[path]);
  manifest.profileCatalogSha256 = required(manifest.assets["catalog.json"]);
  manifest.retainedProvenance = {
    stableSet: ledger.stableSet,
    manifestSha256: required(manifest.assets[ledgerPath]),
    repositories: Object.fromEntries(
      Object.entries(ledger.repositories).map(([name, repository]) => [
        name,
        {
          url: repository.url,
          revision: repository.revision,
          license: repository.license,
        },
      ]),
    ),
    skills: Object.fromEntries(
      Object.entries(ledger.skills).map(([name, skill]) => [
        name,
        {
          repository: skill.repository,
          sourceSubpath: skill.sourceSubpath,
          stablePath: skill.stablePath,
          treeSha256: skill.treeSha256,
        },
      ]),
    ),
  };
  manifest.projection.generatedSha256 = projectionClaim(manifest);
  report.generatedSha256 = manifest.projection.generatedSha256;
  report.canonicalManifestSha256 = manifest.canonical.manifestSha256;
  report.retainedProvenanceManifestSha256 =
    manifest.retainedProvenance.manifestSha256;
  kit.set("manifest.json", jsonBytes(manifest));
  kit.set("projection-report.json", jsonBytes(report));
}
function mutateNoticeByte(candidate: Candidate, path: string): void {
  const original = required(candidate.kit.get(path));
  const offset = original.indexOf(Buffer.from("Permission is hereby granted"));
  expect(offset).toBeGreaterThan(0);
  const changed = Buffer.from(original);
  changed[offset] = 0x51;
  expect(
    [...changed].filter((byte, index) => byte !== original[index]),
  ).toHaveLength(1);
  candidate.kit.set(path, changed);
}
async function snapshot(root: string) {
  return Promise.all(
    (await filePaths(root)).map(async (path) => ({
      path,
      sha256: sha256(await readFile(join(root, path))),
      mode: (await stat(join(root, path))).mode,
    })),
  );
}
async function scaffold(candidate: Candidate): Promise<Fixture> {
  const root = await mkdtemp(join(tmpdir(), "kpi-r1-release-identity-"));
  temporaryRoots.push(root);
  const pluginRoot = join(root, "plugin");
  const upstreamRoot = join(root, "upstream");
  const kitRoot = join(pluginRoot, "kit");
  await Promise.all([
    mkdir(kitRoot, { recursive: true }),
    mkdir(upstreamRoot),
    mkdir(join(pluginRoot, "validation/p0"), { recursive: true }),
    mkdir(join(root, "unrelated-destination")),
  ]);
  await Promise.all([
    ...["package.json", "LICENSE"].map((path) =>
      cp(join(workspaceRoot, path), join(root, path)),
    ),
    ...["package.json", "LICENSE"].map((path) =>
      cp(join(packageRoot, "upstream", path), join(upstreamRoot, path)),
    ),
    ...[
      "package.json",
      "plugin.json",
      "LICENSE",
      "README.md",
      "README.zh.md",
      "SECURITY.md",
      "CHANGELOG.md",
      "validation/p0/compatibility.v2.json",
      "skills",
      "dist",
      "src",
    ].map((path) =>
      cp(join(packageRoot, path), join(pluginRoot, path), { recursive: true }),
    ),
    ...[...candidate.kit].map(async ([path, bytes]) => {
      const target = join(kitRoot, path);
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, bytes);
    }),
  ]);
  const topNotice = required(candidate.kit.get("THIRD_PARTY_NOTICES.md"))
    .toString("utf8")
    .replaceAll(
      "Retained license: onboard/runtime/",
      "Retained license: kit/onboard/runtime/",
    )
    .replaceAll(
      "Retained notice: onboard/runtime/",
      "Retained notice: kit/onboard/runtime/",
    );
  await writeFile(join(pluginRoot, "THIRD_PARTY_NOTICES.md"), topNotice);
  await writeFile(
    join(root, "unrelated-destination/keep.bin"),
    Buffer.from([0, 255, 13, 10, 83, 66, 84, 68]),
  );
  const actual = createNodeFileSystem();
  const mutations: Mutation[] = [];
  const files: P0FileSystem = {
    ...actual,
    writeText: async (path, text) => {
      mutations.push({ operation: "writeText", path });
      await actual.writeText(path, text);
    },
    makeDirectory: async (path) => {
      mutations.push({ operation: "makeDirectory", path });
      await actual.makeDirectory(path);
    },
    move: async (path, to) => {
      mutations.push({ operation: "move", path, to });
      await actual.move(path, to);
    },
    remove: async (path) => {
      mutations.push({ operation: "remove", path });
      await actual.remove(path);
    },
  };
  return {
    root,
    input: { workspaceRoot: root, pluginRoot, upstreamRoot, files },
    kitRoot,
    sbomPath: join(pluginRoot, "SBOM.spdx.json"),
    mutations,
  };
}
interface Fixture {
  root: string;
  input: {
    workspaceRoot: string;
    pluginRoot: string;
    upstreamRoot: string;
    files: P0FileSystem;
  };
  kitRoot: string;
  sbomPath: string;
  mutations: Mutation[];
}
async function metadataAndMH(f: Fixture) {
  await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
    plugin: { license: "Apache-2.0" },
  });
  return verifyEmbeddedKitReleaseIntegrity({
    kitRoot: f.kitRoot,
    files: f.input.files,
  });
}
async function rejectWithoutMutation(
  f: Fixture,
  failure: { code: string; message: string },
  releaseRoots: readonly ("source-package" | "staged-promotion")[] = [
    "source-package",
    "staged-promotion",
  ],
): Promise<void> {
  const before = await snapshot(f.root);
  for (const releaseRoot of releaseRoots) {
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot }),
    ).rejects.toMatchObject({ name: "P0ValidationError", ...failure });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
  }
  expect(await snapshot(f.root)).toEqual(before);
}
async function rejectCoherent(
  candidate: Candidate,
  message: string,
  releaseRoots?: readonly ("source-package" | "staged-promotion")[],
): Promise<void> {
  const f = await scaffold(candidate);
  const mh = await metadataAndMH(f);
  expect(mh.projection.generatedSha256).toBe(
    candidate.manifest.projection.generatedSha256,
  );
  await rejectWithoutMutation(
    f,
    { code: "LICENSE_MISMATCH", message },
    releaseRoots,
  );
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("exact reviewed R1 release identity", () => {
  it("real source writer -> real verifier -> strict stage uses identical R1 bytes and exact SPDX mapping", async () => {
    const candidate = await actualR1Candidate();
    const f = await scaffold(candidate);
    expect((await metadataAndMH(f)).projection.generatedSha256).toBe(r1Root);
    const before = await snapshot(f.root);
    expect(
      sha256(
        await readFile(join(f.input.pluginRoot, "THIRD_PARTY_NOTICES.md")),
      ),
    ).toBe("7d2281ddb7b08cba64101aa15a7f3480a2f2f7262141feb08131f555714bce10");
    const inventory = [];
    for (const path of await filePaths(f.input.pluginRoot)) {
      if (
        !(
          path.startsWith("kit/") ||
          path.startsWith("dist/") ||
          path.startsWith("skills/") ||
          [
            "plugin.json",
            "LICENSE",
            "README.md",
            "README.zh.md",
            "SECURITY.md",
            "CHANGELOG.md",
            "THIRD_PARTY_NOTICES.md",
            "validation/p0/compatibility.v2.json",
          ].includes(path)
        )
      )
        continue;
      const kitPath = path.slice("kit/".length);
      const license =
        !path.startsWith("kit/") ||
        ["manifest.json", "projection-report.json"].includes(kitPath)
          ? "Apache-2.0"
          : required(expectedKitLicenses[kitPath]);
      inventory.push({
        path,
        sha256: sha256(await readFile(join(f.input.pluginRoot, path))),
        license,
      });
    }
    inventory.sort((a, b) => a.path.localeCompare(b.path));
    expect(inventory).toHaveLength(470);
    expect(inventory.filter((file) => file.license === "MIT")).toHaveLength(
      110,
    );
    const plugin = JSON.parse(
      await readFile(join(f.input.pluginRoot, "package.json"), "utf8"),
    ) as { name: string; version: string };
    const expectedSource = semantic({
      plugin: { name: plugin.name, version: plugin.version },
      kit: { generatedSha256: r1Root },
      files: inventory,
    });
    const written = await writePluginSpdxSbom(f.input);
    const bytes = await readFile(f.sbomPath);
    expect(written).toEqual({
      sourceTreeSha256: expectedSource,
      sbomSha256: sha256(bytes),
    });
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    const sbom: {
      documentNamespace: string;
      files: Array<{
        fileName: string;
        checksums: unknown[];
        licenseConcluded: string;
        licenseInfoInFiles: string[];
      }>;
    } = JSON.parse(bytes.toString("utf8"));
    expect(sbom.documentNamespace).toBe(
      `https://kpi.local/spdx/${expectedSource}`,
    );
    expect(sbom.files).toHaveLength(470);
    expect(sbom.files.map((file) => file.fileName)).toEqual(
      inventory.map((file) => `./${file.path}`),
    );
    for (const item of inventory)
      expect(
        sbom.files.find((file) => file.fileName === `./${item.path}`),
      ).toMatchObject({
        checksums: [{ algorithm: "SHA256", checksumValue: item.sha256 }],
        licenseConcluded: item.license,
        licenseInfoInFiles: [item.license],
      });
    await expect(verifyPluginReleaseArtifacts(f.input)).resolves.toEqual(
      written,
    );
    expect(f.mutations).toHaveLength(1);
    const staged = await writePluginSpdxSbom({
      ...f.input,
      releaseRoot: "staged-promotion",
    });
    expect(staged).toEqual(written);
    expect(await readFile(f.sbomPath)).toEqual(bytes);
    expect(f.mutations).toEqual([
      { operation: "writeText", path: f.sbomPath },
      { operation: "writeText", path: f.sbomPath },
    ]);
    await expect(verifyPluginReleaseArtifacts(f.input)).resolves.toEqual(
      written,
    );
    expect(f.mutations).toHaveLength(2);
    expect(
      (await snapshot(f.root)).filter(
        (file) => file.path !== "plugin/SBOM.spdx.json",
      ),
    ).toEqual(before);
  });

  it("unknown root with known non-overlay ADR and unchanged reviewed ledger reaches the paired gate", async () => {
    const candidate = await actualR1Candidate();
    expect(candidate.manifest.overlayDigests[adrPath]).toBeUndefined();
    candidate.kit.set(
      adrPath,
      Buffer.concat([
        required(candidate.kit.get(adrPath)),
        Buffer.from("\nUnreviewed ADR content.\n"),
      ]),
    );
    rebindClaims(candidate);
    expect(sha256(required(candidate.kit.get(ledgerPath)))).toBe(r1RawLedger);
    expect(semantic(candidate.ledger)).toBe(r1SemanticLedger);
    expect(candidate.manifest.projection.generatedSha256).not.toBe(r1Root);
    await rejectCoherent(candidate, pairedMessage);
  });

  it("raw ledger reorder retains semantic identity but reaches the paired gate", async () => {
    const candidate = await actualR1Candidate();
    const raw = Buffer.from(
      `${JSON.stringify(Object.fromEntries(Object.entries(candidate.ledger).reverse()), null, 4)}\n`,
    );
    expect(semantic(JSON.parse(raw.toString("utf8")))).toBe(r1SemanticLedger);
    expect(sha256(raw)).not.toBe(r1RawLedger);
    rebindClaims(candidate, raw);
    expect(candidate.manifest.projection.generatedSha256).not.toBe(r1Root);
    await rejectCoherent(candidate, pairedMessage);
  });

  it.each([
    "THIRD_PARTY_NOTICES.md",
    stableNoticePath,
  ])("unbound single-byte %s tamper fails MH without any mutation", async (path) => {
    const candidate = await actualR1Candidate();
    mutateNoticeByte(candidate, path);
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: f.kitRoot,
        files: f.input.files,
      }),
    ).rejects.toMatchObject({
      code: "PACKAGE_CONTENT_INVALID",
      message: mhMessage,
    });
    await rejectWithoutMutation(f, {
      code: "PACKAGE_CONTENT_INVALID",
      message: mhMessage,
    });
  });
  it.each([
    "THIRD_PARTY_NOTICES.md",
    stableNoticePath,
  ])("coherent single-byte %s tamper reaches the paired gate", async (path) => {
    const candidate = await actualR1Candidate();
    mutateNoticeByte(candidate, path);
    rebindClaims(candidate);
    expect(semantic(candidate.ledger)).toBe(r1SemanticLedger);
    await rejectCoherent(candidate, pairedMessage);
  });

  it.each([
    "owner",
    "pin",
    "selection",
    "nested-domain-owner",
    "nested-domain-role",
    "extra-repository",
    "extra-skill",
  ])("coherent wrong %s fails the complete R1 semantic gate", async (attack) => {
    const candidate = await actualR1Candidate();
    if (attack === "owner")
      required(candidate.ledger.skills.grilling).repository =
        "mattpocock-skills";
    else if (attack === "pin") {
      const repository = required(candidate.ledger.repositories[r1Repository]);
      const revision = "2222222222222222222222222222222222222222";
      candidate.kit.set(
        "THIRD_PARTY_NOTICES.md",
        Buffer.from(
          required(candidate.kit.get("THIRD_PARTY_NOTICES.md"))
            .toString("utf8")
            .replaceAll(repository.revision, revision),
        ),
      );
      repository.revision = revision;
    } else if (attack === "selection")
      required(candidate.ledger.sourceSelection).inputSha256 = "0".repeat(64);
    else if (attack === "nested-domain-owner")
      required(
        candidate.ledger.sourceSelection,
      ).domain.receipt.record.target.repositoryKey = r1Repository;
    else if (attack === "nested-domain-role")
      required(candidate.ledger.sourceSelection).domain.role = "final-owner";
    else if (attack === "extra-repository")
      candidate.ledger.repositories.unreviewed = structuredClone(
        required(candidate.ledger.repositories[r1Repository]),
      );
    else
      candidate.ledger.skills.unreviewed = structuredClone(
        required(candidate.ledger.skills.grilling),
      );
    rebindClaims(candidate);
    expect(semantic(candidate.ledger)).not.toBe(r1SemanticLedger);
    await rejectCoherent(candidate, semanticMessage);
  });

  it("R1 ledger cannot borrow the old global overlay even with coherent claims", async () => {
    const candidate = await actualR1Candidate();
    const old = await readReleaseFixture("old");
    const global = required(old.get("AGENTS.global.md"));
    expect(sha256(global)).toBe(
      "7c21a5989aaa8bf3b658c3c28d56e30862ead5e70a2ad72520a95a23bd2694ea",
    );
    candidate.kit.set("AGENTS.global.md", global);
    rebindClaims(candidate);
    expect(semantic(candidate.ledger)).toBe(r1SemanticLedger);
    await rejectCoherent(candidate, overlayMessage);
  });
  it.each([
    "old",
    "mixed",
    "domain",
  ] as const)("%s ledger cannot borrow the new R1 global overlay", async (profile) => {
    const candidate = fromKit(await readReleaseFixture(profile));
    const r1 = await actualR1Candidate();
    candidate.kit.set(
      "AGENTS.global.md",
      required(r1.kit.get("AGENTS.global.md")),
    );
    rebindClaims(candidate);
    // The old stage deliberately permits first-party changes; only release is
    // immutable there. Mixed/domain stage delegates strict release validation.
    await rejectCoherent(
      candidate,
      "Overlay has no reviewed first-party license identity: AGENTS.global.md",
      profile === "old" ? ["source-package"] : undefined,
    );
  });

  it.each([
    "extra",
    "missing",
  ])("%s asset in a known first-party prefix is not admitted", async (attack) => {
    const candidate = await actualR1Candidate();
    if (attack === "extra")
      candidate.kit.set(
        "onboard/runtime/unreviewed.md",
        Buffer.from("No prefix license default.\n"),
      );
    else candidate.kit.delete("onboard/runtime/examples/catalog.minimal.json");
    rebindClaims(candidate);
    await rejectCoherent(candidate, pairedMessage);
  });
  it("extra unbound disk asset is rejected by exact inventory mapping", async () => {
    const candidate = await actualR1Candidate();
    const f = await scaffold(candidate);
    await writeFile(
      join(f.kitRoot, "onboard/runtime/unreviewed.md"),
      "Not a reviewed asset.\n",
    );
    expect((await metadataAndMH(f)).projection.generatedSha256).toBe(r1Root);
    await rejectWithoutMutation(f, {
      code: "LICENSE_MISMATCH",
      message:
        "Inventoried Kit file is unbound or differs from its classified asset: onboard/runtime/unreviewed.md",
    });
  });
  it.each([
    "canonical-tree",
    "transform",
    "projection-policy",
  ])("%s must match the exact canonical R1 contract", async (attack) => {
    const candidate = await actualR1Candidate();
    if (attack === "canonical-tree")
      candidate.manifest.canonical.sourceTreeSha256 = "0".repeat(64);
    else if (attack === "transform")
      candidate.manifest.canonical.transformVersion = "unreviewed-transform";
    else candidate.manifest.projection.policySha256 = "0".repeat(64);
    rebindClaims(candidate);
    expect(candidate.manifest.projection.generatedSha256).toBe(r1Root);
    await rejectCoherent(candidate, canonicalMessage);
  });
  it("strict stage checks package notice bytes even for the exact approved R1 Kit", async () => {
    const f = await scaffold(await actualR1Candidate());
    const path = join(f.input.pluginRoot, "THIRD_PARTY_NOTICES.md");
    const notice = await readFile(path, "utf8");
    const changed = notice.replace(
      "Copyright (c) 2023 Phosphor Icons",
      "Copyright (c) 2023 Unreviewed Owner",
    );
    expect(changed).not.toBe(notice);
    await writeFile(path, changed);
    const before = await snapshot(f.root);
    expect((await metadataAndMH(f)).projection.generatedSha256).toBe(r1Root);
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" }),
    ).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message:
        "The staged root notice is not the exact embedded Kit attribution.",
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    expect(await snapshot(f.root)).toEqual(before);
  });
});

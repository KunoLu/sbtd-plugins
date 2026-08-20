# Web UI Autotest Generator

A Codex skill for generating and reviewing Web UI automated testing assets.

It first analyzes frontend pages, routes, components, APIs, user flows, and selector stability, and then generates maintainable Playwright test suites, coverage checklists, failure repair plans, and Chinese test reports. The goal is not to produce disposable recorded scripts, but to establish UI automated testing assets that can run independently, be maintained continuously, and be reviewed easily.

## Applicable Scenarios

- Generate Playwright + TypeScript UI automated tests from an existing Web project.
- Catalog pages, features, API dependencies, and cross-page business flows.
- Audit whether UI elements have stable selectors or accessible locator information.
- Generate test governance files such as `ui-test-manifest.json`, `ui-selector-audit.json`, and `ui-test-coverage.json`.
- Analyze Playwright JSON reports and output failure classifications and repair recommendations.
- Generate Chinese test summary reports describing coverage, risks, and follow-up actions.

## Default Output Structure

```text
tests/e2e/
  pages/                 # Page Object models
  specs/                 # Page-level or flow-level test cases
  fixtures/              # Authentication state, test data, and API mocks
  utils/                 # Common helper functions
  reports/               # Test reports and Chinese summaries
playwright.config.ts
ui-test-manifest.json
ui-selector-audit.json
ui-test-coverage.json
```

If the target project already uses another UI testing framework, the skill will prioritize the existing system; otherwise, it uses Playwright + TypeScript by default.

## Repository Structure

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── templates/
│       ├── auth-fixture.ts.template
│       ├── github-actions-e2e.yml.template
│       ├── package-scripts.json.template
│       ├── page-object.ts.template
│       ├── page-spec.ts.template
│       ├── playwright.config.ts.template
│       └── summary.zh-CN.md.template
├── references/
│   ├── coverage-rubric.md
│   └── output-contract.md
└── scripts/
    ├── analyze_failures.py
    ├── audit_selectors.py
    ├── check_coverage.py
    └── generate_manifest.py
```

## Script Entry Points

Run the following commands in the root directory of the target Web project, and replace `path/to/web-ui-autotest-generator` with the local path to this skill.

Generate the initial page and feature inventory:

```bash
python3 path/to/web-ui-autotest-generator/scripts/generate_manifest.py --root . --out ui-test-manifest.json --pretty
```

Audit selector stability:

```bash
python3 path/to/web-ui-autotest-generator/scripts/audit_selectors.py --root . --out ui-selector-audit.json --pretty
```

Check coverage after generating the tests:

```bash
python3 path/to/web-ui-autotest-generator/scripts/check_coverage.py --root . --manifest ui-test-manifest.json --selector-audit ui-selector-audit.json --tests-dir tests/e2e --out ui-test-coverage.json --pretty
```

Analyze the Playwright JSON failure report:

```bash
python3 path/to/web-ui-autotest-generator/scripts/analyze_failures.py --report tests/e2e/reports/results.json --out ui-test-repair-plan.json --pretty
```

## Workflow

1. Inspect the target project structure, package manager, and existing testing tools.
2. Analyze frontend routes, pages, components, UI controls, state management, and API calls.
3. If backend code, OpenAPI, Swagger, or Apifox documentation exists, supplement the analysis with API contracts.
4. Generate inventories of pages, features, APIs, and flows.
5. Audit selector stability and record recommendations for adding `data-testid` attributes or accessibility improvements.
6. Generate Playwright Page Objects, fixtures, specs, and CI configuration.
7. Run the tests when conditions permit.
8. If tests fail, analyze the causes of failure and generate a repair plan.
9. Self-check the generated results according to the coverage rules.
10. Output a Chinese test report.

## Coverage and Quality Requirements

The generated testing assets should cover as much as possible:

- Page loading, primary content rendering, and loading states.
- Empty states, error states, and unauthenticated or unauthorized states.
- Required form fields, valid submissions, invalid submissions, and server-side validation errors.
- Search, filtering, reset, pagination, sorting, and row actions for tables or lists.
- Modals, drawers, confirmation dialogs, and dangerous operations.
- Cross-page flows, such as searching after creation, editing on a details page, and verification after deletion.
- API dependencies corresponding to page loading and user actions.

Selector priority:

1. `data-testid` or the project's existing test ID convention.
2. Accessible roles and names.
3. Form field labels.
4. Stable visible text.
5. Stable component attributes.
6. Use CSS selectors only when there is no better approach.

## License

This independently implemented Skill is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

# Coverage Rubric

Use this rubric to review generated Web UI automation tests.

Human-readable final reports should be written in Chinese by default. Keep machine-readable JSON field names stable, and translate explanations, gaps, and repair suggestions in `tests/e2e/reports/summary.md`.

## Coverage Levels

Classify each page or flow:

- `full`: Core happy path, important negative path, and cross-page/API behavior are covered.
- `partial`: Main page loads and some actions are covered, but important branches are missing.
- `smoke`: Only load/render checks are covered.
- `missing`: No executable test exists.
- `blocked`: Coverage requires missing credentials, unavailable environment, or unclear business rules.

## Page Coverage Checklist

Each route should be checked for:

- Route loads without console/runtime errors.
- Primary visible content appears.
- Loading state resolves.
- Empty state is represented when relevant.
- API error state is represented when relevant.
- Unauthorized or permission-denied state is represented when relevant.

## Component Coverage Checklist

Forms:

- Required fields.
- Valid submission.
- Invalid submission.
- Disabled/loading submit state.
- Server validation error.

Tables/lists:

- Initial data render.
- Search/filter.
- Reset.
- Pagination.
- Sorting when present.
- Row action.
- Empty result.

Dialogs/drawers:

- Open.
- Close/cancel.
- Submit success.
- Submit validation failure.

Navigation:

- Link click.
- Route param handling.
- Back/return behavior when present.
- Breadcrumb/menu active state when relevant.

Destructive actions:

- Confirmation appears.
- Cancel does not mutate data.
- Confirm mutates data.
- Success/failure feedback appears.

Uploads/downloads:

- Accepted file path.
- Rejected file type/size when implemented.
- Download response or browser download event.

## API Mapping Checklist

Every API dependency discovered from frontend/backend code should be one of:

- Covered by a UI scenario.
- Covered by a fixture/setup helper.
- Mocked for a UI state scenario.
- Excluded with an explicit reason.

Pay special attention to:

- Page-load APIs.
- Search/list APIs.
- Create/update/delete APIs.
- Detail APIs.
- Export/download APIs.
- Permission/user-info APIs.

## Cross-Page Flow Checklist

Generate scenario tests for important business flows:

- Login -> target page.
- Create -> list/search -> detail.
- Detail -> edit -> verify persisted change.
- Delete -> verify absence.
- Parent page -> child page -> return.
- Multi-step wizard or checkout-like flow.

## Quality Gates

Generated tests should pass these gates:

- No arbitrary `waitForTimeout` unless explicitly justified.
- No generated CSS class selectors when better locators exist.
- No production credentials.
- Test data is deterministic and isolated.
- Tests can run through `npm run test:e2e` or an equivalent command.
- Failing tests produce screenshot/trace/video or Playwright report artifacts.
- Coverage gaps are documented.

## Scoring Guidance

Use `ui-test-coverage.json.summary.scores` for quick reporting:

- `overallScore`: weighted quality score across pages, features, APIs, cross-page flows, and selectors.
- `pageCoveragePercent`: discovered routes with executable tests.
- `featureCoveragePercent`: expected feature checks covered by specs.
- `apiCoveragePercent`: discovered API dependencies referenced or exercised by specs.
- `crossPageFlowCoveragePercent`: business flows covered by scenario specs.
- `selectorStabilityScore`: interactive UI elements with stable selector/accessibility metadata.

Suggested interpretation:

- 90-100: strong regression suite candidate.
- 75-89: usable, with known gaps.
- 50-74: smoke/partial coverage; expand before CI gating.
- Below 50: discovery or generation likely needs another pass.

## Selector Stability Gates

Selector audit is not the same as accessibility review, but it catches common automation risks.

Classify selector stability:

- `high`: score >= 85, generated tests should be maintainable.
- `medium`: score 60-84, core paths may be stable but flaky selectors are likely.
- `low`: score < 60, recommend adding `data-testid`, role/name, labels, or better accessibility metadata before broad generation.

For P0 flows, avoid CSS fallback selectors unless the final report documents why no better locator is available.

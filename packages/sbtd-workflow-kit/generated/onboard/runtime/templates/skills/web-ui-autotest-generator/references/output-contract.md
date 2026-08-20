# 输出契约

生成清单、覆盖率、失败修复计划和最终中文报告时，使用以下结构。

## `ui-test-manifest.json`

```json
{
  "project": {
    "name": "string",
    "frontendFramework": "string",
    "backendFramework": "string | null",
    "testFramework": "playwright"
  },
  "pages": [
    {
      "id": "string",
      "name": "string",
      "route": "string",
      "sourceFiles": ["string"],
      "authRequired": true,
      "permissions": ["string"],
      "uiElements": {
        "buttons": ["string"],
        "links": ["string"],
        "forms": [
          {
            "name": "string",
            "fields": [
              {
                "name": "string",
                "type": "string",
                "required": true
              }
            ]
          }
        ],
        "tables": [
          {
            "name": "string",
            "columns": ["string"],
            "rowActions": ["string"]
          }
        ],
        "dialogs": ["string"]
      },
      "apiDependencies": [
        {
          "method": "GET",
          "path": "/api/example",
          "trigger": "page-load | user-action | setup | teardown"
        }
      ],
      "flows": [
        {
          "name": "string",
          "steps": ["string"],
          "expectedResult": "string"
        }
      ],
      "proposedTests": [
        {
          "id": "string",
          "name": "string",
          "type": "load | happy-path | validation | error-state | navigation | permission | smoke",
          "priority": "P0 | P1 | P2"
        }
      ]
    }
  ]
}
```

## `ui-test-coverage.json`

```json
{
  "summary": {
    "routesDiscovered": 0,
    "routesCovered": 0,
    "testsGenerated": 0,
    "coverageLevel": "full | partial | smoke | missing | blocked",
    "scores": {
      "overallScore": 0,
      "pageCoveragePercent": 0,
      "featureCoveragePercent": 0,
      "apiCoveragePercent": 0,
      "crossPageFlowCoveragePercent": 0,
      "selectorStabilityScore": 0
    },
    "totals": {
      "expectedFeatureItems": 0,
      "coveredFeatureItems": 0,
      "apiDependenciesDiscovered": 0,
      "apiDependenciesCovered": 0,
      "crossPageFlowsDiscovered": 0,
      "crossPageFlowsCovered": 0
    }
  },
  "pages": [
    {
      "route": "string",
      "coverageLevel": "full | partial | smoke | missing | blocked",
      "score": {
        "expectedItems": 0,
        "coveredItems": 0,
        "coveragePercent": 0,
        "apiDependencies": 0,
        "apiDependenciesCovered": 0,
        "apiCoveragePercent": 0
      },
      "covered": [
        "page-load",
        "search",
        "create"
      ],
      "missing": [
        {
          "item": "string",
          "reason": "string",
          "suggestedTest": "string"
        }
      ],
      "testFiles": ["string"]
    }
  ],
  "crossPageFlows": [
    {
      "name": "string",
      "covered": true,
      "testFile": "string | null",
      "missingReason": "string | null"
    }
  ]
}
```

## `ui-selector-audit.json`

```json
{
  "summary": {
    "filesScanned": 0,
    "interactiveElements": 0,
    "stableElements": 0,
    "missingStableSelectors": 0,
    "selectorStabilityScore": 0,
    "selectorStabilityLevel": "high | medium | low"
  },
  "files": [
    {
      "file": "string",
      "interactiveElements": 0,
      "stableElements": 0,
      "missingStableSelectors": [
        {
          "file": "string",
          "line": 0,
          "element": "string",
          "tag": "string",
          "suggestedTestId": "string",
          "reason": "string"
        }
      ]
    }
  ],
  "recommendations": []
}
```

## `ui-test-repair-plan.json`

```json
{
  "summary": {
    "failedTests": 0,
    "categories": {
      "selector": 0,
      "timeout": 0,
      "assertion": 0,
      "auth": 0,
      "navigation": 0,
      "api": 0,
      "test-data": 0,
      "unknown": 0
    },
    "status": "passed | needs-repair"
  },
  "failures": [
    {
      "title": "string",
      "file": "string",
      "line": 0,
      "status": "string",
      "durationMs": 0,
      "category": "string",
      "message": "string",
      "suggestedFixes": ["string"],
      "artifacts": ["string"]
    }
  ],
  "nextIteration": {
    "priorityActions": ["string"],
    "rerunCommand": "string",
    "recommendedLoop": ["string"]
  }
}
```

## 中文最终测试报告

面向人阅读的最终测试报告默认使用中文，建议输出到 `tests/e2e/reports/summary.md`，并以 `assets/templates/summary.zh-CN.md.template` 为基础。

报告应包含：

- 生成了哪些测试资产和报告文件。
- 如何重新运行测试。
- 是否执行过测试。
- 通过、失败或阻塞结论。
- 关键覆盖率缺口和总体评分。
- 选择器稳定性评分和主要改造建议。
- 如果执行失败，说明失败分类和修复优先级。
- 仍需人工提供的账号、环境变量、测试数据或业务规则。

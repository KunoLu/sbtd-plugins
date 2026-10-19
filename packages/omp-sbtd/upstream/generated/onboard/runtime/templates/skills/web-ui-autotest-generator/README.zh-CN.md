# Web UI Autotest Generator

一个用于生成和评审 Web UI 自动化测试资产的 Codex skill。

它会先分析前端页面、路由、组件、接口、用户流程和选择器稳定性，再生成可维护的 Playwright 测试套件、覆盖率清单、失败修复计划和中文测试报告。目标不是产出一次性的录制脚本，而是沉淀可以独立运行、持续维护、方便复查的 UI 自动化测试资产。

## 适用场景

- 从现有 Web 项目中生成 Playwright + TypeScript UI 自动化测试。
- 梳理页面、功能、接口依赖和跨页面业务流程。
- 审计 UI 元素是否具备稳定选择器或可访问定位信息。
- 生成 `ui-test-manifest.json`、`ui-selector-audit.json`、`ui-test-coverage.json` 等测试治理文件。
- 分析 Playwright JSON 报告，并输出失败分类与修复建议。
- 生成中文测试总结报告，说明覆盖情况、风险和后续动作。

## 默认输出结构

```text
tests/e2e/
  pages/                 # Page Object 模型
  specs/                 # 页面级或流程级测试用例
  fixtures/              # 登录状态、测试数据、接口 mock
  utils/                 # 通用辅助函数
  reports/               # 测试报告和中文总结
playwright.config.ts
ui-test-manifest.json
ui-selector-audit.json
ui-test-coverage.json
```

如果目标项目已经使用其他 UI 测试框架，skill 会优先沿用现有体系；否则默认使用 Playwright + TypeScript。

## 仓库结构

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

## 脚本入口

在目标 Web 项目根目录中运行以下命令，并把 `path/to/web-ui-autotest-generator` 替换为本 skill 的本地路径。

生成初始页面和功能清单：

```bash
python3 path/to/web-ui-autotest-generator/scripts/generate_manifest.py --root . --out ui-test-manifest.json --pretty
```

审计选择器稳定性：

```bash
python3 path/to/web-ui-autotest-generator/scripts/audit_selectors.py --root . --out ui-selector-audit.json --pretty
```

生成测试后检查覆盖率：

```bash
python3 path/to/web-ui-autotest-generator/scripts/check_coverage.py --root . --manifest ui-test-manifest.json --selector-audit ui-selector-audit.json --tests-dir tests/e2e --out ui-test-coverage.json --pretty
```

分析 Playwright JSON 失败报告：

```bash
python3 path/to/web-ui-autotest-generator/scripts/analyze_failures.py --report tests/e2e/reports/results.json --out ui-test-repair-plan.json --pretty
```

## 工作流程

1. 检查目标项目结构、包管理器和已有测试工具。
2. 分析前端路由、页面、组件、UI 控件、状态管理和接口调用。
3. 如存在后端代码、OpenAPI、Swagger 或 Apifox 文档，补充分析接口契约。
4. 生成页面、功能、接口和流程清单。
5. 审计选择器稳定性，记录 `data-testid` 或可访问性改造建议。
6. 生成 Playwright Page Object、fixture、spec 和 CI 配置。
7. 条件允许时运行测试。
8. 如果测试失败，分析失败原因并生成修复计划。
9. 按覆盖率规则自检生成结果。
10. 输出中文测试报告。

## 覆盖率与质量要求

生成的测试资产应尽量覆盖：

- 页面加载、主要内容渲染和加载态。
- 空态、错误态、未登录或无权限状态。
- 表单必填、合法提交、非法提交和服务端校验错误。
- 表格或列表的搜索、筛选、重置、分页、排序和行操作。
- 弹窗、抽屉、确认框和危险操作。
- 跨页面流程，例如创建后搜索、详情页编辑、删除后验证。
- 页面加载和用户操作对应的接口依赖。

选择器优先级：

1. `data-testid` 或项目已有测试 id 约定。
2. 可访问角色和名称。
3. 表单字段 label。
4. 稳定可见文本。
5. 稳定组件属性。
6. 仅在没有更好方式时使用 CSS 选择器。

## 许可证

此 Skill 为个人独立实现，采用 Apache License 2.0。详见 [LICENSE](LICENSE)。

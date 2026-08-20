import { describe, expect, it } from "vitest";
import {
  fingerprintToolCall,
  isDependencyInstall,
  isHighConfidenceSecretPath,
  isMixedSecretPath,
  observeToolRisk,
  ToolApprovalBook,
  type ToolCapability,
} from "../src/tool-risk/index.ts";

describe("Feature: SBTD 运行时工作流与门禁 - Tool 能力注册表", () => {
  it.each([
    ["read", "local-read", false],
    ["grep", "local-read", false],
    ["glob", "local-read", false],
    ["lsp", "local-read", false],
    ["ast_grep", "local-read", false],
    ["inspect_image", "local-read", false],
    ["web_search", "external-read", false],
    ["ask", "coordination", false],
    ["todo", "coordination", false],
    ["debug", "diagnostic", false],
    ["recall", "diagnostic", false],
    ["write", "workspace-write", true],
    ["edit", "workspace-write", true],
    ["bash", "destructive", true],
    ["eval", "destructive", true],
    ["browser", "external-write", true],
    ["github", "external-write", true],
    ["task", "external-write", true],
    ["sbtd_workflow", "phase-transition", true],
    ["mcp__server_tool", "unknown", true],
    ["never-heard-of-this", "unknown", true],
  ] as const)("Scenario: 工具 %s 分类为 %s", (toolName, capability, mutation) => {
    const observation = observeToolRisk({ toolName, input: {} });
    expect(observation.capability satisfies ToolCapability).toBe(capability);
    expect(observation.mutationOrPhaseAdvancing).toBe(mutation);
  });

  it("Scenario: 缺少 toolName 的畸形事件按 unknown fail closed", () => {
    const observation = observeToolRisk({ input: {} });
    expect(observation.capability).toBe("unknown");
    expect(observation.mutationOrPhaseAdvancing).toBe(true);
  });

  it("Scenario: SSH 远程读取不冒充本地只读", () => {
    const observation = observeToolRisk({
      toolName: "read",
      input: { path: "ssh://host/etc/hostname" },
    });
    expect(observation.capability).toBe("external-read");
    expect(observation.remote).toBe(true);
    expect(observation.mutationOrPhaseAdvancing).toBe(true);
  });

  it("Scenario: 本地路径 read 保持 local-read", () => {
    const observation = observeToolRisk({
      toolName: "read",
      input: { path: "src/extension.ts:10-20" },
    });
    expect(observation.capability).toBe("local-read");
    expect(observation.remote).toBe(false);
    expect(observation.mutationOrPhaseAdvancing).toBe(false);
  });
});

describe("Feature: SBTD 运行时工作流与门禁 - 依赖变更识别", () => {
  it.each([
    "npm install lodash",
    "npm i lodash",
    "npm ci",
    "pnpm add example-package",
    "pnpm i",
    "bun add lodash",
    "yarn add lodash",
    "yarn install",
    "yarn",
    "sudo npm install -g typescript",
    "corepack pnpm add example-package",
    "cd x && npm install",
    "  npm install",
    "cd x\nnpm install",
    "pip install requests",
    "pip3 install requests",
    "uv pip install requests",
    "python -m pip install requests",
    "python3 -m pip install --user requests",
    "brew install wget",
    "cargo install ripgrep",
    "cargo add serde",
    "npx create-vite@latest demo",
    "bunx cowsay",
    "dotnet add package Newtonsoft.Json",
    "nuget install Newtonsoft.Json",
    "Install-Package Newtonsoft.Json",
    "choco install git",
    "winget install Git.Git",
    "composer install",
    "composer require guzzlehttp/guzzle",
    "go get example.com/module",
    "go install example.com/tool@latest",
    "go mod tidy",
    "go mod download",
    "cd app; npm install",
    "npm install || echo failed",
    "NODE_ENV=development npm install",
    "bash -c 'npm install'",
    'powershell -Command "npm install"',
    'pwsh -Command "Install-Package Newtonsoft.Json"',
    'powershell -command "npm i lodash"',
    "pwsh -CommandWithArgs npm install",
  ])("Scenario: 高置信依赖变更被识别: %s", (command) => {
    expect(isDependencyInstall(command)).toBe(true);
    expect(
      observeToolRisk({ toolName: "bash", input: { command } })
        .installingDependency,
    ).toBe(true);
  });

  it.each([
    "npm ls",
    "npm view lodash",
    "npm run install-deps",
    "npm config get registry",
    "pip show requests",
    "pip list",
    "go list -m all",
    "go build ./...",
    "go vet ./...",
    "composer show",
    "dotnet build",
    "dotnet restore --locked-mode || true; npm ls",
    "git status",
    "ls node_modules",
    "echo npm install",
    "npm --version",
    "yarn --version",
    "python -m pytest",
  ])("Scenario: 纯查询或非安装命令不误报: %s", (command) => {
    expect(isDependencyInstall(command)).toBe(false);
  });
});

describe("Feature: SBTD 运行时工作流与门禁 - 秘密访问识别", () => {
  it.each([
    ".env",
    ".env.local",
    ".envrc",
    ".netrc",
    ".git-credentials",
    ".npmrc",
    ".pypirc",
    ".ssh/id_ed25519",
    "home/user/.ssh",
    "id_rsa",
    ".docker/config.json",
    ".kube/config",
    ".aws/credentials",
    ".config/gcloud/credentials.db",
    ".azure/accessTokens.json",
    ".pgpass",
    ".my.cnf",
    ".mylogin.cnf",
    "auth.json",
    ".composer/auth.json",
    "secrets/private.p12",
    "secrets/private.pfx",
    "certs/server.pem",
    "certs/server.key",
    "store.keystore",
    "store.jks",
    ".gnupg/secring.gpg",
    "C:/Users/me/.aws/credentials",
    "C:\\Users\\me\\.aws\\credentials",
    ".microsoft/usersecrets/abc/secrets.json",
  ])("Scenario: 高置信秘密路径被识别: %s", (path) => {
    expect(isHighConfidenceSecretPath(path)).toBe(true);
    expect(
      observeToolRisk({ toolName: "read", input: { path } }).secretRead,
    ).toBe(true);
  });

  it.each([
    "README.md",
    "src/config.ts",
    "appsettings.Development.json",
    "certs/public.crt",
    "certs/ca.cer",
    ".env.example",
    ".env.sample",
    ".env.template",
    "id_rsa.pub",
    "nuget.config",
    ".aws/config",
    "package.json",
  ])("Scenario: 公开或混合路径不被硬阻断: %s", (path) => {
    expect(isHighConfidenceSecretPath(path)).toBe(false);
    expect(
      observeToolRisk({ toolName: "read", input: { path } }).secretRead,
    ).toBe(false);
  });

  it("Scenario: 混合公开配置作为可配置观察暴露", () => {
    expect(isMixedSecretPath("appsettings.Development.json")).toBe(true);
    expect(isMixedSecretPath(".env.example")).toBe(true);
    expect(isMixedSecretPath("certs/public.crt")).toBe(true);
    expect(
      observeToolRisk({
        toolName: "read",
        input: { path: "appsettings.Development.json" },
      }).mixedSecretAccess,
    ).toBe(true);
  });

  it.each([
    "cat .envrc",
    "cat .netrc",
    "cat .git-credentials",
    "cat .npmrc",
    "cat .docker/config.json",
    "cat .kube/config",
    "cat .aws/credentials",
    "cat .pgpass",
    "cat server.p12",
    "cat server.pfx",
    "Get-Content .env",
    "gc .env",
    "type .env",
    "cmd /c type .env",
    "type C:\\Users\\me\\.env",
    "git show HEAD:.env",
    "dd if=.env of=/tmp/copy",
    "base64 .env",
    "openssl enc -d -in .env",
    "tar czf backup.tgz .env",
    "bash -c 'cat .env'",
    "grep password .env",
    "head -n 5 .npmrc",
    "cat < .env",
  ])("Scenario: 高置信秘密读取命令被识别: %s", (command) => {
    expect(
      observeToolRisk({ toolName: "bash", input: { command } }).secretRead,
    ).toBe(true);
  });

  it.each([
    'grep ".env" src/config.ts',
    "rg '.env' README.md docs/",
    "git status",
    "echo .env",
    "ls -la",
    "npm test",
  ])("Scenario: 提及或无关命令不被误判为秘密读取: %s", (command) => {
    expect(
      observeToolRisk({ toolName: "bash", input: { command } }).secretRead,
    ).toBe(false);
  });
});

describe("Feature: SBTD 运行时工作流与门禁 - 类型化单次批准", () => {
  const installCall = {
    toolCallId: "call-1",
    toolName: "bash",
    input: { command: "pnpm add example-package" },
  };
  const secretCall = {
    toolCallId: "call-2",
    toolName: "read",
    input: { path: ".env" },
  };

  it("Scenario: 批准只授予被阻断的 pending descriptor", () => {
    const approvals = new ToolApprovalBook();
    // Approving a call that was never blocked does nothing.
    approvals.resolve("call-2", true);
    expect(observeToolRisk(secretCall, approvals).secretReadApproved).toBe(
      false,
    );
  });

  it("Scenario: 精确批准的秘密读取只放行一次", () => {
    const approvals = new ToolApprovalBook();
    const blocked = observeToolRisk(secretCall, approvals);
    expect(blocked.secretRead).toBe(true);
    expect(blocked.secretReadApproved).toBe(false);
    approvals.recordBlocked("call-2", blocked.riskClasses, blocked.fingerprint);
    approvals.resolve("call-2", true);
    expect(observeToolRisk(secretCall, approvals).secretReadApproved).toBe(
      true,
    );
    approvals.consume("call-2");
    expect(observeToolRisk(secretCall, approvals).secretReadApproved).toBe(
      false,
    );
  });

  it("Scenario: 安装批准与秘密读取批准不互换", () => {
    const approvals = new ToolApprovalBook();
    const blockedInstall = observeToolRisk(installCall, approvals);
    approvals.recordBlocked(
      "call-1",
      blockedInstall.riskClasses,
      blockedInstall.fingerprint,
    );
    approvals.resolve("call-1", true);
    expect(observeToolRisk(installCall, approvals).installApproved).toBe(true);
    // The same tool-call ID cannot authorize a secret read.
    const secretReplay = {
      toolCallId: "call-1",
      toolName: "read",
      input: { path: ".env" },
    };
    expect(observeToolRisk(secretReplay, approvals).secretReadApproved).toBe(
      false,
    );
  });

  it("Scenario: 改变目标或命令立即使批准失效", () => {
    const approvals = new ToolApprovalBook();
    const blocked = observeToolRisk(secretCall, approvals);
    approvals.recordBlocked("call-2", blocked.riskClasses, blocked.fingerprint);
    approvals.resolve("call-2", true);
    const changed = {
      toolCallId: "call-2",
      toolName: "read",
      input: { path: ".env.production" },
    };
    expect(observeToolRisk(changed, approvals).secretReadApproved).toBe(false);
    // The fingerprint mismatch consumed the approval entirely.
    expect(observeToolRisk(secretCall, approvals).secretReadApproved).toBe(
      false,
    );
  });

  it("Scenario: deny 与 turn 清理消费批准", () => {
    const approvals = new ToolApprovalBook();
    const blocked = observeToolRisk(installCall, approvals);
    approvals.recordBlocked("call-1", blocked.riskClasses, blocked.fingerprint);
    approvals.resolve("call-1", false);
    expect(observeToolRisk(installCall, approvals).installApproved).toBe(false);
    approvals.recordBlocked("call-1", blocked.riskClasses, blocked.fingerprint);
    approvals.resolve("call-1", true);
    approvals.clear();
    expect(observeToolRisk(installCall, approvals).installApproved).toBe(false);
  });

  it("Scenario: fingerprint 忽略无关瞬态字段但绑定工具与输入", () => {
    const first = fingerprintToolCall(installCall);
    const sameInputDifferentId = fingerprintToolCall({
      ...installCall,
      toolCallId: "other-id",
    });
    const changedInput = fingerprintToolCall({
      ...installCall,
      input: { command: "pnpm add other-package" },
    });
    expect(first).toBe(sameInputDifferentId);
    expect(first).not.toBe(changedInput);
  });
});

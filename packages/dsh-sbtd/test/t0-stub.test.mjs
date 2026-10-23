import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import { SBTD_SECTION_TEXT } from "../dist/section.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

test("插件加载时打印 T0 stub 日志并注册非空中文 sbtd section", () => {
  const logs = [];
  const original = console.log;
  console.log = (...args) => {
    logs.push(args.join(" "));
  };
  const sections = [];
  try {
    apply({
      systemPrompt: {
        section(opts) {
          sections.push(opts);
        },
      },
      tools: {
        register() {},
      },
      on() {},
    });
  } finally {
    console.log = original;
  }

  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt", "commands"]);
  assert.deepEqual(logs, ["[dsh-sbtd] plugin loaded (T0 stub)"]);
  assert.deepEqual(sections, [{ name: "sbtd", order: 50, text: SBTD_SECTION_TEXT }]);
  assert.ok(sections[0].text.length > 0);
});

test("包声明支持的宿主范围与发布文件清单", () => {
  const pkg = JSON.parse(readFileSync(join(pkgRoot, "package.json"), "utf8"));

  assert.equal(pkg.peerDependencies["@deepseek-ai/dsh"], ">=0.2.0-rc.2 <0.3.0-0");
  // 0.2.1+ hosts let engines.dsh decide alone; it must carry the same range.
  assert.equal(pkg.engines.dsh, ">=0.2.0-rc.2 <0.3.0-0");
  // Local build/test host fact: exact pin at the range floor (R2 Q2 A).
  assert.equal(pkg.devDependencies["@deepseek-ai/dsh"], "0.2.0-rc.2");
  assert.deepEqual(pkg.files, [
    "dist/",
    "cordis.patch.yml",
    "manuals/",
    "CHANGELOG.md",
    "CHANGELOG.zh.md",
  ]);
});

test("0.2.0-rc.2 包可发布且标记为 dsh-plugin", () => {
  const pkg = JSON.parse(readFileSync(join(pkgRoot, "package.json"), "utf8"));

  assert.equal(pkg.private, false);
  assert.equal(pkg.version, "0.2.0-rc.2");
  assert.ok(pkg.keywords.includes("dsh-plugin"));
});

test("cordis patch name 使用已安装的 npm 包名", () => {
  const pkg = JSON.parse(readFileSync(join(pkgRoot, "package.json"), "utf8"));
  const patch = readFileSync(join(pkgRoot, "cordis.patch.yml"), "utf8");

  assert.equal(pkg.name, "@kunolu/dsh-sbtd");
  assert.equal(name, "dsh-sbtd");
  assert.match(patch, /^\s+- id:\s*sbtd\s*$/m);
  assert.match(patch, /^\s+name:\s*"?@kunolu\/dsh-sbtd"?\s*$/m);
  assert.doesNotMatch(patch, /^\s+name:\s*dsh-sbtd\s*$/m);
});

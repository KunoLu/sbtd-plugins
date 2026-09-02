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
    });
  } finally {
    console.log = original;
  }

  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.deepEqual(logs, ["[dsh-sbtd] plugin loaded (T0 stub)"]);
  assert.deepEqual(sections, [{ name: "sbtd", order: 50, text: SBTD_SECTION_TEXT }]);
  assert.ok(sections[0].text.length > 0);
});

test("README 钉 0.1.1-rc.2 并说明 @next 安装命令", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  const pkg = JSON.parse(readFileSync(join(pkgRoot, "package.json"), "utf8"));

  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd@next/);
  assert.doesNotMatch(readme, /\/absolute\/path\/to\/sbtd-plugins\/packages\/dsh-sbtd/);
  assert.doesNotMatch(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd(?!@next)/);
  assert.doesNotMatch(readme, /0\.1\.0-rc\.7|0\.1\.2-alpha/);
  assert.equal(pkg.peerDependencies["@deepseek-ai/dsh"], "0.1.1-rc.2");
  assert.deepEqual(pkg.files, ["dist/", "cordis.patch.yml", "manuals/"]);
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

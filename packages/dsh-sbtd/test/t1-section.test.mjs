import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import {
  SBTD_SECTION_NAME,
  SBTD_SECTION_ORDER,
  SBTD_SECTION_TEXT,
} from "../dist/section.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

test("section plaintext 快照为中文 6.1 短规则且不超过 2048 字节", () => {
  const snapshot = readFileSync(
    join(pkgRoot, "test/snapshots/sbtd-section.txt"),
    "utf8",
  ).replace(/\n$/, "");

  assert.equal(SBTD_SECTION_TEXT, snapshot);
  assert.ok(SBTD_SECTION_TEXT.length > 0);
  assert.ok(Buffer.byteLength(SBTD_SECTION_TEXT, "utf8") <= 2048);
  assert.match(SBTD_SECTION_TEXT, /sbtd_plan/);
  assert.match(SBTD_SECTION_TEXT, /sbtd_clarify/);
  assert.match(SBTD_SECTION_TEXT, /sbtd_validate/);
  assert.match(SBTD_SECTION_TEXT, /sbtd_e2e/);
  assert.match(SBTD_SECTION_TEXT, /sbtd_review/);
  assert.match(SBTD_SECTION_TEXT, /Maestro/);
  assert.doesNotMatch(SBTD_SECTION_TEXT, /AGENTS\.md/);
});

test("apply 注册非空中文 sbtd section 且不写磁盘", () => {
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
    });
  } finally {
    console.log = original;
  }

  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.deepEqual(logs, ["[dsh-sbtd] plugin loaded (T0 stub)"]);
  assert.deepEqual(sections, [
    {
      name: SBTD_SECTION_NAME,
      order: SBTD_SECTION_ORDER,
      text: SBTD_SECTION_TEXT,
    },
  ]);
  assert.ok(sections[0].text.length > 0);

  for (const rel of ["src/index.ts", "src/section.ts", "src/state.ts"]) {
    const src = readFileSync(join(pkgRoot, rel), "utf8");
    assert.doesNotMatch(src, /writeFile|AGENTS\.md/);
  }
});

test("README 钉 0.1.1-rc.2、@next 安装并提到短中文 sbtd section", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  const pkg = JSON.parse(readFileSync(join(pkgRoot, "package.json"), "utf8"));

  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd@next/);
  assert.match(readme, /短中文 sbtd section/);
  assert.doesNotMatch(
    readme,
    /\/absolute\/path\/to\/sbtd-plugins\/packages\/dsh-sbtd/,
  );
  assert.doesNotMatch(
    readme,
    /dsh plugin --profile web add @kunolu\/dsh-sbtd(?!@next)/,
  );
  assert.doesNotMatch(readme, /0\.1\.0-rc\.7|0\.1\.2-alpha/);
  assert.equal(pkg.peerDependencies["@deepseek-ai/dsh"], "0.1.1-rc.2");
  assert.equal(pkg.private, true);
});

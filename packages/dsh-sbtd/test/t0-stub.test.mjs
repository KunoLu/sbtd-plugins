import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import { SBTD_SECTION_TEXT } from "../dist/section.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const releaseVersion = "0.2.0-rc.3";

function isCurrentReleasePrepared(readme, version) {
  const rows = readme.split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("|") && line.endsWith("|"))
    .map((line) => line.split("|").slice(1, -1)
      .map((cell) => cell.replace(/[`*_]/g, "").trim()))
    .filter((cells) => cells[0] === version);
  if (rows.length !== 1 || rows[0].length !== 2) return false;
  const state = rows[0][1];
  const preparationLabels = /\b(?:preparation|prepared|unpublished|unreleased)\b|\bnot(?: yet)? (?:published|released)\b|准备中|(?:尚)?未发布/gi;
  const withoutLabels = state.replace(preparationLabels, "");
  // A current-version status cell may only contain preparation labels and punctuation.
  return withoutLabels !== state
    && withoutLabels.replace(/[\s()（）\/—–.,，;；:\-]/g, "") === "";
}

test("发布状态校验：当前版本准备态通过", () => {
  for (const state of ["Preparation", "Not yet published", "Preparation — not yet published", "准备中", "尚未发布", "准备中（尚未发布）"]) {
    assert.equal(
      isCurrentReleasePrepared(`| ${releaseVersion} | ${state} |`, releaseVersion),
      true,
      state,
    );
  }
});

test("发布状态校验：当前版本误称已发布被拒绝", () => {
  for (const state of ["Published", "Released", "Preparation; published", "已发布", "已经发布", "准备中；已发布", "准备中；已于 2026-11-18 发布", "Not not yet published"]) {
    assert.equal(
      isCurrentReleasePrepared(`| ${releaseVersion} | ${state} |`, releaseVersion),
      false,
      state,
    );
  }
  assert.equal(isCurrentReleasePrepared("| 0.2.0-rc.2 | Published |", releaseVersion), false);
  assert.equal(isCurrentReleasePrepared(
    `| ${releaseVersion} | Preparation |\n| ${releaseVersion} | Published |`,
    releaseVersion,
  ), false);
});

test("发布状态校验：旧版发布史不误伤", () => {
  for (const [prepared, historical] of [
    ["Preparation — not yet published", "Published on 2026-10-23"],
    ["准备中（尚未发布）", "已于 2026-10-23 发布"],
  ]) {
    const current = `| ${releaseVersion} | ${prepared} |`;
    const history = `| 0.2.0-rc.2 | ${historical} |`;
    assert.equal(isCurrentReleasePrepared(`${current}\n${history}`, releaseVersion), true);
    assert.equal(isCurrentReleasePrepared(`${history}\n${current}`, releaseVersion), true);
    assert.equal(isCurrentReleasePrepared(
      `${history}\n| ${releaseVersion} | Published / 已发布 |`,
      releaseVersion,
    ), false);
  }
});

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

for (const filename of ["README.md", "README.zh.md"]) {
  test(`${filename} 钉 0.2.0-rc.2 并说明 @next 安装命令`, () => {
    const readme = readFileSync(join(pkgRoot, filename), "utf8");

    assert.match(readme, /@deepseek-ai\/dsh@0\.2\.0-rc\.2/);
    assert.match(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd@next/);
    assert.doesNotMatch(
      readme,
      /dsh plugin --profile web add @kunolu\/dsh-sbtd(?!@next)/,
    );
    assert.doesNotMatch(
      readme,
      /\/absolute\/path\/to\/sbtd-plugins\/packages\/dsh-sbtd/,
    );
    assert.doesNotMatch(readme, /0\.1\.0-rc\.7|0\.1\.2-alpha/);
  });

  test(`${filename} 当前插件版本保持准确准备态`, () => {
    const readme = readFileSync(join(pkgRoot, filename), "utf8");

    assert.equal(isCurrentReleasePrepared(readme, releaseVersion), true);
  });

  test(`${filename} 顶部语言切换钉 release tag`, () => {
    const readme = readFileSync(join(pkgRoot, filename), "utf8");
    const switcher = readme.match(/^<p align="center">[\s\S]*?<\/p>/)?.[0];

    assert.ok(switcher, "language switcher must precede the README body");
    for (const target of ["README.md", "README.zh.md"]) {
      assert.ok(
        switcher.includes(
          `href="https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.3/packages/dsh-sbtd/${target}"`,
        ),
        `missing release-tag-pinned link to ${target}`,
      );
    }
  });
}

test("双语 README 的二级与三级标题数量一致", () => {
  const english = readFileSync(join(pkgRoot, "README.md"), "utf8");
  const chinese = readFileSync(join(pkgRoot, "README.zh.md"), "utf8");

  for (const heading of [/^## /gm, /^### /gm]) {
    assert.equal(
      (english.match(heading) ?? []).length,
      (chinese.match(heading) ?? []).length,
      `heading count differs for ${heading}`,
    );
  }
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

test("0.2.0-rc.3 包可发布且标记为 dsh-plugin", () => {
  const pkg = JSON.parse(readFileSync(join(pkgRoot, "package.json"), "utf8"));

  assert.equal(pkg.private, false);
  assert.equal(pkg.version, "0.2.0-rc.3");
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

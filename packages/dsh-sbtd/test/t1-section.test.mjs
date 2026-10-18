import assert from "node:assert/strict";
import { test } from "node:test";
import { apply, inject, name } from "../dist/index.js";
import {
  SBTD_SECTION_NAME,
  SBTD_SECTION_ORDER,
  SBTD_SECTION_TEXT,
} from "../dist/section.js";


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
      on() {},
    });
  } finally {
    console.log = original;
  }

  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt", "commands"]);
  assert.deepEqual(logs, ["[dsh-sbtd] plugin loaded (T0 stub)"]);
  assert.deepEqual(sections, [
    {
      name: SBTD_SECTION_NAME,
      order: SBTD_SECTION_ORDER,
      text: SBTD_SECTION_TEXT,
    },
  ]);
  assert.ok(sections[0].text.length > 0);
});

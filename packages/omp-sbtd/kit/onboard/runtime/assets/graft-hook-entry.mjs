#!/usr/bin/env node
/**
 * SBTD managed Graft hook bridge (P1-04) — the version-pinned adapter that
 * replaces the upstream generated `graft-hooks.cjs` shim.
 *
 * The upstream shim is dynamic: it searches the baked init-time dir, the
 * repo's node_modules, a legacy prefix guess and finally `npm root -g`, picks
 * the HIGHEST version found, and swallows every failure into a silent no-op.
 * None of that exists here. The managed launcher (`sbtd_graft_entry.py hook`)
 * has already proven the exact pinned `@nanonets/graft@0.22.0` package, the
 * canonical selected root, the complete current wiring stamp and the graph,
 * and runs this bridge with the scrubbed managed environment. This bridge
 * therefore imports ONLY the exact validated `dist/claude/hooks.js` it is
 * handed and calls its `main(event)` — no candidate search, no npm lookup,
 * no version shopping, no fallback entry, no silent no-op.
 *
 * Not an upstream-supported API: it is pinned to the validated 0.22.0 module
 * shape (`main(event)`), which the launcher re-proves on every event.
 *
 * Protocol discipline: this bridge writes nothing to stdout — the native
 * module's hook JSON output flows through untouched. Every failure is one
 * fixed line on stderr and exit code 2. stdin is consumed by the native
 * module itself (the original event payload, forwarded by the launcher).
 *
 * Usage (exactly, anything else fails closed):
 *   node graft-hook-entry.mjs --entry ABS/dist/claude/hooks.js --event NAME
 * where NAME is one of: session-start, prompt, post-edit, stop.
 */
import { isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';

const EVENTS = new Set(['session-start', 'prompt', 'post-edit', 'stop']);
const ENTRY_SUFFIX = '/dist/claude/hooks.js';

function fail(message) {
  process.stderr.write(`sbtd-graft-hook-entry: ${message}\n`);
  return 2;
}

/** Exactly `--entry <path> --event <name>` in any order, no duplicates. */
function parseArgs(argv) {
  const parsed = { entry: null, event: null };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (
      (flag === '--entry' || flag === '--event') &&
      value !== undefined &&
      !value.startsWith('--')
    ) {
      const key = flag.slice(2);
      if (parsed[key] !== null) return null;
      parsed[key] = value;
      index += 1;
      continue;
    }
    return null;
  }
  return parsed.entry !== null && parsed.event !== null ? parsed : null;
}

async function run(argv) {
  const args = parseArgs(argv);
  if (args === null) {
    return fail('expected exactly --entry <absolute pinned hooks.js> --event <name>');
  }
  if (!EVENTS.has(args.event)) {
    return fail('unsupported hook event');
  }
  if (!isAbsolute(args.entry)) {
    return fail('the hook module path is not absolute');
  }
  if (!args.entry.replace(/\\/g, '/').endsWith(ENTRY_SUFFIX)) {
    return fail('the hook module is not the pinned package dist/claude/hooks.js');
  }
  let mod;
  try {
    mod = await import(pathToFileURL(args.entry).href);
  } catch {
    return fail('the validated Graft hook module could not be loaded');
  }
  if (typeof mod.main !== 'function') {
    return fail('the validated Graft hook module has no main export');
  }
  // Upstream Stop detaches sync-run and can outlive the launcher's private HOME.
  // Run that same pinned structural sync synchronously under its native lock,
  // then invoke Stop only after it can no longer spawn a detached rebuild.
  if (args.event === 'stop') {
    const root = process.env.CLAUDE_PROJECT_DIR;
    if (!root || !isAbsolute(root)) return fail('the selected project root is unavailable');
    try {
      const moduleUrl = pathToFileURL(args.entry);
      const state = await import(new URL('./state.js', moduleUrl).href);
      if (state.readStats(root)?.dirty) {
        const sync = await import(new URL('./sync-run.js', moduleUrl).href);
        if (typeof sync.runSync !== 'function') return fail('the fixed graph sync is unavailable');
        if (!state.acquireLock(root)) return fail('the graph sync is busy');
        sync.runSync(root);
        if (state.readStats(root)?.dirty) return fail('the structural graph sync did not complete');
      }
    } catch {
      return fail('the controlled structural graph sync failed');
    }
  }
  try {
    await mod.main(args.event);
  } catch {
    return fail('the Graft hook handler failed');
  }
  return 0;
}

process.exitCode = await run(process.argv.slice(2));

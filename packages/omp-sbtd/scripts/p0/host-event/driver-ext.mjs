// Slice 5 Host Event Surface suite — driver companion extension (promoted
// from the Gate 0.2 spike driver-ext). RPC mode exposes no `navigate_tree`
// command, so the only stable public Host entry for `session_tree` is the
// ExtensionCommandContext.navigateTree API (the same API the TUI tree
// navigation uses; the Host itself emits the real `session_tree` event from
// agent-session). This extension adds one `/spike` command that invokes that
// public Host API. It never touches the candidate Plugin, never emits events
// itself, and returns no policy results.
// Diagnostics go to SPIKE_DRIVER_EXT_LOG as digests/flags only.
import { appendFileSync } from "node:fs";

const log = (entry) => {
  const path = process.env.SPIKE_DRIVER_EXT_LOG;
  if (typeof path === "string" && path.length > 0)
    appendFileSync(
      path,
      `${JSON.stringify({ runId: process.env.HOST_EVENT_RUN_ID, ...entry })}\n`,
      "utf8",
    );
};

export default function hostEventDriver(pi) {
  pi.registerCommand("spike", {
    description: "Host Event suite driver (tree navigation trigger).",
    handler: async (args, ctx) => {
      const [action, target] = args.trim().split(/\s+/);
      if (
        action === "tree" &&
        typeof target === "string" &&
        target.length > 0
      ) {
        try {
          const result = await ctx.navigateTree(target, { summarize: false });
          log({
            action: "tree",
            cancelled: result.cancelled === true,
            ok: true,
          });
        } catch (error) {
          // Diagnostic only (driver-ext log is not evidence): record a
          // stable Error name only. Host exception text can carry local
          // paths or other PII and must never be persisted.
          log({
            action: "tree",
            ok: false,
            errorName: error instanceof Error ? error.name : "unknown",
          });
        }
        return;
      }
      log({ action: "unknown", ok: false });
    },
  });
}

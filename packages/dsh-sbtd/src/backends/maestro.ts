/**
 * Maestro preflight backend (T12) — hybrid six-step check.
 *
 * Locks: Q1A–Q6A.
 * Steps 1–3 live-probed (injectable). Steps 4–6 declared facts (never invent).
 * Never spawns `maestro test`. Never silent-installs. Never writes maestro/flow/.
 * Never registers apply() tools (T13 mounts sbtd_e2e).
 */

import { spawnSync } from "node:child_process";
import { getSession } from "../state.js";

export type DeviceClass = "sim" | "emulator" | "usb" | "cloud";

export type PlatformHint = "ios" | "android";

export type JavaProbe = {
  ok: boolean;
  version?: string;
  detail?: string;
};

export type CliProbe = {
  ok: boolean;
  version?: string;
  detail?: string;
};

export type DeviceProbe = {
  ok: boolean;
  /** Resolved device class when available (incl. declared cloud). */
  class?: DeviceClass;
  detail?: string;
};

export type PreflightProbes = {
  java?: JavaProbe;
  cli?: CliProbe;
  device?: DeviceProbe;
};

export type PreflightResult = {
  lastPreflight: "ok" | "blocked";
  missing: string[];
  guidance: string;
  probes?: PreflightProbes;
};

/**
 * Host / test options. Trust handles (cwd, detect*, declared facts, sessionId)
 * are host-injected — never model-controlled. Model may only supply `platform`.
 */
export type MaestroOptions = {
  /** Host-injected project cwd (Q4A). Not a model-trust arg. */
  cwd?: string;
  /** Model-visible platform hint only (Q4A). */
  platform?: PlatformHint;
  /** Session id for optional session.maestro write (Q3A). */
  sessionId?: string;
  /** Skip writing session.maestro when true. */
  skipSessionWrite?: boolean;

  // --- Declared facts (steps 4–6); never invent ---
  /** Step 4: app installed in the target env. */
  appInstalled?: boolean;
  /** Step 5: in-app test / virtual env (URL, launch args, flags, start screen). */
  appEnv?: string | boolean;
  /** Step 6: bundleId / applicationId. */
  appId?: string;
  /** Step 6 alias for appId. */
  bundleId?: string;
  /** Step 6: test accounts / data isolation confirmed. */
  accounts?: string | boolean;
  /**
   * Step 3 cloud (Q6A): host/user declaration of device class.
   * Cloud records in probes without run/upload. Local classes equally valid.
   */
  deviceClass?: DeviceClass;
  /** Optional declared device id (user-confirmed). */
  deviceId?: string;

  // --- Injectable live probes (tests / host) ---
  detectJava?: () => JavaProbe | Promise<JavaProbe>;
  detectCli?: () => CliProbe | Promise<CliProbe>;
  detectDevice?: (
    options: MaestroOptions,
  ) => DeviceProbe | Promise<DeviceProbe>;
};

/** T10 forbid list — must not be treated as model-trust args (Q4A). */
export const FORBIDDEN_MODEL_KEYS = [
  "cwd",
  "mcp",
  "runRefresh",
  "serverName",
  "toolNames",
] as const;

export type ForbiddenModelKey = (typeof FORBIDDEN_MODEL_KEYS)[number];

/** Model-visible input surface: platform hint only. */
export type MaestroModelInput = {
  platform?: PlatformHint;
};

const MISSING_JAVA = "java";
const MISSING_CLI = "cli";
const MISSING_DEVICE = "device";
const MISSING_APP = "app";
const MISSING_APP_ENV = "appEnv";
const MISSING_IDENTITY = "identity";

function parseJavaMajor(text: string): number | null {
  // OpenJDK / Temurin style: version "21.0.2" or 21.0.2 / 1.8.0_xxx
  const quoted = text.match(/version\s+"([^"]+)"/i);
  const bare = text.match(/\b(\d+)(?:\.(\d+))?(?:\.(\d+))?/);
  const raw = quoted?.[1] ?? (bare ? bare[0] : null);
  if (!raw) return null;
  const parts = raw.split(".");
  if (parts[0] === "1" && parts[1]) {
    const n = Number(parts[1]);
    return Number.isFinite(n) ? n : null;
  }
  const n = Number(parts[0]);
  return Number.isFinite(n) ? n : null;
}

/**
 * Default Java 17+ probe: `java --version`, fallback `java -version`.
 * Never throws.
 */
export function defaultDetectJava(): JavaProbe {
  try {
    for (const args of [["--version"], ["-version"]] as const) {
      const result = spawnSync("java", [...args], {
        encoding: "utf8",
        timeout: 8_000,
        env: process.env,
      });
      const text = `${result.stdout ?? ""}\n${result.stderr ?? ""}`.trim();
      if (result.error && (result.error as NodeJS.ErrnoException).code === "ENOENT") {
        continue;
      }
      if (!text && result.status !== 0) continue;
      const major = parseJavaMajor(text);
      const firstLine = text.split("\n")[0] ?? "";
      if (major != null && major >= 17) {
        return firstLine
          ? { ok: true, version: String(major), detail: firstLine }
          : { ok: true, version: String(major) };
      }
      if (major != null) {
        return {
          ok: false,
          version: String(major),
          detail: `Java ${major} found; Maestro requires 17+`,
        };
      }
      if (text) {
        return firstLine
          ? { ok: false, detail: firstLine }
          : { ok: false, detail: "unparseable java version output" };
      }
    }
    return { ok: false, detail: "java not found on PATH" };
  } catch (err) {
    return {
      ok: false,
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}

/**
 * Default Maestro CLI probe: `maestro --version` only (never `maestro test`).
 * Never throws.
 */
export function defaultDetectCli(): CliProbe {
  try {
    const result = spawnSync("maestro", ["--version"], {
      encoding: "utf8",
      timeout: 8_000,
      env: process.env,
    });
    if (result.error && (result.error as NodeJS.ErrnoException).code === "ENOENT") {
      return { ok: false, detail: "maestro not found on PATH" };
    }
    const text = `${result.stdout ?? ""}\n${result.stderr ?? ""}`.trim();
    if (result.status === 0 && text) {
      const first = (text.split("\n")[0] ?? "").trim() || text.trim();
      return { ok: true, version: first, detail: first };
    }
    return {
      ok: false,
      detail: text || `maestro --version exited ${result.status ?? "null"}`,
    };
  } catch (err) {
    return {
      ok: false,
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}

/**
 * Default device probe. Cloud / declared deviceClass is first-class (Q6A)
 * and records without cloud run/upload. Local listing is best-effort.
 * Never throws. Never spawns `maestro test`.
 */
export function defaultDetectDevice(options: MaestroOptions = {}): DeviceProbe {
  try {
    if (options.deviceClass === "cloud") {
      return {
        ok: true,
        class: "cloud",
        detail: "cloud device class declared (no cloud run/upload in T12)",
      };
    }
    if (
      options.deviceClass === "sim" ||
      options.deviceClass === "emulator" ||
      options.deviceClass === "usb"
    ) {
      return {
        ok: true,
        class: options.deviceClass,
        detail: options.deviceId
          ? `declared ${options.deviceClass} (${options.deviceId})`
          : `declared ${options.deviceClass}`,
      };
    }

    // Best-effort local listing (never maestro test).
    const platform = options.platform;
    if (platform !== "android") {
      const sim = spawnSync("xcrun", ["simctl", "list", "devices", "available"], {
        encoding: "utf8",
        timeout: 10_000,
        env: process.env,
      });
      const out = `${sim.stdout ?? ""}\n${sim.stderr ?? ""}`;
      if (
        sim.status === 0 &&
        /Booted|\(Booted\)|iPhone|iPad/i.test(out) &&
        !/No devices|unable to find|xcrun: error/i.test(out)
      ) {
        return { ok: true, class: "sim", detail: "iOS Simulator available" };
      }
    }
    if (platform !== "ios") {
      const adb = spawnSync("adb", ["devices"], {
        encoding: "utf8",
        timeout: 10_000,
        env: process.env,
      });
      const out = `${adb.stdout ?? ""}`;
      const lines = out
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith("List of devices"));
      const online = lines.filter((l) => /\tdevice$/.test(l));
      if (adb.status === 0 && online.length > 0) {
        const isEmu = online.some((l) => /emulator-/i.test(l));
        return {
          ok: true,
          class: isEmu ? "emulator" : "usb",
          detail: isEmu
            ? "Android emulator available via adb"
            : "Android USB/device available via adb",
        };
      }
    }

    return {
      ok: false,
      detail:
        "No sim/emulator/USB device detected; declare deviceClass or start a virtual device",
    };
  } catch (err) {
    return {
      ok: false,
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}

function isDeclaredTruthy(value: string | boolean | undefined): boolean {
  if (value === true) return true;
  if (typeof value === "string" && value.trim() !== "") return true;
  return false;
}

function resolveAppId(options: MaestroOptions): string | undefined {
  const id = options.appId ?? options.bundleId;
  if (typeof id === "string" && id.trim() !== "") return id.trim();
  return undefined;
}

/**
 * Pick model-visible args only (`platform`). Rejects T10 trust keys (Q4A).
 * Host/test injection remains on MaestroOptions separately.
 */
export function pickModelInput(args: unknown): MaestroModelInput {
  if (args == null || typeof args !== "object" || Array.isArray(args)) {
    return {};
  }
  const record = args as Record<string, unknown>;
  for (const key of FORBIDDEN_MODEL_KEYS) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      throw new Error(
        `Maestro model input forbids trust handle "${key}" (host-injected only)`,
      );
    }
  }
  const out: MaestroModelInput = {};
  if (record.platform === "ios" || record.platform === "android") {
    out.platform = record.platform;
  } else if (record.platform !== undefined) {
    throw new Error(
      `Maestro platform hint must be "ios" | "android" (got ${JSON.stringify(record.platform)})`,
    );
  }
  return out;
}

/** True when a schema/properties map omits every T10 trust key. */
export function modelSchemaForbidsTrustHandles(
  properties: Record<string, unknown> | null | undefined,
): boolean {
  if (properties == null || typeof properties !== "object") return false;
  for (const key of FORBIDDEN_MODEL_KEYS) {
    if (Object.prototype.hasOwnProperty.call(properties, key)) return false;
  }
  return true;
}

function buildGuidance(missing: string[], platform?: PlatformHint): string {
  if (missing.length === 0) {
    return "Maestro preflight ok: Java 17+, CLI, device, app, in-app test env, and identity/accounts are ready.";
  }

  const lines: string[] = [
    "Maestro preflight blocked. This is a local environment check (not a project dependency).",
    "Missing facts: " + missing.join(", ") + ".",
    "Prepare a virtual device and the target app on this machine, then enter the in-app test environment. Ask before any install — no silent install.",
  ];

  // Acceptance: when app and/or device missing, guidance must mention app AND virtual device.
  if (missing.includes(MISSING_APP) || missing.includes(MISSING_DEVICE)) {
    lines.push(
      "You need both: (1) a virtual device (iOS Simulator / Android Emulator) or USB/cloud device, and (2) the target app installed into that environment.",
    );
  }

  if (missing.includes(MISSING_JAVA)) {
    lines.push(
      "Java 17+ is required (Temurin 21 recommended). Check: `java --version` (fallback `java -version`).",
      "Example install (only after DSH approval): `brew install --cask temurin@21`",
    );
  }
  if (missing.includes(MISSING_CLI)) {
    lines.push(
      "Maestro CLI is a local prerequisite. Check: `maestro --version` (never run `maestro test` during preflight).",
      "Example install (only after DSH approval): `curl -Ls \"https://get.maestro.mobile.dev\" | bash`",
    );
  }
  if (missing.includes(MISSING_DEVICE)) {
    if (platform === "ios") {
      lines.push(
        "Start an iOS Simulator, e.g. `open -a Simulator` then `xcrun simctl list devices available`.",
      );
    } else if (platform === "android") {
      lines.push(
        "Start an Android Emulator or connect USB; check with `adb devices`. Do not auto-create AVDs.",
      );
    } else {
      lines.push(
        "Start iOS Simulator (`open -a Simulator`) or Android Emulator / USB (`adb devices`), or declare deviceClass=cloud|sim|emulator|usb.",
      );
    }
  }
  if (missing.includes(MISSING_APP)) {
    lines.push(
      "Install the target app into the device/simulator (do not auto-install):",
      "  iOS: `xcrun simctl install booted /path/to/App.app`",
      "  Android: `adb install -r /path/to/app.apk`",
    );
  }
  if (missing.includes(MISSING_APP_ENV)) {
    lines.push(
      "Confirm the in-app test/virtual environment (base URL, launch arguments, feature flags, start screen). Missing ⇒ blocked; switch inside the app or provide launch args.",
    );
  }
  if (missing.includes(MISSING_IDENTITY)) {
    lines.push(
      "Confirm bundleId/applicationId and test accounts/data isolation. Missing identity or accounts ⇒ blocked; never invent them.",
    );
  }

  lines.push(
    "If you decline install help, preflight stays blocked / skipped-by-user — other non-mobile work can continue; do not pretend E2E ran.",
  );
  return lines.join("\n");
}

function writeSession(
  sessionId: string | undefined,
  result: PreflightResult,
  probes: PreflightProbes,
  options: MaestroOptions,
): void {
  if (!sessionId || options.skipSessionWrite) return;
  const session = getSession(sessionId);
  session.maestro = {
    lastPreflight: result.lastPreflight,
    missing: [...result.missing],
    ...(probes.java?.ok && probes.java.version
      ? { java: probes.java.version }
      : probes.java?.detail
        ? { java: probes.java.detail }
        : {}),
    ...(probes.cli?.ok && probes.cli.version
      ? { cli: probes.cli.version }
      : probes.cli?.detail
        ? { cli: probes.cli.detail }
        : {}),
    ...(probes.device?.ok && probes.device.class
      ? { device: probes.device.class }
      : probes.device?.detail
        ? { device: probes.device.detail }
        : {}),
    ...(options.appInstalled !== undefined
      ? { appInstalled: Boolean(options.appInstalled) }
      : {}),
    ...(isDeclaredTruthy(options.appEnv)
      ? {
          appEnv:
            typeof options.appEnv === "string"
              ? options.appEnv
              : "declared",
        }
      : {}),
  };
}

/**
 * Hybrid six-step Maestro preflight (Q1A).
 * Never throws for missing env. Never spawns `maestro test`.
 */
export async function preflight(
  options: MaestroOptions = {},
): Promise<PreflightResult> {
  try {
    // Host cwd is accepted on options but not required for declared/stub probes.
    void options.cwd;

    const java = await Promise.resolve(
      (options.detectJava ?? defaultDetectJava)(),
    );
    const cli = await Promise.resolve((options.detectCli ?? defaultDetectCli)());
    const device = await Promise.resolve(
      (options.detectDevice ?? defaultDetectDevice)(options),
    );

    const missing: string[] = [];
    if (!java.ok) missing.push(MISSING_JAVA);
    if (!cli.ok) missing.push(MISSING_CLI);
    if (!device.ok) missing.push(MISSING_DEVICE);

    // Declared facts 4–6 — never invent.
    if (options.appInstalled !== true) missing.push(MISSING_APP);
    if (!isDeclaredTruthy(options.appEnv)) missing.push(MISSING_APP_ENV);
    const appId = resolveAppId(options);
    if (!appId || !isDeclaredTruthy(options.accounts)) {
      missing.push(MISSING_IDENTITY);
    }

    const probes: PreflightProbes = { java, cli, device };
    const lastPreflight = missing.length === 0 ? "ok" : "blocked";
    const guidance = buildGuidance(missing, options.platform);
    const result: PreflightResult = {
      lastPreflight,
      missing,
      guidance,
      probes,
    };

    writeSession(options.sessionId, result, probes, options);
    return result;
  } catch (err) {
    const missing = [
      MISSING_JAVA,
      MISSING_CLI,
      MISSING_DEVICE,
      MISSING_APP,
      MISSING_APP_ENV,
      MISSING_IDENTITY,
    ];
    const guidance =
      buildGuidance(missing, options.platform) +
      `\n(internal: ${err instanceof Error ? err.message : String(err)})`;
    const result: PreflightResult = {
      lastPreflight: "blocked",
      missing,
      guidance,
    };
    try {
      writeSession(options.sessionId, result, {}, options);
    } catch {
      // never throw from session write failure
    }
    return result;
  }
}

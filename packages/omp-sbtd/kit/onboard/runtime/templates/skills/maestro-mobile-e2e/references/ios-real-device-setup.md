# iOS Real-Device Maestro Setup Lesson

Use this reference only when running or debugging Maestro on iOS real devices and the current failure matches the lesson index.

## Metadata

- Date: 2026-06-24
- Tags: `maestro`, `ios`, `real-device`, `xcode`, `signing`, `java`, `automation`, `validation`
- Severity: High
- Source: `counting_pills_ios` real-device Maestro smoke onboarding and debugging.

## Scope

Applies to iOS real-device Maestro E2E, especially when using Maestro 2.6.1, patching the Maestro iOS driver, testing an iPhone-only app on iPad, or debugging driver setup, view hierarchy, or tap crashes.

Do not apply these fixes preemptively. Confirm the matching symptom first.

## Failure Pattern

Observed issues:

- iOS driver missing files.
- Driver port unreachable from the Mac.
- Installed app build lacks accessibility identifiers.
- iPhone-only app on iPad compatibility mode exposes only status bar hierarchy.
- Tap crashes with `ScreenSizeHelper.swift: Fatal error: Not implemented yet` when device orientation is `.faceUp`, `.faceDown`, or `.unknown`.
- Maestro 2.6.1 `launchApp` or `clearAppState` is incomplete on the target iOS real-device setup.

Root cause pattern:

Maestro CLI, Xcode signing, the driver project, device connectivity, app build artifacts, and flow assertions are often debugged as one blob. Separate them before changing application code or rewriting tests.

## Required Checks

1. Check Java first. Maestro requires Java 17 or newer; prefer Java 21 for this known setup. If only Maestro should use Java 21, set `JAVA_HOME` in a Maestro wrapper instead of changing global Java.
2. Check Maestro CLI version and path with the same Java environment that will run tests.
3. Check Apple signing separately for the app and for the Maestro driver. Correct app signing does not prove driver provisioning is correct.
4. Check real-device UDID, iOS version, installed app bundle id, and whether the installed app is the current build.
5. Verify the Maestro driver HTTP port is reachable from the Mac. If not, use `iproxy` or `pymobiledevice3 usbmux forward`.
6. Before treating an assertion failure as an app bug, inspect screenshot, command JSON hierarchy, Maestro log, and XCTest runner log.

## Jar Patch Protocol

Patch Maestro CLI jars only after confirming the failure matches this reference.

1. Backup the jar before every patch:

   ```bash
   cp ~/.maestro/lib/maestro-cli-2.6.1.jar ~/.maestro/lib/maestro-cli-2.6.1.jar.bak-$(date +%Y%m%d%H%M%S)
   ```

2. Patch only the missing or broken driver files needed for the current failure.
3. Repack the jar.
4. Run `maestro driver-setup` again.
5. Re-run the smallest failing flow.
6. Keep the exact restore command in the final report.

## Known Fixes

- If `driver/ios/MaestroDriverLib` is missing from `~/.maestro/lib/maestro-cli-2.6.1.jar`, backup the jar, patch the missing files, repack, and rerun `maestro driver-setup --apple-team-id <TEAM_ID> --destination generic/platform=iphoneos`.
- If the driver port is unreachable, establish Mac-to-device port forwarding with `iproxy` or `pymobiledevice3 usbmux forward`, then rerun the smallest flow.
- If Maestro cannot reliably launch or clear app state on iOS real devices, prelaunch the app with `xcrun devicectl device process launch` and deterministic automation launch arguments.
- For app launch determinism, consider automation-only launch arguments such as `isMaestro`, `skipSplash`, `disableCamera`, or `disableUploadGuide` when the app supports them.
- If critical UI lacks stable accessibility identifiers, add the smallest stable identifiers needed for the tested flow after user approval.
- If testing an iPhone-only app on iPad shows only status bar hierarchy, prefer an iPhone real device. If an iPad must be used, use a temporary test build with `TARGETED_DEVICE_FAMILY=1,2`; do not silently change production target families.
- If tap crashes in `ScreenSizeHelper.swift` for `.faceUp`, `.faceDown`, or `.unknown`, inspect device orientation. For Maestro 2.6.1, a targeted driver patch can treat those orientations as unrotated before rerunning driver setup.

## Minimum Smoke

Before expanding business flows, validate this chain:

1. Driver setup succeeds.
2. The app launches into a deterministic automation state.
3. A stable identifier is visible.
4. A stable identifier can be tapped.
5. A post-tap screen assertion passes.

Only after this chain passes should API, account, upload, camera, or cross-page flows be added.

## Reporting

If this reference is used, report:

- Matching symptom and exact error text.
- Checks run and their result.
- Patch or workaround applied.
- Backup path and restore command for any patched jar.
- `maestro driver-setup` rerun result when applicable.
- Smallest flow rerun result.
- Remaining version-specific risk and removal note if the upstream bug is fixed.

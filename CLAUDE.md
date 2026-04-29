# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Standalone ADB-based test utilities for the Barco Duvel (ClickShare base unit). No dependency on TEnTo or the Wave4 BSP — only requires `adb` in PATH and Python 3.10+.

## Running the test

```bash
# USB
python testcases/test_peripheral.py --serial 1882000501 --iterations 5

# TCP/IP
python testcases/test_peripheral.py --ip 192.168.1.100 --iterations 3

# With custom output dir
python testcases/test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs

# Selective tests
python testcases/test_peripheral.py --ip 192.168.1.100 --tests camera
python testcases/test_peripheral.py --ip 192.168.1.100 --tests speaker mic

# Stop on first failure
python testcases/test_peripheral.py --ip 192.168.1.100 --iterations 10 --fail-fast
```

No install step — run directly from the repo root. There are no automated tests, linting config, or build system.

## Version control

**Versioning:** `common/version.py` holds `VERSION` and `VERSION_INFO`. Bump both manually — patch (`1.9.x`) for bug fixes and minor additions, minor (`1.x.0`) for new features or behavioural changes.

**Commit message format:**
- Version bump commits: `bump to vX.Y.Z: <one-line summary of what changed>`
- Non-bump commits: imperative lowercase summary, e.g. `add --fail-fast flag`, `fix audio card parsing`
- Do not include a body or issue references unless something non-obvious needs explanation

**When to bump the version:**
- Bump in the same commit that introduces the change (not a separate follow-up commit)
- Do not bump for documentation-only changes (e.g. CLAUDE.md, README updates)
- After bumping, the commit message must start with `bump to vX.Y.Z:`

**Branch strategy:** work directly on `master` — this is a single-developer utility repo with no CI. Force-push is prohibited; amend only unpushed commits.

## Recompiling the ARM64 binary

```bash
NDK=$ANDROID_HOME/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin
$NDK/aarch64-linux-android26-clang -static -o tools/v4l2_stream_test tools/v4l2_stream_test.c
```

## Architecture

```
common/duvel_device.py      — DuvelDevice class (all ADB logic lives here)
common/ui_mtr.py            — MtrUi class (ADB-based UI controller for MTR / Teams)
common/ui_base.py           — BasePage base class shared by all page objects
common/ui_main.py           — MainPage page object (Teams Rooms home screen buttons)
common/ui_invite_people.py  — InvitePeoplePage page object ("Invite people to join you" dialog)
common/ui_in_call.py        — InCallPage page object (active call screen)
common/ui_more_menu.py      — MoreMenuPage page object (More overlay: Meet now, Call, Share, Whiteboard, Join with an ID, Settings)
common/ui_settings.py       — SettingsPage page object (Settings dialog: org name, About, Device settings)
common/ui_device_settings.py — DeviceSettingsPage page object (Android Device Settings: Accessibility, System, About, Admin settings)
testcases/test_peripheral.py       — CLI entry point + TestResult / ResultWriter / PeripheralTestRunner
tools/v4l2_stream_test   — Static ARM64 binary pushed to device at connect() time
data/barco_tone_2s.wav   — 1 kHz / 2 s tone WAV; generated locally if absent, pushed at connect()
scripts/                 — Windows helper batch files (ADB key switcher, Duvel device setup)
common/version.py        — VERSION string (bump manually on releases)
```

**Data flow in testcases/test_peripheral.py:**
1. `main()` constructs `DuvelDevice` and calls `connect()` — this pushes `v4l2_stream_test` to `/data/local/tmp/`
2. `PeripheralTestRunner.run_round()` drives the full reboot → boot → camera → audio → speaker → mic sequence
3. Timing is captured as Unix timestamps in `TestResult`; `ResultWriter` formats and saves them

**DuvelDevice public API** (import in other scripts as needed):
- `connect()` / `disconnect()`
- `reboot()` / `wait_for_boot(timeout)`
- `wait_for_camera_working(timeout, frame_save_path)` → `(dev, name)`
- `wait_for_audio_working(timeout)` → `(short_name, full_name)`
- `test_speaker(duration)` → `bool`
- `test_mic(duration, rms_threshold)` → `(passed, rms)`
- `ui` → `MtrUi` — lazy property; returns the `MtrUi` instance for this device (same serial, created on first access)

**MtrUi public API** (access via `device.ui` or `common/ui_mtr.py` directly):
- `tap(x, y)` / `long_press(x, y, duration_ms)` / `swipe(x1, y1, x2, y2, duration_ms)`
- `keyevent(keycode)` / `input_text(text)` — module-level constants `KEY_HOME`, `KEY_BACK`, `KEY_ENTER`, etc.
- `home()` / `back()` / `recent_apps()`
- `screenshot(local_path)` — uses `adb exec-out screencap -p` (no temp file on device)
- `dump_ui()` → raw XML; `find_element(text, text_contains, content_desc, resource_id, cls)` → dict with `center` tuple
- `tap_element(...)` → bool; `wait_for_element(timeout, ...)` → bool; `wait_for_element_gone(timeout, ...)` → bool
- `current_activity()` → `"package/activity"` string
- `launch(package, activity)` / `force_stop(package)`
- `launch_teams()` / `is_teams_foreground()` / `end_call()` — MTR-specific helpers; `end_call()` delegates to `in_call.hang_up()`
- `main` → `MainPage` — lazy property
- `invite_people` → `InvitePeoplePage` — lazy property
- `in_call` → `InCallPage` — lazy property
- `more_menu` → `MoreMenuPage` — lazy property
- `settings` → `SettingsPage` — lazy property
- `device_settings` → `DeviceSettingsPage` — lazy property

**Page object base** (`common/ui_base.py`): all page objects inherit `BasePage` — provides `__init__(ui)` and `_tap(candidates: list[dict]) -> bool` (tries each kwarg dict against `tap_element` in order).

**MainPage** (`common/ui_main.py`, access via `device.ui.main`):
- `is_visible()` → bool
- `click_meet_now()` / `click_call()` / `click_share()` / `click_join_with_an_id()` / `click_more()` → bool

**InvitePeoplePage** (`common/ui_invite_people.py`, access via `device.ui.invite_people`):
- `is_visible()` → bool
- `dismiss()` / `click_add_participants()` → bool
- `get_meeting_id()` / `get_passcode()` / `get_dial_in_info()` → str | None

**InCallPage** (`common/ui_in_call.py`, access via `device.ui.in_call`):
- `is_visible()` → bool; `get_meeting_title()` → str | None
- `hang_up()` / `mute()` / `toggle_camera()` / `change_video()` / `show_participants()` / `reactions()` / `share()` / `more_options()` / `change_view()` / `volume_up()` / `volume_down()` → bool

**MoreMenuPage** (`common/ui_more_menu.py`, access via `device.ui.more_menu`):
- `is_visible()` → bool
- `click_back()` / `click_meet_now()` / `click_call()` / `click_share()` / `click_whiteboard()` / `click_join_with_an_id()` / `click_settings()` → bool

**SettingsPage** (`common/ui_settings.py`, access via `device.ui.settings`):
- `is_visible()` → bool
- `click_back()` → bool; `get_org_name()` → str | None
- `click_about()` / `click_device_settings()` → bool

**DeviceSettingsPage** (`common/ui_device_settings.py`, access via `device.ui.device_settings`):
- `is_visible()` → bool; `click_exit()` → bool
- `click_accessibility()` / `click_system()` / `click_about()` / `click_admin_settings()` → bool

**Key implementation details:**
- Camera check uses a two-stage approach: sysfs UVC enumeration (no `v4l2-ctl`) → `v4l2_stream_test` STREAMON + 5s AF/AE warm-up + DQBUF
- Audio card detection reads `/proc/asound/cards` (no root required); prefers USB-Audio cards over internal SOC
- `_adb_raw()` never raises; `_adb()` raises on non-zero exit. Internal polling uses `_poll_until()` with a 2s interval
- `connect()` must be called before any device operations; for TCP/IP it runs `adb connect`, for USB it verifies presence in `adb devices`
- Log file is appended to `<output-dir>/YYYYMMDD.txt`; frames go to `<output-dir>/frames/roundNN.jpg`

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

Always respond and discuss in Traditional Chinese (繁體中文).

## What this is

Standalone ADB-based test utilities for the Barco Duvel (ClickShare base unit). No dependency on TEnTo or the Wave4 BSP — only requires `adb` in PATH and Python 3.10+.

UI page objects and element references are based on: Barco FW `04.03.00.master-1660`, MDEP `TPB7.241001.071`. Resource IDs and UI hierarchy may differ on other versions.

## Running the tests

All scripts are run from the **repo root**. Python resolves `from common.xxx import` via `testcases/common/` (script directory is added to `sys.path` automatically).

```bash
# Peripheral stress test (camera / speaker / mic)
python testcases/test_peripheral.py --serial 1882000501 --iterations 5
python testcases/test_peripheral.py --ip 192.168.1.100 --iterations 3
python testcases/test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs
python testcases/test_peripheral.py --ip 192.168.1.100 --tests camera          # selective
python testcases/test_peripheral.py --ip 192.168.1.100 --tests speaker mic
python testcases/test_peripheral.py --ip 192.168.1.100 --iterations 10 --fail-fast

# MTR Meet Now test (reboot-on-exception)
python testcases/test_mtr_meet_now.py --ip 192.168.1.100
python testcases/test_mtr_meet_now.py --ip 192.168.1.100 --output-dir C:/logs --iterations 3

# MTR Join-with-ID call test — join → screenshot → hang up; records desktop with ffmpeg
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host --iterations 5
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --meeting-id 123456789 --no-record

# MTR dirty disconnect test — join → screenshot → hang up → reboot Duvel; records desktop
python testcases/test_mtr_join_with_id_for_dirty_disconnect.py --ip 192.168.1.100 --from-host
python testcases/test_mtr_join_with_id_for_dirty_disconnect.py --ip 192.168.1.100 --meeting-id 123456789 --iterations 5

# MDEP setup wizard + Teams sign-in automation (each step skipped if screen not visible)
python testcases/test_setup_flow.py --ip 192.168.1.100
python testcases/test_setup_flow.py --serial 1882000501
python testcases/test_setup_flow.py --ip 192.168.1.100 \
    --email user@domain.com --password MyPW --admin-password Admin123!
```

No install step — run directly from the repo root. There are no automated tests, linting config, or build system.

## Version control

**Versioning:** `testcases/common/version.py` holds `VERSION` and `VERSION_INFO`. Bump both manually — patch (`1.9.x`) for bug fixes and minor additions, minor (`1.x.0`) for new features or behavioural changes.

**Commit message format:**
- Version bump commits: `bump to vX.Y.Z: <one-line summary of what changed>`
- Non-bump commits: imperative lowercase summary, e.g. `add --fail-fast flag`, `fix audio card parsing`
- Do not include a body or issue references unless something non-obvious needs explanation
- Do not include AI authorship lines (e.g. `Co-Authored-By`) in any commit message

**When to bump the version:**
- Bump in the same commit that introduces the change (not a separate follow-up commit)
- Do not bump for documentation-only changes (e.g. CLAUDE.md, README updates)
- After bumping, the commit message must start with `bump to vX.Y.Z:`

**Branch strategy:** work directly on `master` — this is a single-developer utility repo with no CI. Force-push is prohibited; amend only unpushed commits.

**README.md sync:** whenever a code change affects the public API, CLI options, file structure, or behaviour described in `README.md`, update `README.md` in the same commit.

## Recompiling the ARM64 binary

```bash
NDK=$ANDROID_HOME/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin
$NDK/aarch64-linux-android26-clang -static -o tools/v4l2_stream_test tools/v4l2_stream_test.c
```

## Architecture

All Python source lives under `testcases/` (import root = `testcases/` at runtime).

```
testcases/common/duvel_device.py      — DuvelDevice class (all ADB logic lives here)
testcases/common/ui_mtr.py            — MtrUi class (ADB-based UI controller for MTR / Teams)
testcases/common/ui_base.py           — BasePage base class shared by all page objects
testcases/common/ui_main.py           — MainPage page object (Teams Rooms home screen buttons)
testcases/common/ui_invite_people.py  — InvitePeoplePage page object ("Invite people to join you" dialog)
testcases/common/ui_in_call.py        — InCallPage page object (active call screen)
testcases/common/ui_more_menu.py      — MoreMenuPage page object (More overlay: Meet now, Call, Share, Whiteboard, Join with an ID, Settings)
testcases/common/ui_settings.py       — SettingsPage page object (Settings dialog: org name, About, Device settings)
testcases/common/ui_device_settings.py — DeviceSettingsPage page object (Android Device Settings: Accessibility, System, About, Admin settings)
testcases/common/ui_norden_call.py    — NordenCallPage page object (dial screen: type name/number, Call button)
testcases/common/ui_join_with_id.py   — JoinWithIdPage page object (Join with an ID dialog: meeting ID, passcode, Join button)
testcases/common/ui_device_setup_wizard.py   — DeviceSetupWizardPage page object (MDEP wizard entry screen, before setup begins)
testcases/common/ui_device_setup_language.py — SetupLanguagePage page object (language selection step)
testcases/common/ui_device_setup_network.py  — SetupNetworkPage page object (network connectivity step)
testcases/common/ui_device_setup_datetime.py — SetupDatetimePage page object (date/time and timezone step)
testcases/common/ui_device_setup_terms.py    — SetupTermsPage page object (EULA acceptance step)
testcases/common/ui_device_setup_privacy.py  — SetupPrivacyPage page object (Microsoft Privacy / diagnostic data step)
testcases/common/ui_device_setup_admin_password.py — SetupAdminPasswordPage page object (admin password creation step)
testcases/common/ui_device_setup_confirm.py  — SetupConfirmPage page object (confirm installation summary step)
testcases/common/ui_device_setup_update.py   — SetupUpdatePage page object (firmware update available step)
testcases/common/ui_device_setup_xms_cloud.py — SetupXmsCloudPage page object (XMS Cloud enrollment step)
testcases/common/ui_device_setup_complete.py — SetupCompletePage page object ("Installation complete!" final step)
testcases/common/ui_teams_sign_in.py         — TeamsSignInPage page object (Teams device-code-flow sign-in screen)
testcases/common/ui_teams_sign_in_email.py   — TeamsSignInEmailPage page object (Teams on-device email/username entry)
testcases/common/ui_azure_auth_webview.py    — AzureAuthWebViewPage page object (Azure Authenticator MSAL WebView: password entry + device registration steps)
testcases/common/teams_desktop.py     — TeamsDesktopController: pywinauto-based automation for Windows Teams desktop (create meeting, accept/decline/end call)
testcases/common/teams_meeting_host.py  — Windows-side host: create Meet Now meeting, log Teams version, auto-accept incoming calls; writes meeting_info.json to logs/teams_meeting_host/ by default
testcases/common/logger.py            — Logger class: write timestamped messages to stdout and {output_dir}/logs.txt simultaneously; methods: info/warning/error/debug
testcases/common/utils.py             — Shared test utilities: screenshot_for_debug, screenshot_host_desktop, start_recording, stop_recording, start_ui_with_scrcpy, FFMPEG_DEFAULT, SCRCPY_DEFAULT
testcases/common/version.py           — VERSION string (bump manually on releases)
testcases/test_peripheral.py          — CLI entry point + TestResult / ResultWriter / PeripheralTestRunner
testcases/test_mtr_meet_now.py        — CLI entry point for the MTR Meet Now test (navigate to main → Meet Now → screenshot); reboots only on exception
testcases/test_mtr_join_with_id.py    — CLI entry point for the MTR join-with-ID call test (navigate to main → join by ID → screenshot → hang up); records desktop via ffmpeg
testcases/test_mtr_join_with_id_for_dirty_disconnect.py — same flow but Step 9 reboots Duvel after hang up to simulate dirty disconnect; records desktop via ffmpeg
testcases/test_setup_flow.py          — CLI entry point for MDEP setup wizard + Teams sign-in automation (14 steps, each skipped if screen not visible)
tools/v4l2_stream_test   — Static ARM64 binary; pushed by push_peripheral_resources() (peripheral test only)
data/barco_tone_2s.wav   — 1 kHz / 2 s tone WAV; generated locally if absent, pushed by push_peripheral_resources()
scripts/                 — Windows helper batch files (ADB key switcher, Duvel device setup, ethernet control)
scripts/adb_key_switch.bat  — Switch active ADB vendor key between Duvel / Fruitesse
scripts/duvel_setup.bat     — Interactive Duvel device provisioning (manufacturing mode, SN, certificate, SSID)
scripts/wave4_tool.bat      — Interactive menu: ethernet up/down, network info, Barco APK version listing
```

**Data flow in testcases/test_peripheral.py:**
1. `main()` constructs `DuvelDevice`, calls `connect()` then `push_peripheral_resources()` — this pushes `v4l2_stream_test` and `barco_tone_2s.wav` to `/data/local/tmp/`
2. `PeripheralTestRunner.run_round()` drives the full reboot → boot → camera → audio → speaker → mic sequence
3. Timing is captured as Unix timestamps in `TestResult`; `ResultWriter` formats and logs them via `Logger`

**Logger** (`testcases/common/logger.py`, `from common.logger import Logger`):
- `Logger(output_dir, name="barcoutils", filename="logs.txt")` — creates logger that writes to stdout and `{output_dir}/{filename}` (append mode); format: `HH:MM:SS  LEVEL    message`
- `info(msg, *args)` / `warning(msg, *args)` / `error(msg, *args)` / `debug(msg, *args)` — log at the corresponding level; supports `%`-style format args

**utils.py public API** (`from common.utils import ...`):
- `FFMPEG_DEFAULT` — default path to ffmpeg.exe (`C:\Tools\ffmpeg\bin\ffmpeg.exe`)
- `SCRCPY_DEFAULT` — default path to scrcpy.exe (`C:\Tools\scrcpy-win64-v3.3.3\scrcpy.exe`)
- `screenshot_for_debug(ui, output_dir, round_num)` — ADB screenshot on failure; saves `round01_HHMMSS.png` to `<output_dir>/files/`
- `screenshot_host_desktop(output_dir, round_num)` → `str | None` — PIL full-desktop capture; saves `round01_HHMMSS_desktop.png` to `<output_dir>/files/`
- `start_recording(output_dir, ffmpeg_path)` → `Popen | None` — start ffmpeg gdigrab desktop recording to `<output_dir>/files/desktop_HHMMSS.mp4`
- `stop_recording(proc)` — gracefully stop ffmpeg (sends `q`); kills on timeout
- `start_ui_with_scrcpy(serial, scrcpy_path)` → `Popen | None` — mirror device screen; window size = host resolution ÷ 2, position x:10, y:50; `serial` may be USB serial or `IP:port`

**DuvelDevice public API** (import in other scripts as needed):
- `connect()` / `disconnect()`
- `push_peripheral_resources()` — push `v4l2_stream_test` binary and `barco_tone_2s.wav` to device; call once after `connect()` in peripheral tests only
- `reboot()` / `wait_for_boot(timeout)`
- `wake_up()` — send KEYCODE_WAKEUP to bring device out of sleep
- `is_sleep_mode()` → `bool` — True if `mWakefulness=Asleep`
- `is_wake_up_mode()` → `bool` — True if `mWakefulness=Awake`
- `wait_for_camera_working(timeout, frame_save_path)` → `(dev, name)`
- `wait_for_audio_working(timeout)` → `(short_name, full_name)`
- `test_speaker(duration)` → `bool`
- `test_mic(duration, rms_threshold)` → `(passed, rms)`
- `barco_fw_version()` → `str` — reads `ro.barco.build.version`
- `mdep_version()` → `str` — reads `ro.mdep.build.id`
- `barco_platform()` → `str` — reads `ro.barco.platform` (e.g. `w4duvel`)
- `barco_product()` → `str` — reads `ro.barco.product` (e.g. `Hub Pro`)
- `barco_board_id()` → `str` — reads `ro.barco.board.id` (e.g. `DVT2`)
- `barco_build_type()` → `str` — reads `ro.barco.build.type` (`debug`/`test`/`release`)
- `barco_minimal_version()` → `str` — reads `ro.barco.build.minimal_version`
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
- `go_to_main_page(timeout=15)` → `bool` — navigate to Teams Rooms home screen from any state (hang up if in-call → BACK up to 5× → launch_teams() fallback)
- All page objects accessible as lazy properties (e.g. `ui.main`, `ui.in_call`, `ui.join_with_id`, `ui.more_menu`, `ui.settings`, `ui.device_settings`, `ui.norden_call`, `ui.invite_people`); setup wizard pages follow `ui.setup_*` / `ui.device_setup_wizard`; sign-in pages: `ui.teams_sign_in`, `ui.teams_sign_in_email`, `ui.azure_auth_webview`

**Page object base** (`testcases/common/ui_base.py`): all page objects inherit `BasePage` — provides `__init__(ui)` and `_tap(candidates: list[dict]) -> bool` (tries each kwarg dict against `tap_element` in order).

**MainPage** (`testcases/common/ui_main.py`, access via `device.ui.main`):
- `is_visible()` → bool
- `click_meet_now()` / `click_call()` / `click_share()` / `click_join_with_an_id()` / `click_more()` → bool

**InvitePeoplePage** (`testcases/common/ui_invite_people.py`, access via `device.ui.invite_people`):
- `is_visible()` → bool
- `dismiss()` / `click_add_participants()` → bool
- `get_meeting_id()` / `get_passcode()` / `get_dial_in_info()` → str | None

**InCallPage** (`testcases/common/ui_in_call.py`, access via `device.ui.in_call`):
- `is_visible()` → bool; `get_meeting_title()` → str | None
- `hang_up()` / `mute()` / `toggle_camera()` / `change_video()` / `show_participants()` / `reactions()` / `share()` / `more_options()` / `change_view()` / `volume_up()` / `volume_down()` → bool

**MoreMenuPage** (`testcases/common/ui_more_menu.py`, access via `device.ui.more_menu`):
- `is_visible()` → bool
- `click_back()` / `click_meet_now()` / `click_call()` / `click_share()` / `click_whiteboard()` / `click_join_with_an_id()` / `click_settings()` → bool

**SettingsPage** (`testcases/common/ui_settings.py`, access via `device.ui.settings`):
- `is_visible()` → bool
- `click_back()` → bool; `get_org_name()` → str | None
- `click_about()` / `click_device_settings()` → bool

**DeviceSettingsPage** (`testcases/common/ui_device_settings.py`, access via `device.ui.device_settings`):
- `is_visible()` → bool; `click_exit()` → bool
- `click_accessibility()` / `click_system()` / `click_about()` / `click_admin_settings()` → bool

**NordenCallPage** (`testcases/common/ui_norden_call.py`, access via `device.ui.norden_call`):
- `is_visible()` → bool
- `type_name_or_number(text)` → bool; `click_call()` / `click_back()` → bool

**JoinWithIdPage** (`testcases/common/ui_join_with_id.py`, access via `device.ui.join_with_id`):
- `is_visible()` → bool
- `enter_meeting_id(meeting_id)` / `enter_passcode(passcode)` → bool; `click_join()` / `click_back()` → bool

**DeviceSetupWizardPage** (`testcases/common/ui_device_setup_wizard.py`, access via `device.ui.device_setup_wizard`):
- `is_visible()` → bool; `confirm_connection()` → bool
- `get_title()` / `get_message()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None

**SetupLanguagePage** (`testcases/common/ui_device_setup_language.py`, access via `device.ui.setup_language`):
- `is_visible()` → bool
- `get_title()` / `get_selected_language()` / `get_ip_address()` / `get_serial_number()` / `get_version()` → str | None
- `select_language(language)` / `click_continue()` / `click_back()` / `click_accessibility_settings()` → bool

**SetupNetworkPage** (`testcases/common/ui_device_setup_network.py`, access via `device.ui.setup_network`):
- `is_visible()` → bool; `is_connected()` → bool
- `get_title()` / `get_connectivity_message()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None
- `click_next()` / `click_settings()` / `click_back()` → bool

**SetupDatetimePage** (`testcases/common/ui_device_setup_datetime.py`, access via `device.ui.setup_datetime`):
- `is_visible()` → bool; `is_24h_format()` → bool | None
- `get_title()` / `get_current_time()` / `get_timezone()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None
- `click_timezone()` / `cancel_timezone_picker()` / `toggle_time_format()` / `click_change_time_server()` / `click_next()` / `click_back()` → bool
- `set_timezone(location, max_scrolls=30)` → bool — scrolls timezone picker and taps matching row

**SetupTermsPage** (`testcases/common/ui_device_setup_terms.py`, access via `device.ui.setup_terms`):
- `is_visible()` → bool
- `get_title()` / `get_eula_text()` / `get_disclaimer()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None
- `click_accept()` → bool

**SetupPrivacyPage** (`testcases/common/ui_device_setup_privacy.py`, access via `device.ui.setup_privacy`):
- `is_visible()` → bool; `is_optional_data_enabled()` → bool | None
- `get_title()` / `get_subtitle()` / `get_required_data_label()` / `get_required_data_content()` / `get_optional_data_content()` / `get_optional_data_clarification()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None
- `toggle_optional_data()` / `click_learn_more()` / `click_accept()` → bool

**SetupAdminPasswordPage** (`testcases/common/ui_device_setup_admin_password.py`, access via `device.ui.setup_admin_password`):
- `is_visible()` → bool
- `get_title()` / `get_password_error()` / `get_password_strength()` → str | None
- `enter_new_password(password)` / `toggle_new_password_visibility()` / `enter_confirm_password(password)` / `toggle_confirm_password_visibility()` / `click_create_and_continue()` → bool

**SetupConfirmPage** (`testcases/common/ui_device_setup_confirm.py`, access via `device.ui.setup_confirm`):
- `is_visible()` → bool
- `get_title()` / `get_setup_status()` / `get_subtitle()` / `get_room_name()` / `get_model_name()` / `get_platform_name()` / `get_serial_number()` / `get_admin_password_status()` / `get_ip_address()` / `get_serial_number_footer()` / `get_version()` / `get_build_type()` → str | None
- `click_change_password()` / `click_confirm_installation()` → bool

**SetupUpdatePage** (`testcases/common/ui_device_setup_update.py`, access via `device.ui.setup_update`):
- `is_visible()` → bool
- `get_title()` / `get_fw_version()` / `get_message()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None
- `click_continue()` → bool

**SetupXmsCloudPage** (`testcases/common/ui_device_setup_xms_cloud.py`, access via `device.ui.setup_xms_cloud`):
- `is_visible()` → bool
- `get_title()` / `get_subtitle()` / `get_extra_info()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None
- `click_skip()` / `click_knowledge_base()` → bool

**SetupCompletePage** (`testcases/common/ui_device_setup_complete.py`, access via `device.ui.setup_complete`):
- `is_visible()` → bool
- `get_title()` / `get_ip_address()` / `get_serial_number()` / `get_version()` / `get_build_type()` → str | None
- `click_continue()` → bool — taps "Continue to Microsoft Teams"

**TeamsSignInPage** (`testcases/common/ui_teams_sign_in.py`, access via `device.ui.teams_sign_in`):
- `is_visible()` → bool
- `get_title()` / `get_tenant_name()` / `get_step1_text()` / `get_step2_text()` / `get_login_code()` → str | None
- `click_refresh_code()` / `click_sign_in_on_device()` / `click_settings()` → bool

**TeamsSignInEmailPage** (`testcases/common/ui_teams_sign_in_email.py`, access via `device.ui.teams_sign_in_email`):
- `is_visible()` → bool
- `get_label()` → str | None
- `enter_email(email)` / `click_sign_in()` / `click_back()` / `click_settings()` / `click_privacy_cookies()` → bool

**AzureAuthWebViewPage** (`testcases/common/ui_azure_auth_webview.py`, access via `device.ui.azure_auth_webview`):
- Package: `com.azure.authenticator` — wraps the MSAL HTML WebView; HTML element IDs are exposed as accessibility resource-ids once loaded
- `is_visible()` → bool; `is_password_page()` / `is_device_registration_page()` → bool — detect current sub-step
- Password step: `get_display_name()` → str | None; `enter_password(password)` / `click_sign_in()` / `click_back()` / `click_forgot_password()` / `click_sign_in_with_another_account()` / `click_terms_of_use()` / `click_privacy_cookies()` → bool
- Registration step: `get_heading()` / `get_description()` → str | None; `click_register()` / `click_more_details()` → bool

**TeamsDesktopController** (`testcases/common/teams_desktop.py`): pywinauto-based automation for the Windows Teams desktop app. Requires `pip install pywinauto pywin32 psutil`.
- `get_version()` → `str | None` — return running Teams version (e.g. `'26106.1911.4707.3286'`); static method, Teams must be running, requires psutil
- `connect(launch=True, timeout=30)` — attach to running Teams; launch if not running
- `create_meeting(timeout=20)` → `str | None` — start Meet Now, copy join link, return URL
- `wait_for_incoming_call(timeout=60)` → `bool` — poll for incoming call toast
- `accept_call()` / `accept_video_call()` / `decline_call()` → `bool` — interact with incoming call toast
- `end_call()` → `bool` — hang up active call
- `mute()` / `toggle_camera()` → `bool` — in-call controls

**Key implementation details:**
- Camera check uses a two-stage approach: sysfs UVC enumeration (no `v4l2-ctl`) → `v4l2_stream_test` STREAMON + 5s AF/AE warm-up + DQBUF
- Audio card detection reads `/proc/asound/cards` (no root required); prefers USB-Audio cards over internal SOC
- `_adb_raw()` never raises; `_adb()` raises on non-zero exit. Internal polling uses `_poll_until()` with a 2s interval
- `connect()` must be called before any device operations; for TCP/IP it runs `adb connect`, for USB it verifies presence in `adb devices`
- Default output dir: `logs/<script-stem>/YYYYMMDD/HHMMSS/`; log saved to `logs.txt`, frames/screenshots to `files/`; exception: `teams_meeting_host.py` uses `logs/teams_meeting_host/` and writes `YYYYMMDD_meeting_host.log`

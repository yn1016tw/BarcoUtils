# Copilot Instructions — BarcoUtils

Standalone ADB-based test utilities for the Barco Duvel (ClickShare base unit).  
Requires only `adb` in PATH and Python 3.10+. No install step.

UI element references target Barco FW `04.03.00.master-1660`, MDEP `TPB7.241001.071`.

---

## Running the tests

All commands are run from the **repo root**. No build or install step.

```bash
# Peripheral (camera / mic / speaker) test
python testcases/test_peripheral.py --ip 192.168.1.100 --iterations 3
python testcases/test_peripheral.py --serial 1882000501 --tests camera
python testcases/test_peripheral.py --ip 192.168.1.100 --tests speaker mic --fail-fast

# MTR Meet Now test (Teams Rooms camera end-to-end)
python testcases/test_mtr_meet_now.py --ip 192.168.1.100
python testcases/test_mtr_meet_now.py --ip 192.168.1.100 --iterations 3

# MTR Join-with-ID call test (join → screenshot → hang up; records desktop)
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --meeting-id 123456789
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host --iterations 5 --no-record

# MTR dirty disconnect test (same as join-with-ID but reboots Duvel after hang up)
python testcases/test_mtr_join_with_id_for_dirty_disconnect.py --ip 192.168.1.100 --from-host
python testcases/test_mtr_join_with_id_for_dirty_disconnect.py --ip 192.168.1.100 --meeting-id 123456789 --iterations 5

# MDEP setup wizard + Teams sign-in automation
python testcases/test_setup_flow.py --ip 192.168.1.100
python testcases/test_setup_flow.py --ip 192.168.1.100 \
    --email user@domain.com --password MyPW --admin-password Admin123!

# Windows host (PC side — creates Meet Now meeting, admits from lobby)
python testcases/common/teams_meeting_host.py --output-dir C:/logs
```

There is no test suite runner, no linter config, and no build system.

---

## Architecture

```
testcases/common/duvel_device.py      ← DuvelDevice: all ADB logic (camera, audio, boot). No UI.
testcases/common/ui_mtr.py            ← MtrUi: ADB input + UI hierarchy + lazy page properties
testcases/common/ui_base.py           ← BasePage: base class for all page objects
testcases/common/utils.py             ← Shared utilities: screenshot, recording, scrcpy helpers
testcases/common/ui_main.py           ← MainPage (Teams Rooms home screen)
testcases/common/ui_invite_people.py  ← InvitePeoplePage ("Invite people to join you" dialog)
testcases/common/ui_in_call.py        ← InCallPage (active call screen)
testcases/common/ui_more_menu.py      ← MoreMenuPage (More overlay)
testcases/common/ui_settings.py       ← SettingsPage
testcases/common/ui_device_settings.py ← DeviceSettingsPage (Android Device Settings)
testcases/common/ui_norden_call.py    ← NordenCallPage (dial screen)
testcases/common/ui_join_with_id.py   ← JoinWithIdPage (Join with an ID dialog)
testcases/common/ui_device_setup_wizard.py    ← DeviceSetupWizardPage (wizard entry)
testcases/common/ui_device_setup_language.py  ← SetupLanguagePage
testcases/common/ui_device_setup_network.py   ← SetupNetworkPage
testcases/common/ui_device_setup_datetime.py  ← SetupDatetimePage
testcases/common/ui_device_setup_terms.py     ← SetupTermsPage
testcases/common/ui_device_setup_privacy.py   ← SetupPrivacyPage
testcases/common/ui_device_setup_admin_password.py ← SetupAdminPasswordPage
testcases/common/ui_device_setup_confirm.py   ← SetupConfirmPage
testcases/common/ui_device_setup_update.py    ← SetupUpdatePage
testcases/common/ui_device_setup_xms_cloud.py ← SetupXmsCloudPage
testcases/common/ui_device_setup_complete.py  ← SetupCompletePage
testcases/common/ui_teams_sign_in.py          ← TeamsSignInPage (device-code-flow)
testcases/common/ui_teams_sign_in_email.py    ← TeamsSignInEmailPage
testcases/common/ui_azure_auth_webview.py     ← AzureAuthWebViewPage (MSAL WebView)
testcases/common/teams_desktop.py     ← TeamsDesktopController: pywinauto Windows Teams automation
testcases/common/teams_meeting_host.py ← Windows host: create meeting, admit from lobby
testcases/common/version.py           ← VERSION string (bump manually)
testcases/test_*.py                   ← CLI entry points
testcases/tools/v4l2_stream_test      ← Static ARM64 binary pushed to device at connect()
testcases/data/barco_tone_2s.wav      ← 1 kHz tone pushed to device at connect()
```

**Import convention:** test scripts in `testcases/` import as `from common.foo import Bar`  
(Python adds the script's directory to `sys.path`, resolving to `testcases/common/`).

**Three-layer stack:**
1. `DuvelDevice` — raw ADB, device hardware (camera, audio, boot). No UI.
2. `MtrUi` — ADB input events + `uiautomator dump` XML parsing + app lifecycle.  
   Accessed as `device.ui` (lazy property on `DuvelDevice`).
3. Page objects (`BasePage` subclasses) — one per screen, accessed as lazy properties on `MtrUi`  
   (e.g. `device.ui.main`, `device.ui.in_call`, `device.ui.join_with_id`).

**Default output directory:** `logs/<script-stem>/YYYYMMDD/HHMMSS/` — logs to `logs.txt`, screenshots/frames to `files/`.

---

## Key conventions

### Page objects

- Each page object is in its own file (`ui_<screen>.py`), inherits `BasePage`.
- UI element locators are defined as a module-level `_BUTTONS` dict (or `_*_CANDIDATES` list)  
  with multiple fallback locators per action — `resource_id` first, then `content_desc` or `text`.
- `is_visible(timeout=0)` — returns `bool`; polls via `_poll()` if `timeout > 0`.
- `click_*()` methods return `bool` and call `self._tap(candidates)`.
- `_tap(candidates)` tries each locator dict in order, stops on first success.

```python
# Typical page object structure
_BUTTONS = {
    "meet_now": [
        {"resource_id": f"{_PKG}:id/meetnow_btn"},
        {"content_desc": "Meet now"},
    ],
}

class MainPage(BasePage):
    def is_visible(self, timeout: int = 0) -> bool:
        return self._poll(lambda: self._ui.find_element(**_HOME_LANDMARKS[0]) is not None, timeout)

    def click_meet_now(self) -> bool:
        return self._tap(_BUTTONS["meet_now"])
```

### ADB wrappers (DuvelDevice)

- `_adb_raw()` — never raises; returns `CompletedProcess`; use for commands that may fail transiently.
- `_adb()` — raises `subprocess.CalledProcessError` on non-zero exit.
- `_poll_until(fn, timeout)` — polls `fn()` every 2 s (`_POLL_INTERVAL`); returns `True` on success.

### Versioning and commits

- Version lives in `testcases/common/version.py` as `VERSION = "X.Y.Z"` and `VERSION_INFO = (X, Y, Z)`.
- Patch (`1.x.y`) for bug fixes; minor (`1.x.0`) for new features or behaviour changes.
- Bump in the **same commit** that introduces the change.
- Commit format: `bump to vX.Y.Z: <one-line summary>` for version bumps; otherwise imperative lowercase (e.g. `add --fail-fast flag`).
- Do **not** include `Co-Authored-By` or AI authorship lines in any commit message.
- No commit body or issue references unless something non-obvious needs explanation.
- Do not bump for documentation-only changes.

### MtrUi element lookup

`find_element()` accepts `text`, `text_contains`, `content_desc`, `resource_id`, or `cls`.  
`tap_element()` / `wait_for_element()` / `wait_for_element_gone()` take the same kwargs.

Resource IDs use the MTR package prefix: `com.microsoft.skype.teams.ipphone:id/<id>`.

`go_to_main_page(timeout=15)` → `bool` — navigate to Teams home from any state: hang up if in-call → press BACK up to 5× → fallback `launch_teams()`.

Setup wizard page objects are accessed via `ui.setup_*` / `ui.device_setup_wizard`.  
Sign-in pages: `ui.teams_sign_in`, `ui.teams_sign_in_email`, `ui.azure_auth_webview`.

### utils.py (testcases/common/utils.py)

- `FFMPEG_DEFAULT` — `C:\Tools\ffmpeg\bin\ffmpeg.exe`
- `SCRCPY_DEFAULT` — `C:\Tools\scrcpy-win64-v3.3.3\scrcpy.exe`
- `screenshot_for_debug(ui, output_dir, round_num)` — ADB screenshot on failure
- `screenshot_host_desktop(output_dir, round_num)` → `str | None` — PIL full-desktop capture
- `start_recording(output_dir, ffmpeg_path)` → `Popen | None` — ffmpeg gdigrab to `files/desktop_HHMMSS.mp4`
- `stop_recording(proc)` — send `q` to ffmpeg; kill on timeout
- `start_ui_with_scrcpy(serial, scrcpy_path)` → `Popen | None` — mirror device screen

### TeamsDesktopController (Windows only)

The Teams lobby "Waiting in the lobby" admit button is in WebView2 and not UIA-accessible.  
`accept_call()` locates it by the Group element bounding rect and clicks at calibrated fractional coordinates — do not replace with element-based automation.

Windows-only dependency: `pip install pywinauto pywin32 psutil`

### Recompiling the ARM64 binary

```bash
NDK=$ANDROID_HOME/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin
$NDK/aarch64-linux-android26-clang -static -o tools/v4l2_stream_test tools/v4l2_stream_test.c
```

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

# MTR Join Call test (requires teams_meeting_host.py on Windows PC)
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --from-host
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-id 123456789

# Windows host (PC side — creates Meet Now meeting, admits from lobby)
python testcases/common/teams_meeting_host.py --output-dir C:/logs
```

There is no test suite runner, no linter config, and no build system.

---

## Architecture

```
testcases/common/duvel_device.py   ← DuvelDevice: all ADB logic (camera, audio, boot)
testcases/common/ui_mtr.py         ← MtrUi: ADB input + UI hierarchy + lazy page properties
testcases/common/ui_base.py        ← BasePage: base class for all page objects
testcases/common/ui_*.py           ← Page objects (one file per screen)
testcases/common/teams_desktop.py  ← TeamsDesktopController: pywinauto Windows Teams automation
testcases/common/teams_meeting_host.py ← Windows host: create meeting, admit from lobby
testcases/common/version.py        ← VERSION string (bump manually)
testcases/test_*.py                ← CLI entry points
tools/v4l2_stream_test             ← Static ARM64 binary pushed to device at connect()
data/barco_tone_2s.wav             ← 1 kHz tone pushed to device at connect()
```

**Import convention:** test scripts in `testcases/` import as `from common.foo import Bar`  
(Python adds the script's directory to `sys.path`, resolving to `testcases/common/`).

**Three-layer stack:**
1. `DuvelDevice` — raw ADB, device hardware (camera, audio, boot). No UI.
2. `MtrUi` — ADB input events + `uiautomator dump` XML parsing + app lifecycle.  
   Accessed as `device.ui` (lazy property on `DuvelDevice`).
3. Page objects (`BasePage` subclasses) — one per screen, accessed as lazy properties on `MtrUi`  
   (e.g. `device.ui.main`, `device.ui.in_call`, `device.ui.join_with_id`).

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

### TeamsDesktopController (Windows only)

The Teams lobby "Waiting in the lobby" admit button is in WebView2 and not UIA-accessible.  
`accept_call()` locates it by the Group element bounding rect and clicks at calibrated fractional coordinates — do not replace with element-based automation.

### Recompiling the ARM64 binary

```bash
NDK=$ANDROID_HOME/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin
$NDK/aarch64-linux-android26-clang -static -o tools/v4l2_stream_test tools/v4l2_stream_test.c
```

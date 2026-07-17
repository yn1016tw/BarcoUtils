# BarcoUtils

Standalone test utilities for Barco Duvel (ClickShare base unit).  
No dependency on TEnTo or the Wave4 BSP — only `adb` in PATH and Python 3.10+.

UI references are based on Barco FW `04.03.00.master-1660`, MDEP `TPB7.241001.071`.

---

## Requirements

- Python 3.10+
- `adb` in PATH
- Duvel device accessible via USB or TCP/IP
- **ffmpeg** — required for desktop recording (`test_mtr_join_with_id.py`, dirty disconnect test). Default path: `C:\Tools\ffmpeg\bin\ffmpeg.exe`
- **scrcpy** — required for device screen mirroring. Default path: `C:\Tools\scrcpy-win64-v3.3.3\scrcpy.exe`
- If installed elsewhere, update `FFMPEG_DEFAULT` / `SCRCPY_DEFAULT` at the top of `testcases/common/utils.py`. ffmpeg path can also be overridden per-run with `--ffmpeg PATH` on the join-with-ID and dirty-disconnect tests.
- Windows Teams desktop (for `testcases/common/teams_meeting_host.py`): `pip install pywinauto pywin32 psutil` (psutil required for `get_version()`)

---

## Repository Structure

```
BarcoUtils/
├── testcases/
│   ├── common/
│   │   ├── duvel_device.py               # DuvelDevice — ADB wrapper (reusable)
│   │   ├── ui_mtr.py                     # MtrUi — ADB-based UI controller for MTR / Teams
│   │   ├── ui_base.py                    # BasePage — shared base class for all page objects
│   │   ├── ui_main.py                    # MainPage — Teams Rooms home screen
│   │   ├── ui_invite_people.py           # InvitePeoplePage — "Invite people to join you" dialog
│   │   ├── ui_in_call.py                 # InCallPage — active call screen
│   │   ├── ui_more_menu.py               # MoreMenuPage — More overlay menu
│   │   ├── ui_settings.py                # SettingsPage — Settings dialog
│   │   ├── ui_device_settings.py         # DeviceSettingsPage — Android Device Settings
│   │   ├── ui_norden_call.py             # NordenCallPage — dial screen
│   │   ├── ui_join_with_id.py            # JoinWithIdPage — Join with an ID dialog
│   │   ├── ui_device_setup_wizard.py     # DeviceSetupWizardPage — MDEP wizard entry screen
│   │   ├── ui_device_setup_language.py   # SetupLanguagePage — language selection step
│   │   ├── ui_device_setup_network.py    # SetupNetworkPage — network connectivity step
│   │   ├── ui_device_setup_datetime.py   # SetupDatetimePage — date/time and timezone step
│   │   ├── ui_device_setup_terms.py      # SetupTermsPage — EULA acceptance step
│   │   ├── ui_device_setup_privacy.py    # SetupPrivacyPage — Microsoft Privacy step
│   │   ├── ui_device_setup_admin_password.py # SetupAdminPasswordPage — admin password creation
│   │   ├── ui_device_setup_confirm.py    # SetupConfirmPage — confirm installation summary
│   │   ├── ui_device_setup_update.py     # SetupUpdatePage — firmware update available step
│   │   ├── ui_device_setup_xms_cloud.py  # SetupXmsCloudPage — XMS Cloud enrollment step
│   │   ├── ui_device_setup_complete.py   # SetupCompletePage — "Installation complete!" final step
│   │   ├── ui_teams_sign_in.py           # TeamsSignInPage — Teams device-code-flow sign-in
│   │   ├── ui_teams_sign_in_email.py     # TeamsSignInEmailPage — Teams on-device email entry
│   │   ├── ui_azure_auth_webview.py      # AzureAuthWebViewPage — Azure MSAL WebView (password + registration)
│   │   ├── ui_device_setup_provider.py   # SetupProviderPage — "Choose your provider" wizard step
│   │   ├── ui_clickshare_main.py         # ClickShareMainPage — ClickShare mode home screen (Duvel & god)
│   │   ├── acroname_hub.py               # AcronameHub — brainstem SDK wrapper for USBHub3+
│   │   ├── teams_desktop.py              # TeamsDesktopController — Windows Teams desktop automation
│   │   ├── teams_meeting_host.py         # Windows host: create Meet Now meeting, auto-accept calls
│   │   ├── edge_desktop.py               # EdgeController — Windows Edge desktop automation (pywinauto)
│   │   ├── logger.py                     # Logger — write timestamped messages to stdout + file
│   │   ├── utils.py                      # Shared utilities: screenshot, recording, scrcpy helpers
│   │   └── version.py                    # VERSION string
│   ├── test_peripheral.py                                        # Peripheral boot-time test (camera / mic / speaker)
│   ├── test_mtr_meet_now.py                                      # MTR Meet Now test (Teams UI → Meet now → screenshot)
│   ├── test_mtr_join_with_id.py                                  # MTR join-with-ID test (join by ID → screenshot → hang up)
│   ├── test_mtr_join_with_id_for_dirty_disconnect.py             # same flow but reboots Duvel after hang up
│   └── test_mtr_join_with_id_for_multiple_peripherals.py         # same flow iterated over Acroname hub ports
├── data/
│   └── barco_tone_2s.wav          # Pre-generated 1 kHz / 2 s tone (pushed by push_peripheral_resources)
├── scripts/
│   ├── adb_key_switch.bat         # Switch active ADB key between Duvel / Fruitesse
│   ├── app_tool.bat               # Manage CLICKSHARE_DEBUG env var (ON/OFF/clear) for desktop app log
│   ├── duvel_setup.bat            # Interactive Duvel device setup helper
│   ├── god_setup.bat              # God-mode production API device setup (mfg mode, SN, certs, WiFi, OOBE)
│   ├── set_wifi_config.ps1        # Configure Base Unit WiFi AP (SSID/channel/band) via v3 REST API
│   ├── wave4_tool.bat             # Interactive menu to control ethernet (up/down) via ADB
│   ├── setup_tool.bat             # Launcher: interactive menu → calls setup_tool.py
│   ├── setup_tool.py              # MDEP setup wizard + Teams sign-in (polling-based, order-independent)
│   ├── record_tool.bat            # Launcher: calls record_tool.ps1
│   ├── record_tool.ps1            # Screen recording tool using ffmpeg gdigrab
│   ├── diagnose-hid-binding.ps1   # Inspect USB/HID registry driver bindings for Gen5 Button
│   ├── find-hid-holder.ps1        # Enumerate processes holding open handles to the Gen5 Button HID device
│   ├── fix-barco-driver.ps1       # Remove duplicate BarcoClickShareDrv entries via pnputil (admin)
│   └── test-hid-clickshare.ps1    # Open/read/write Gen5 Button HID device from PowerShell
├── src/
│   ├── timesheet/
│   │   ├── fill_timesheet.py      # SAP Fiori CATS timesheet auto-fill via Playwright + Edge persistent profile
│   │   ├── fill_timesheet2.py     # Same, via EdgeController + TimesheetPage (pywinauto, no Playwright)
│   │   ├── timesheet_page.py      # TimesheetPage — UI-Automation page object for SAP Fiori "My Timesheet"
│   │   └── 2026_holidays.csv      # Taiwan public holidays used for holiday-vs-workday classification
│   ├── hid-test/
│   │   ├── hid_test.cpp           # Windows C++ tool: enumerate Gen4/Gen5 Button HID devices, test CreateFile access
│   │   └── build.bat              # MSVC build script (auto-detects VS 2017/2019/2022)
│   └── hid-desc/
│       ├── hid_desc_tool.bat      # ADB menu tool: backup/restore/patch the Button's HID report descriptor
│       ├── parse_hid_desc.py      # Parse and pretty-print a HID report descriptor .bin file
│       └── patch_hid_desc.py      # Patch Usage Page / Usage in a HID report descriptor .bin file
└── tools/
    ├── v4l2_stream_test.c         # Minimal V4L2 streaming test (source)
    └── v4l2_stream_test           # Precompiled static ARM64 binary (Android 26+)
```

---

## testcases/test_peripheral.py

Measures how long after reboot it takes for the camera (UVC), microphone, and speaker to become ready.  
Supports stress testing (configurable iterations), selective test execution, and logs results to `<output-dir>/logs.txt`.

### What it tests

| Step | Method | Pass condition |
|------|--------|----------------|
| Boot complete | `getprop sys.boot_completed` + `init.svc.bootanim` + `pm list packages` | All three pass |
| Camera streaming | sysfs `uvcvideo` driver check → `v4l2_stream_test` STREAMON + DQBUF | Frame delivered within 5 s |
| Audio card | `/proc/asound/cards` — prefers USB-Audio card over internal SOC | Card enumerated by kernel |
| Speaker | `tinyplay` with pre-pushed 1 kHz tone WAV | Exit 0 |
| Mic | `tinycap` RMS measurement | RMS > 100 (ambient noise) |

A captured JPEG frame is saved locally for every camera check.

### Usage

```bash
# USB serial
python testcases/test_peripheral.py --serial 1882000501 --iterations 5

# ADB over TCP/IP
python testcases/test_peripheral.py --ip 192.168.1.100 --iterations 3

# Camera only
python testcases/test_peripheral.py --ip 192.168.1.100 --tests camera

# Speaker and mic only
python testcases/test_peripheral.py --ip 192.168.1.100 --tests speaker mic

# Custom output directory
python testcases/test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs
```

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--serial SERIAL` | — | USB ADB serial number (mutually exclusive with `--ip`) |
| `--ip IP[:PORT]` | — | ADB over TCP/IP (default port 5555) |
| `--iterations N` | 1 | Number of test rounds |
| `--tests TEST ...` | all | Tests to run: `camera` `speaker` `mic` |
| `--output-dir DIR` | auto | Directory for log file and captured frames (default: `logs/test_peripheral/YYYYMMDD/HHMMSS/`) |
| `--boot-timeout SEC` | 300 | Max seconds to wait for boot |
| `--device-timeout SEC` | 120 | Max seconds to wait for camera / audio |
| `--fail-fast` | off | Stop after the first failed round |

### Output

```
[Round 1/3] PASS
  Reboot triggered    : 14:30:00.123
  Boot ready          : 14:30:44.901  (+44.8s)  PASS
  Camera working      : 14:31:05.210  (+20.3s from boot)  PASS  [/dev/video0  Rally Camera]
  Frame saved         : logs/test_peripheral/20260513/143000/files/round01_143005.jpg
  Audio card ready    : 14:31:06.400  (+21.5s from boot)  PASS  [RallyCamera  Rally Camera]
  Speaker working     : 14:31:08.612  (+23.7s from boot)  PASS
  Mic working         : 14:31:11.003  (+26.1s from boot)  PASS  RMS=412
  Total (reboot->mic) : 70.9s
```

Log: `<output-dir>/logs.txt`  
Frames: `<output-dir>/files/round01_HHMMSS.jpg`, …

---

## testcases/test_mtr_meet_now.py

Verifies the Teams Rooms Meet Now flow end-to-end with per-step timestamps.  
On exception, reboots the device before the next round.

### Test procedure

| Step | Action | Pass condition |
|------|--------|----------------|
| 1 | Navigate to main page | `meetnow_btn` visible in UI hierarchy |
| 2 | Tap "Meet now" | Button found and tapped |
| 3 | Invite dialog visible | `invite_button` or "Invite people to join you" text found |
| 4 | Dismiss dialog | Dismiss (X) button found and tapped |
| 5 | Screenshot saved | PNG written to `files/` |
| 6 | Hang up | End call button found and tapped |

### Usage

```bash
python testcases/test_mtr_meet_now.py --ip 192.168.1.100
python testcases/test_mtr_meet_now.py --serial 1882000501 --iterations 3
python testcases/test_mtr_meet_now.py --ip 192.168.1.100 --output-dir C:/logs --fail-fast
```

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--serial SERIAL` | — | USB ADB serial number |
| `--ip IP[:PORT]` | — | ADB over TCP/IP (default port 5555) |
| `--iterations N` | 1 | Number of test rounds |
| `--output-dir DIR` | auto | Directory for log file and screenshots (default: `logs/test_mtr_meet_now/YYYYMMDD/HHMMSS/`) |
| `--boot-timeout SEC` | 300 | Max seconds to wait for boot |
| `--device-timeout SEC` | 120 | Max seconds to wait for main page |
| `--fail-fast` | off | Stop after the first failed round |

### Output

```
14:30:00  INFO     MTR Meet Now Test  v1.14.30
14:30:00  INFO     ------------------------------------------------------------
14:30:00  INFO     Round 1/1
14:30:00  INFO     Navigating to Teams Rooms main page...
14:30:07  INFO     Main page visible  (+7.3s)
14:30:07  INFO     Tapping 'Meet now'...
14:30:08  INFO     Meet now tapped  (+7.7s)
14:30:09  INFO     Invite dialog visible  (+9.0s)
14:30:09  INFO     Dialog dismissed  (+9.4s)
14:30:15  INFO     Screenshot saved  (+10.2s)  files/round01_143015.png
14:30:16  INFO     Call ended  (+10.7s)
14:30:16  INFO     [Round 1/1] PASS
14:30:16  INFO       Total (reboot->shot)  : 16.2s
14:30:16  INFO     ============================================================
14:30:16  INFO     Summary (1/1 PASS)
```

Log: `<output-dir>/logs.txt`  
Screenshots: `<output-dir>/files/round01_HHMMSS.png`, …

---

## testcases/test_mtr_join_with_id.py

Verifies the Teams Rooms join-by-ID flow end-to-end.  
Designed to run alongside `testcases/common/teams_meeting_host.py` on the Windows PC.  
Desktop video is recorded via ffmpeg throughout the test.

### Test procedure

| Step | Action | Pass condition |
|------|--------|----------------|
| 1 | Navigate to main page | Teams Rooms home screen visible |
| 2 | Tap "Join with an ID" | Button found and tapped |
| 3 | Join dialog visible | Join-with-ID form visible |
| 4 | Enter meeting ID + passcode | Fields filled and confirmed |
| 5 | Tap "Join Teams meeting" | Join button tapped |
| 6 | In-call screen visible | Active call screen detected |
| 7 | Wait 15s, take screenshot | PNG written to `files/` |
| 8 | Hang up | End call button tapped (force-stop if needed) |

### Usage

```bash
# Manual meeting ID
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --meeting-id 123456789
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --meeting-id 123456789 --passcode abc123

# Load meeting info from teams_meeting_host.py (default path)
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host

# Load from custom directory
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --meeting-info-dir C:/logs

# Stress test
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host --iterations 5

# Skip desktop recording
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --meeting-id 123456789 --no-record
```

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--serial SERIAL` | — | USB ADB serial number |
| `--ip IP[:PORT]` | — | ADB over TCP/IP (default port 5555) |
| `--meeting-id ID` | — | Meeting ID (manual, mutually exclusive with `--from-host` / `--meeting-info-dir`) |
| `--passcode CODE` | — | Meeting passcode (optional, used with `--meeting-id`) |
| `--from-host` | — | Load meeting info from default JSON path written by `teams_meeting_host.py` |
| `--meeting-info-dir DIR` | — | Load meeting info from `DIR/meeting_info.json` |
| `--meeting-info-timeout SEC` | 120 | Seconds to wait for `meeting_info.json` to appear |
| `--iterations N` | 1 | Number of test rounds |
| `--output-dir DIR` | auto | Directory for log file and screenshots (default: `logs/test_mtr_join_with_id/YYYYMMDD/HHMMSS/`) |
| `--device-timeout SEC` | 120 | Max seconds to wait for Teams Rooms UI |
| `--fail-fast` | off | Stop after the first failed round |
| `--no-record` | off | Disable ffmpeg desktop recording |
| `--ffmpeg PATH` | `C:\Tools\ffmpeg\bin\ffmpeg.exe` | Path to ffmpeg.exe |

---

## testcases/test_mtr_join_with_id_for_dirty_disconnect.py

Same flow as `test_mtr_join_with_id.py` but reboots Duvel after hanging up to simulate a dirty disconnect.

### Usage

```bash
python testcases/test_mtr_join_with_id_for_dirty_disconnect.py --ip 192.168.1.100 --from-host
python testcases/test_mtr_join_with_id_for_dirty_disconnect.py --ip 192.168.1.100 --meeting-id 123456789 --iterations 5
```

---

## testcases/test_mtr_join_with_id_for_multiple_peripherals.py

Iterates over Acroname USBHub3+ downstream ports and runs the full join-with-ID flow for each port.  
Use this to verify that different peripherals (cameras, speakers, mics) plugged into the hub all work correctly during an active Teams call.

Requires an Acroname USBHub3+ connected via USB and the `brainstem` Python package installed.

### Test procedure

| Step | Action |
|------|--------|
| 1 | Switch AcronameHub to target port (exclusive — all others disabled) |
| 2 | Wait for peripheral to enumerate (`--port-settle` seconds) |
| 3 | Query peripheral name via sysfs / `/proc/asound/cards` |
| 4–8 | Same join-with-ID flow as `test_mtr_join_with_id.py` |
| 9 | Wait for camera to be fully released (`dumpsys media.camera`) before next port switch |

### Usage

```bash
# Terminal 1 — create meeting and auto-accept calls
python testcases/common/teams_meeting_host.py

# Terminal 2 — run the test
python testcases/test_mtr_join_with_id_for_multiple_peripherals.py --ip 192.168.1.100 --from-host
python testcases/test_mtr_join_with_id_for_multiple_peripherals.py --ip 192.168.1.100 --from-host --ports 0 1 2
python testcases/test_mtr_join_with_id_for_multiple_peripherals.py --ip 192.168.1.100 --meeting-id 123456789 --ports 0 1 2 3 --iterations 2
```

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--serial SERIAL` | — | USB ADB serial number |
| `--ip IP[:PORT]` | — | ADB over TCP/IP (default port 5555) |
| `--meeting-id ID` | — | Meeting ID (manual) |
| `--from-host` | — | Load meeting info from `teams_meeting_host.py` output |
| `--meeting-info-dir DIR` | — | Load meeting info from `DIR/meeting_info.json` |
| `--ports N ...` | 0–7 | Hub ports to test |
| `--iterations N` | 1 | Rounds per port |
| `--port-settle SEC` | 5 | Seconds to wait after switching port |
| `--hub-serial HEX` | auto | Acroname hub serial (e.g. `0xDC770118`) |
| `--output-dir DIR` | auto | Log and screenshot directory |
| `--device-timeout SEC` | 120 | Max seconds to wait for Teams Rooms UI |
| `--fail-fast` | off | Stop after the first failed round |
| `--no-record` | off | Disable ffmpeg desktop recording |

---

## testcases/common/teams_meeting_host.py

Windows-side host script. Creates a Meet Now meeting in Teams desktop, logs the Teams version,
writes meeting info to JSON, and automatically accepts incoming calls.

Requires `pip install pywinauto pywin32 psutil`.

### Usage

```bash
# Start meeting and auto-accept calls (default)
python testcases/common/teams_meeting_host.py

# Custom output directory for meeting_info.json and log file
python testcases/common/teams_meeting_host.py --output-dir C:/logs

# Create meeting only, do not accept calls
python testcases/common/teams_meeting_host.py --no-auto-accept

# Accept video calls instead of audio-only
python testcases/common/teams_meeting_host.py --accept-video
```

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir DIR` | `logs/teams_meeting_host/` | Directory for `meeting_info.json` and `YYYYMMDD_meeting_host.log` |
| `--accept-video` | off | Accept calls with video (default: audio only) |
| `--no-auto-accept` | off | Create meeting and print info, then exit |
| `--connect-timeout SEC` | 30 | Seconds to wait for Teams to start |
| `--meeting-timeout SEC` | 30 | Seconds to wait for meeting to be created |

### Output files

Default location: `testcases/logs/teams_meeting_host/`

| File | Description |
|------|-------------|
| `YYYYMMDD_meeting_host.log` | Timestamped log (stdout + file via Logger) |
| `meeting_info.json` | Meeting ID, passcode, join URL written after meeting is created |

```json
{
  "meeting_id": "123 456 789 012",
  "passcode": "abcXYZ",
  "join_url": "https://teams.microsoft.com/l/meetup-join/...",
  "created_at": "2026-05-04 14:30:00",
  "info_file": "C:/logs/meeting_info.json"
}
```

### Typical two-machine workflow

**PC (Windows)** — run first:
```bash
python testcases/common/teams_meeting_host.py
```

**MTR device** — run once the host is ready:
```bash
python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host
```

The join-with-ID test polls for `meeting_info.json` (up to `--meeting-info-timeout` seconds),  
so both processes can be started in any order.

---

## common/teams_desktop.py — TeamsDesktopController

pywinauto-based automation for the Windows Teams desktop app.

```python
from common.teams_desktop import TeamsDesktopController

# Get Teams version (static — no connect() required; Teams must be running)
version = TeamsDesktopController.get_version()  # e.g. '26106.1911.4707.3286'

ctrl = TeamsDesktopController()
ctrl.connect()                          # attach to Teams; launch if not running
info = ctrl.create_meeting()            # start Meet Now; returns dict(join_url, meeting_id, passcode)
ctrl.wait_for_incoming_call(timeout=60)
ctrl.accept_call()                      # Admit from lobby or accept incoming audio call
ctrl.end_call()
```

**Lobby handling**: "Waiting in the lobby" admit/deny buttons are rendered in WebView2 and not  
accessible via UIA. `accept_call()` detects the lobby popup by its Group element bounding rect  
and clicks at calibrated fractional coordinates.

**Teams version compatibility**: the Meet Now button's UIA accessible name changed from `"Meet now"` to `"Start an instant Teams meeting."` in Teams ≥ 26149. `create_meeting()` tries both labels automatically.

---

## common/edge_desktop.py — EdgeController

pywinauto-based automation for the Windows Microsoft Edge desktop app (`msedge.exe`). Drives the page purely through the UI Automation tree — no DOM access. Used by the timesheet tools (below) to navigate SAP Fiori pages.

```python
from common.edge_desktop import EdgeController

ctrl = EdgeController()
ctrl.connect()                        # attach to running Edge, launch if not running; maximizes window
ctrl.navigate("https://example.com")
print(ctrl.get_title(), ctrl.get_url())
ctrl.refresh()                         # F5; auto-dismisses Chromium's "Resubmit the form?" dialog
ctrl.new_tab("https://example.com")
ctrl.close_tab()
ctrl.screenshot("C:/logs/edge.png")
ctrl.close()
```

Requires `pip install pywinauto pywin32` (`pip install psutil` too for `get_version()`).

`connect()` matches the real browser window by title/class instead of `top_window()`, since `msedge.exe` spawns many windowless helper processes (renderer/GPU/etc.) that a naive attach could latch onto. `_main_window()` similarly rejects stale tooltip/flyout panes left over from a hover, picking the actual Edge window by title match (falling back to the largest window by area).

---

## common/ui_mtr.py — MtrUi

ADB-based UI controller for Microsoft Teams Rooms. Wraps raw ADB input, UI hierarchy queries,  
and app lifecycle. Page objects are accessed via lazy properties.

```python
from common.ui_mtr import MtrUi
ui = MtrUi(serial="192.168.1.100:5555")
ui.launch_teams()
ui.screenshot("logs/screen.png")
el = ui.find_element(resource_id="com.microsoft.skype.teams.ipphone:id/meetnow_btn")
ui.tap(*el["center"])

# Page objects
ui.main.is_visible()
ui.main.click_meet_now()
ui.main.click_join_with_an_id()
ui.invite_people.is_visible()
ui.invite_people.dismiss()
ui.join_with_id.enter_meeting_id("123456789")
ui.join_with_id.enter_passcode("abc123")
ui.join_with_id.click_join()
ui.in_call.is_visible()
ui.in_call.hang_up()
```

`device.ui` returns the `MtrUi` for a `DuvelDevice` (lazy property, same serial).

### Page objects

| Property | Class | File | Screen |
|----------|-------|------|--------|
| `ui.main` | `MainPage` | `ui_main.py` | Teams Rooms home screen |
| `ui.invite_people` | `InvitePeoplePage` | `ui_invite_people.py` | "Invite people to join you" dialog |
| `ui.in_call` | `InCallPage` | `ui_in_call.py` | Active call screen |
| `ui.more_menu` | `MoreMenuPage` | `ui_more_menu.py` | More overlay menu |
| `ui.settings` | `SettingsPage` | `ui_settings.py` | Settings dialog |
| `ui.device_settings` | `DeviceSettingsPage` | `ui_device_settings.py` | Android Device Settings |
| `ui.norden_call` | `NordenCallPage` | `ui_norden_call.py` | Dial screen |
| `ui.join_with_id` | `JoinWithIdPage` | `ui_join_with_id.py` | Join with an ID dialog |
| `ui.clickshare_main` | `ClickShareMainPage` | `ui_clickshare_main.py` | ClickShare mode home screen (Duvel & god) |
| `ui.setup_provider` | `SetupProviderPage` | `ui_device_setup_provider.py` | MDEP "Choose your provider" wizard step |

All page objects inherit `BasePage` (`ui_base.py`) which provides `__init__(ui)` and `_tap(candidates)`.

---

## common/duvel_device.py

Reusable `DuvelDevice` class. All ADB interaction lives here — import it in other scripts as needed.

```python
from common.duvel_device import DuvelDevice

device = DuvelDevice(serial="192.168.1.100:5555", is_ip=True)
device.connect()                    # adb connect / verify device
device.push_peripheral_resources()  # push v4l2_stream_test + tone WAV (peripheral tests only)
device.barco_fw_version()           # ro.barco.build.version
device.reboot()
device.wait_for_boot(timeout=300)
dev, name = device.wait_for_camera_working(120, frame_save_path="frame.jpg")
card, full = device.wait_for_audio_working(120)
speaker_ok = device.test_speaker(duration=2)
mic_ok, rms = device.test_mic(duration=2)
device.disconnect()
```

### Camera check detail

`v4l2-ctl` is not available on Duvel. The camera check uses two stages:

1. **sysfs enumeration** — finds `/dev/videoX` nodes where the driver symlink points to `uvcvideo` and `index == 0` (capture node, not metadata).
2. **Streaming verification** — runs `tools/v4l2_stream_test /dev/videoX` on the device:
   - `VIDIOC_QUERYCAP` → `VIDIOC_S_FMT` (MJPEG, fallback YUYV) → `VIDIOC_REQBUFS` (1 MMAP buffer)
   - `VIDIOC_STREAMON` → `select()` wait → `VIDIOC_DQBUF`
   - Exit 0 = frame received; exit 1 = timeout (5 s); exit 2 = device error

The binary is pushed to `/data/local/tmp/v4l2_stream_test` by `push_peripheral_resources()`, called once before the test loop in `test_peripheral.py`.

### Camera idle check

After a Teams call ends, the camera may take a moment to be fully released by the Android Camera API.  
`camera_client_count()` queries `dumpsys media.camera` and parses the `Active Camera Clients` list:

- `[]` → 0 clients (idle)
- Non-empty list → ≥ 1 client still active

`wait_for_camera_idle(timeout=30)` polls every 2 s until the count reaches 0. Note: `v4l2_stream_test` bypasses the Android Camera API and will not appear in this count.

### Audio check detail

`/proc/asound/cards` is readable without root and confirms the kernel has enumerated the audio device.  
USB-Audio cards (external camera mic/speaker) are preferred over the internal MT8195 SOC audio.

`tinyplay` and `tinycap` require access to `/dev/snd/pcm*` which is owned by `system:audio`.  
Since `adb shell` runs as `shell` (not in the `audio` group), both commands are prefixed with `su root`.

### Mic RMS reference

| RMS range | Meaning |
|-----------|---------|
| < 50 | Near silence — hardware not responding |
| 50–100 | Below default threshold |
| > 100 (default) | Ambient noise confirmed — PASS |

---

## scripts/

Windows batch scripts for device management tasks.

### app_tool.bat

Interactive menu for managing the `CLICKSHARE_DEBUG` environment variable, which controls log output in the ClickShare desktop app.

```
scripts\app_tool.bat
```

**Menu options:**
- `[1]` Enable debug log — `setx CLICKSHARE_DEBUG ON`
- `[2]` Disable debug log — `setx CLICKSHARE_DEBUG OFF`
- `[3]` Clear variable — removes `CLICKSHARE_DEBUG` from user environment

The current value is read from `HKCU\Environment` and displayed at the top of the menu on each launch. Changes take effect after restarting the ClickShare app.

**Other ways to enable logging in the ClickShare desktop app:**

| Method | Description |
|--------|-------------|
| Hold left **Shift** at launch | Enables debug log for that session |
| `CLICKSHARE_DEBUG=ON` env var | Permanent via `setx`; this tool manages it |
| `-enablelogging` CLI arg | Pass to `ClickShare.exe` at launch |
| `-debuglogging` CLI arg | Enables debug-level log |
| `-loglevel <level>` CLI arg | Set log level (e.g. `debug`, `info`) |
| `-logmaxsize <bytes>` CLI arg | Set max log file size |
| `-debughandler` CLI arg | Enable debug handler |

CLI example:
```
ClickShare.exe -enablelogging -debuglogging
ClickShare.exe -enablelogging -loglevel debug
```

---

### wave4_tool.bat

Interactive menu for controlling the Duvel ethernet interface via ADB.

```
scripts\wave4_tool.bat
```

**Menu options:**
- Connect by IP address or USB serial
- Ethernet UP — `ip link set eth0 up`
- Ethernet DOWN — `ip link set eth0 down`
- Show eth0 status and IP address
- Show all network interfaces
- Show all IP addresses

Automatically runs `adb root` before ethernet up/down commands (requires debug or test build).

### setup_tool.bat / setup_tool.py

Automates the full MDEP Device Setup Wizard + Teams sign-in flow.  
Uses a polling loop to detect which page is currently active and handle it —  
resilient to page-order differences across firmware versions.

```
scripts\setup_tool.bat
```

**Interactive menu** prompts for connection type (IP or USB serial), then runs the Python script with default credentials. Credentials can be overridden by passing arguments directly to `setup_tool.py`:

```bash
python scripts/setup_tool.py --ip 192.168.1.100
python scripts/setup_tool.py --serial 1882000501 --admin-password Admin@123
python scripts/setup_tool.py --ip 192.168.1.100 --email user@domain.com --password MyPW
```

**Pages handled (any order):** confirm connection, provider selection, language, network, date/time, terms, privacy, firmware update, XMS Cloud (skip), admin password, confirm installation, setup complete, Teams sign-in, Teams email, Azure password, device registration.

**Flow ends** once either the MTR home screen (Duvel) or the ClickShare main screen (Duvel & god) is reached.

**Timeout:** 10 minutes total. Polls every 2 seconds.

### adb_key_switch.bat

Switches the active ADB vendor key between Duvel and Fruitesse devices.

### duvel_setup.bat

Interactive helper for Wave4 Duvel device provisioning (manufacturing mode, serial number, certificate, SSID).

```
scripts\duvel_setup.bat
```

**Menu options:**

| Option | Description |
|--------|-------------|
| `[1]` | Enable Manufacturing Mode |
| `[2]` | Set Serial Number |
| `[3]` | Reboot Base Unit |
| `[4]` | Activate Development Certificate |
| `[5]` | Create Development Certificate (ClickShare) |
| `[6]` | Set SSID (`ClickShare-<SN>`) |
| `[7]` | **Setup** — run MDEP setup wizard + Teams sign-in via `setup_tool.py` |
| `[8]` | Run All Steps 1–6 in sequence |
| `[9]` | **Run All Steps + Auto Setup** — steps 1–6 then wizard (full one-shot init) |
| `[A]` | Find Device IP Address (adb) |
| `[B]` | Change Device IP |
| `[C]` | Change SN |

### god_setup.bat

Interactive helper for production-line device setup via the Base Unit's God-mode REST API (separate from ADB-based `duvel_setup.bat`).

```
scripts\god_setup.bat
```

**Menu options:**

| Option | Description |
|--------|--------------|
| `[1]` | Enable Manufacturing Mode |
| `[2]` | Set Serial Number |
| `[3]` | Set Part Number |
| `[4]` | Set Ethernet MAC Address |
| `[5]` | Set WiFi Configuration (calls `set_wifi_config.ps1`) |
| `[6]` | Install ClickShare Certificate |
| `[7]` | Install MDEP Enrollment Certificate |
| `[8]` | Install MDEP Platform Certificate |
| `[9]` | Setup OOBE |
| `[10]` | Run All Steps (1–9 in sequence) |
| `[B]` | Enable Secure Boot |
| `[E]` | Read Secure Boot Status |
| `[G]` | Get Current Firmware Version |
| `[N]` | Read Part Number |
| `[V]` | Override ClickShare Certificate |
| `[X]` | Reboot Device |
| `[R]` / `[D]` | Refresh / Select Device (adb) |
| `[S]` / `[P]` / `[M]` / `[F]` | Change Serial Number / Part Number / MAC Address / FW Build Dir |

### set_wifi_config.ps1

Configures the Base Unit's WiFi Access Point (SSID, channel, band) via the v3 REST API (port 4003 by default). Called by `god_setup.bat` option `[5]`, or standalone:

```powershell
scripts\set_wifi_config.ps1 -DeviceIp 192.168.1.100 -Ssid Clickshare-9752000162 -Channel 7
```

The `/v3/login/internal` endpoint returns a short-lived (1 minute) session via a `Set-Cookie: client-session=<jwt>` header — a fresh login is performed immediately before each REST call, and PowerShell's `WebRequestSession` (`-SessionVariable`/`-WebSession`) captures/resends that cookie automatically.

### HID diagnostic scripts

Standalone PowerShell tools for troubleshooting the Gen5 ClickShare Button (VID=0600 PID=0185) HID binding on Windows:

| Script | Purpose |
|--------|---------|
| `diagnose-hid-binding.ps1` | Inspect USB/HID registry driver bindings for the Gen5 Button; run with `BarcoClickShareAutorunService` disabled |
| `find-hid-holder.ps1` | Enumerate which processes hold open handles to the Gen5 Button HID device |
| `fix-barco-driver.ps1` | Remove duplicate `BarcoClickShareDrv` registry entries via `pnputil` (requires Administrator) |
| `test-hid-clickshare.ps1` | Open/read/write the Gen5 Button HID device from PowerShell directly (no build required) |

---

## src/ utilities

Standalone tools that don't fit the ADB test-case flow above. Not covered by `testcases/`'s `sys.path` resolution — each is self-contained or adds its own path.

### src/timesheet — Timesheet Auto-Fill

Automates SAP Fiori CATS time entry so weekly hours don't have to be filled manually.

**fill_timesheet.py** — Playwright-based, logs in via the Edge persistent profile:

```bash
pip install playwright click python-dotenv
playwright install msedge

python src/timesheet/fill_timesheet.py                     # fill today (headed, with backfill Mon-today)
python src/timesheet/fill_timesheet.py --date 2026-05-30   # specific date
python src/timesheet/fill_timesheet.py --hidden            # headless Edge
python src/timesheet/fill_timesheet.py --no-backfill       # only fill the target date
python src/timesheet/fill_timesheet.py --skip              # exit without filling (notifies Telegram)
```

**fill_timesheet2.py** — same behaviour, driven instead through `common.edge_desktop.EdgeController` + `timesheet_page.TimesheetPage` (pure UI Automation, no Playwright/browser profile):

```bash
pip install pywinauto pywin32 click python-dotenv

python src/timesheet/fill_timesheet2.py
python src/timesheet/fill_timesheet2.py --date 2026-07-22
python src/timesheet/fill_timesheet2.py --date 2026-07-22 --assignment Duvel --hours 8
python src/timesheet/fill_timesheet2.py --date 2026-07-22 --no-backfill
python src/timesheet/fill_timesheet2.py --skip
```

By default every weekday from Monday of the target week up to the target date is checked; any day not already Approved / Sent For Approval / recorded is filled. `TimesheetPage.fill_day()` only supports whole-hour values — SAP's Hours field rejects typed digits and only accepts Up/Down arrow-key increments of 1.0.

The Telegram notification reports only the target date's outcome (not the whole backfilled week), prefixed with an OK (✅) or FAIL (❌) icon and a screenshot of the Edge window attached. It's OK whenever the target date ends up filled this run or was already filled/approved before this run; FAIL only when the row can't be located or an exception is raised.

Both variants require `src/timesheet/.env` with at least `SAP_URL` (plus `DEFAULT_ASSIGNMENT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` for notifications — not committed). Logs to `src/timesheet/log/`.

⚠️ These operate on a real SAP account — `submit()` saves entered records with no dry-run mode.

### src/hid-test — HID open-access test

Windows x64 C++ tool to enumerate ClickShare Gen4 (PID=0x00CE) and Gen5 (PID=0x0185) Buttons (VID=0x0600) and verify HID open access.

```bat
src\hid-test\build.bat   :: compile with MSVC (auto-detects VS 2017/2019/2022)
src\hid-test\hid_test.exe
```

### src/hid-desc — HID descriptor tool

ADB-based menu tool to inspect, backup/restore, and patch the ClickShare Button's HID report descriptor (`/clickshare/hid*.bin`, accessed as root via `adb` — Button must be USB-connected).

```bat
src\hid-desc\hid_desc_tool.bat
```

```bash
python src/hid-desc/parse_hid_desc.py <file.bin> [file2.bin ...]
python src/hid-desc/patch_hid_desc.py <file.bin> --usage-page 0x0081 --usage 0x83
```

---

## tools/v4l2_stream_test

Minimal C program that verifies a V4L2 device can actually deliver frames.

```
usage: v4l2_stream_test /dev/videoX [output_file]
```

- If `output_file` is given, raw frame bytes are written there (MJPEG → valid JPEG).
- Compiled as a static ARM64 binary using Android NDK r28 (Android API 26+).

To recompile:
```bash
NDK=$ANDROID_HOME/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin
$NDK/aarch64-linux-android26-clang -static -o tools/v4l2_stream_test tools/v4l2_stream_test.c
```

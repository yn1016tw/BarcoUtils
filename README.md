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
- Windows Teams desktop (for `testcases/common/teams_meeting_host.py`): `pip install pywinauto pywin32`

---

## Repository Structure

```
BarcoUtils/
├── testcases/
│   ├── common/
│   │   ├── duvel_device.py        # DuvelDevice — ADB wrapper (reusable)
│   │   ├── ui_mtr.py              # MtrUi — ADB-based UI controller for MTR / Teams
│   │   ├── ui_base.py             # BasePage — shared base class for all page objects
│   │   ├── ui_main.py             # MainPage — Teams Rooms home screen
│   │   ├── ui_invite_people.py    # InvitePeoplePage — "Invite people to join you" dialog
│   │   ├── ui_in_call.py          # InCallPage — active call screen
│   │   ├── ui_more_menu.py        # MoreMenuPage — More overlay menu
│   │   ├── ui_settings.py         # SettingsPage — Settings dialog
│   │   ├── ui_device_settings.py  # DeviceSettingsPage — Android Device Settings
│   │   ├── ui_norden_call.py      # NordenCallPage — dial screen
│   │   ├── ui_join_with_id.py     # JoinWithIdPage — Join with an ID dialog
│   │   ├── teams_desktop.py       # TeamsDesktopController — Windows Teams desktop automation
│   │   ├── teams_meeting_host.py  # Windows host: create Meet Now meeting, auto-admit from lobby
│   │   └── version.py             # VERSION string
│   ├── test_peripheral.py         # Peripheral boot-time test (camera / mic / speaker)
│   ├── test_mtr_meet_now.py       # MTR camera test (reboot → Teams UI → Meet now → screenshot)
│   └── test_mtr_join_call.py      # MTR join-call test (reboot → join by ID → in-call screenshot)
├── data/
│   └── barco_tone_2s.wav          # Pre-generated 1 kHz / 2 s tone (pushed by push_peripheral_resources)
├── scripts/
│   ├── adb_key_switch.bat         # Switch active ADB key between Duvel / Fruitesse
│   └── duvel_setup.bat            # Interactive Duvel device setup helper
└── tools/
    ├── v4l2_stream_test.c         # Minimal V4L2 streaming test (source)
    └── v4l2_stream_test           # Precompiled static ARM64 binary (Android 26+)
```

---

## testcases/test_peripheral.py

Measures how long after reboot it takes for the camera (UVC), microphone, and speaker to become ready.  
Supports stress testing (configurable iterations), selective test execution, and logs results to a dated file.

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
| `--output-dir DIR` | `logs` | Directory for log file and captured frames |
| `--boot-timeout SEC` | 300 | Max seconds to wait for boot |
| `--device-timeout SEC` | 120 | Max seconds to wait for camera / audio |
| `--fail-fast` | off | Stop after the first failed round |

### Output

```
[Round 1/3] PASS
  Reboot triggered    : 14:30:00.123
  Boot ready          : 14:30:44.901  (+44.8s)  PASS
  Camera working      : 14:31:05.210  (+20.3s from boot)  PASS  [/dev/video0  Rally Camera]
  Frame saved         : logs/files/round01.jpg
  Audio card ready    : 14:31:06.400  (+21.5s from boot)  PASS  [RallyCamera  Rally Camera]
  Speaker working     : 14:31:08.612  (+23.7s from boot)  PASS
  Mic working         : 14:31:11.003  (+26.1s from boot)  PASS  RMS=412
  Total (reboot->mic) : 70.9s
```

Log file: `<output-dir>/YYYYMMDD.log`  
Frames: `<output-dir>/files/round01_HHMMSS.jpg`, …

---

## testcases/test_mtr_meet_now.py

Verifies the Teams Rooms camera flow end-to-end after a full reboot, with per-step timestamps.

### Test procedure

| Step | Action | Pass condition |
|------|--------|----------------|
| 1 | Reboot device | Command accepted |
| 2 | Wait for boot | `sys.boot_completed` + `bootanim` + `pm list packages` |
| 3 | Wait for main page | `meetnow_btn` visible in UI hierarchy |
| 4 | Tap "Meet now" | Button found and tapped |
| 5 | Invite dialog visible | `invite_button` or "Invite people to join you" text found |
| 6 | Dismiss dialog | Dismiss (X) button found and tapped |
| 7 | Screenshot saved | PNG written to `files/` |
| 8 | Hang up | End call button found and tapped |

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
| `--output-dir DIR` | `logs` | Directory for log file and screenshots |
| `--boot-timeout SEC` | 300 | Max seconds to wait for boot |
| `--device-timeout SEC` | 120 | Max seconds to wait for main page |
| `--fail-fast` | off | Stop after the first failed round |

### Output

```
[Round 1/1] PASS
  Reboot triggered      : 14:30:00.123
  Boot ready            : 14:30:44.901  (+44.8s)  PASS
  Main page visible     : 14:30:52.210  (+7.3s from boot)  PASS
  Meet now tapped       : 14:30:52.650  (+7.7s from boot)  PASS
  Invite dialog visible : 14:30:53.900  (+9.0s from boot)  PASS
  Dialog dismissed      : 14:30:54.300  (+9.4s from boot)  PASS
  Screenshot saved      : 14:30:55.100  (+10.2s from boot)  PASS
  Screenshot path       : logs/files/round01_143054.png
  Call ended            : 14:30:55.600  (+10.7s from boot)  PASS
  Total (reboot->shot)  : 55.0s
```

Log file: `<output-dir>/YYYYMMDD.log`  
Screenshots: `<output-dir>/files/round01_HHMMSS.png`, …

---

## testcases/test_mtr_join_call.py

Verifies the Teams Rooms join-by-ID flow end-to-end after a full reboot.  
Designed to run alongside `testcases/common/teams_meeting_host.py` on the Windows PC.

### Test procedure

| Step | Action | Pass condition |
|------|--------|----------------|
| 1 | Reboot device | Command accepted |
| 2 | Wait for boot | `sys.boot_completed` + `bootanim` + `pm list packages` |
| 3 | Wait for main page | Teams Rooms home screen visible |
| 4 | Tap "Join with an ID" | Button found and tapped |
| 5 | Join dialog visible | Join-with-ID form visible |
| 6 | Enter meeting ID + passcode | Fields filled and confirmed |
| 7 | Tap "Join Teams meeting" | Join button tapped |
| 8 | In-call screen visible | Active call screen detected |
| 9 | Screenshot saved | PNG written to `files/` |
| 10 | Hang up | End call button tapped |

### Usage

```bash
# Manual meeting ID
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-id 123456789
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-id 123456789 --passcode abc123

# Load meeting info from teams_meeting_host.py (default path)
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --from-host

# Load from custom directory
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-info-dir C:/logs

# Stress test
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --from-host --iterations 5
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
| `--output-dir DIR` | `logs` | Directory for log file and screenshots |
| `--boot-timeout SEC` | 300 | Max seconds to wait for boot |
| `--device-timeout SEC` | 120 | Max seconds to wait for Teams Rooms UI |
| `--fail-fast` | off | Stop after the first failed round |

---

## testcases/common/teams_meeting_host.py

Windows-side host script. Creates a Meet Now meeting in Teams desktop, writes meeting info to JSON,  
and automatically admits MTR devices from the lobby.

Requires `pip install pywinauto pywin32`.

### Usage

```bash
# Start meeting and auto-admit (default)
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
| `--output-dir DIR` | `logs/` next to script | Directory for `meeting_info.json` and `YYYYMMDD_meeting_host.log` |
| `--accept-video` | off | Accept calls with video (default: audio only) |
| `--no-auto-accept` | off | Create meeting and print info, then exit |
| `--connect-timeout SEC` | 30 | Seconds to wait for Teams to start |
| `--meeting-timeout SEC` | 30 | Seconds to wait for meeting to be created |

### meeting_info.json

Written to `<output-dir>/meeting_info.json` once the meeting is created.  
`test_mtr_join_call.py` reads this file via `--from-host` or `--meeting-info-dir`.

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
python testcases/common/teams_meeting_host.py --output-dir C:/logs
```

**MTR device** — run once the host is ready:
```bash
python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-info-dir C:/logs
```

The join-call test polls for `meeting_info.json` (up to `--meeting-info-timeout` seconds),  
so both processes can be started in any order.

---

## common/teams_desktop.py — TeamsDesktopController

pywinauto-based automation for the Windows Teams desktop app.

```python
from common.teams_desktop import TeamsDesktopController

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

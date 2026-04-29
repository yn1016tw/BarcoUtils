# BarcoUtils

Standalone test utilities for Barco Duvel (ClickShare base unit).  
No dependency on TEnTo or the Wave4 BSP — only `adb` in PATH and Python 3.10+.

---

## Repository Structure

```
BarcoUtils/
├── testcases/
│   ├── common/
│   │   ├── duvel_device.py       # DuvelDevice — ADB wrapper (reusable)
│   │   ├── ui_mtr.py             # MtrUi — ADB-based UI controller for MTR / Teams
│   │   ├── ui_base.py            # BasePage — shared base class for all page objects
│   │   ├── ui_main.py            # MainPage — Teams Rooms home screen
│   │   ├── ui_invite_people.py   # InvitePeoplePage — "Invite people to join you" dialog
│   │   ├── ui_in_call.py         # InCallPage — active call screen
│   │   └── version.py            # VERSION string
│   ├── test_peripheral.py        # Peripheral boot-time test (camera / mic / speaker)
│   └── test_mtr_camera.py        # MTR camera test (reboot → Teams UI → screenshot)
├── data/
│   └── barco_tone_2s.wav         # Pre-generated 1 kHz / 2 s tone (pushed once at connect)
├── scripts/
│   ├── adb_key_switch.bat        # Switch active ADB key between Duvel / Fruitesse
│   └── duvel_setup.bat           # Interactive Duvel device setup helper
└── tools/
    ├── v4l2_stream_test.c        # Minimal V4L2 streaming test (source)
    └── v4l2_stream_test          # Precompiled static ARM64 binary (Android 26+)
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

Console header:
```
Peripheral Test  v1.9.1
  Device     : 10.102.94.110:5555
  FW         : 04.03.00.master-1649
  Iterations : 3
  Tests      : camera speaker mic
  Output dir : logs
  [ADB] Connected to 10.102.94.110:5555
  [ADB] v4l2_stream_test -> /data/local/tmp/v4l2_stream_test
  [ADB] barco_tone_2s.wav -> /data/local/tmp/barco_tone_2s.wav
```

Console (per round):
```
[Round 1/3] PASS
  Reboot triggered    : 14:30:00.123
  Boot ready          : 14:30:44.901  (+44.8s)  PASS
  Camera working      : 14:31:05.210  (+20.3s from boot)  PASS  [/dev/video0  Rally Camera]
  Frame saved         : logs/frames/round01.jpg
  Audio card ready    : 14:31:06.400  (+21.5s from boot)  PASS  [RallyCamera  Rally Camera]
  Speaker working     : 14:31:08.612  (+23.7s from boot)  PASS
  Mic working         : 14:31:11.003  (+26.1s from boot)  PASS  RMS=412
  Total (reboot->mic) : 70.9s
```

Summary:
```
=== Summary (3/3 PASS) ===
  Total time    min/avg/max: 68.1s / 70.9s / 73.4s
  Boot time     min/avg/max: 43.2s / 44.8s / 46.1s
  Camera ready  min/avg/max: 19.5s / 20.3s / 21.0s
  Audio card    min/avg/max: 20.8s / 21.5s / 22.3s
  Speaker ready min/avg/max: 22.1s / 23.7s / 25.0s
  Mic ready     min/avg/max: 24.9s / 26.1s / 27.5s
```

Log file: `logs/test_peripheral/YYYYMMDD/YYYYMMDD.log` (appended on each run)  
Frames: `logs/test_peripheral/YYYYMMDD/files/round01_HHMMSS.jpg`, …

---

## testcases/test_mtr_camera.py

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
python testcases/test_mtr_camera.py --ip 192.168.1.100
python testcases/test_mtr_camera.py --serial 1882000501 --iterations 3
python testcases/test_mtr_camera.py --ip 192.168.1.100 --output-dir C:/logs --fail-fast
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
  Screenshot path       : logs/test_mtr_camera/20260429/files/round01_143054.png
  Call ended            : 14:30:55.600  (+10.7s from boot)  PASS
  Total (reboot->shot)  : 55.0s
```

Log file: `logs/test_mtr_camera/YYYYMMDD/YYYYMMDD.log` (appended on each run)  
Screenshots: `logs/test_mtr_camera/YYYYMMDD/files/round01_HHMMSS.png`, …

---

## common/ui_mtr.py — MtrUi

ADB-based UI controller for Microsoft Teams Rooms. Wraps raw ADB input, UI hierarchy queries, and app lifecycle. Page objects are accessed via lazy properties.

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
ui.invite_people.is_visible()
ui.invite_people.dismiss()
ui.in_call.hang_up()
```

`device.ui` returns the `MtrUi` for a `DuvelDevice` (lazy property, same serial).

### Page objects

| Property | Class | File | Screen |
|----------|-------|------|--------|
| `ui.main` | `MainPage` | `ui_main.py` | Teams Rooms home screen |
| `ui.invite_people` | `InvitePeoplePage` | `ui_invite_people.py` | "Invite people to join you" dialog |
| `ui.in_call` | `InCallPage` | `ui_in_call.py` | Active call screen |

All page objects inherit `BasePage` (`ui_base.py`) which provides `__init__(ui)` and `_tap(candidates)`. Element matching tries `resource_id` first, `content_desc` second.

---

## common/duvel_device.py

Reusable `DuvelDevice` class. All ADB interaction lives here — import it in other scripts as needed.

```python
from common.duvel_device import DuvelDevice

device = DuvelDevice(serial="192.168.1.100:5555", is_ip=True)
device.connect()                                    # adb connect + push test binary + push tone WAV
device.fw_version()                                 # ro.barco.build.version
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

The binary is pushed to `/data/local/tmp/v4l2_stream_test` once at `connect()`.

### Audio check detail

`/proc/asound/cards` is readable without root and confirms the kernel has enumerated the audio device.  
USB-Audio cards (external camera mic/speaker) are preferred over the internal MT8195 SOC audio.

`tinyplay` and `tinycap` require access to `/dev/snd/pcm*` which is owned by `system:audio`. Since `adb shell` runs as the `shell` user (not in the `audio` group), both commands are prefixed with `su root`.

### Speaker test

`test_speaker(duration)` plays `data/barco_tone_2s.wav` (pre-pushed at `connect()`) via `tinyplay`. Returns `True` if exit 0.

### Mic test

`test_mic(duration, rms_threshold)` records via `tinycap` and measures RMS. Returns `(passed, rms)`.

| RMS range | Meaning |
|-----------|---------|
| < 50 | Near silence — hardware not responding |
| 50–100 | Below default threshold |
| > 100 (default threshold) | Ambient noise confirmed |

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

---

## Requirements

- Python 3.10+
- `adb` in PATH
- Duvel device accessible via USB or TCP/IP

---

See [CHANGELOG.txt](CHANGELOG.txt) for version history.

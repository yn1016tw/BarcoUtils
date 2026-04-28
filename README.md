# BarcoUtils

Standalone test utilities for Barco Duvel (ClickShare base unit).  
No dependency on TEnTo or the Wave4 BSP — only `adb` in PATH and Python 3.10+.

---

## Repository Structure

```
BarcoUtils/
├── common/
│   ├── duvel_device.py     # DuvelDevice — ADB wrapper (reusable)
│   └── version.py          # VERSION string
├── data/
│   └── barco_tone_2s.wav   # Pre-generated 1 kHz / 2 s tone (pushed once at connect)
├── tools/
│   ├── v4l2_stream_test.c  # Minimal V4L2 streaming test (source)
│   └── v4l2_stream_test    # Precompiled static ARM64 binary (Android 26+)
└── test_peripheral.py      # Peripheral test script
```

---

## test_peripheral.py

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
python test_peripheral.py --serial 1882000501 --iterations 5

# ADB over TCP/IP
python test_peripheral.py --ip 192.168.1.100 --iterations 3

# Camera only
python test_peripheral.py --ip 192.168.1.100 --tests camera

# Speaker and mic only
python test_peripheral.py --ip 192.168.1.100 --tests speaker mic

# Custom output directory
python test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs
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

### Output

Console header:
```
Peripheral Test  v1.8.0
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

Log file: `logs/YYYYMMDD.txt` (appended on each run)  
Frames: `logs/frames/round01.jpg`, `round02.jpg`, …

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

## Changelog

### v1.8.0
- `test_peripheral.py`: FW version (`ro.barco.build.version`) shown in startup header
- `test_peripheral.py`: ADB connection logs moved to after the header block
- `test_peripheral.py`: default `--output-dir` changed from `.` to `logs`; `logs/` and `logs/frames/` created at startup

### v1.7.0
- `test_peripheral.py`: add `--tests` argument to selectively run `camera`, `speaker`, `mic` (default: all)
- `common/duvel_device.py`: add `fw_version()` — reads `ro.barco.build.version` via `getprop`

### v1.6.0
- Remove `common/usb_switcher.py` (AcronameHubSwitcher) and `test_usb_switcher.py`
- `test_peripheral.py`: remove per-metric pass/fail counts from summary output

### v1.5.0
- `test_peripheral.py`: each step in per-round output now shows `PASS` or `FAIL` inline

### v1.4.0
- `common/duvel_device.py`: prefix `tinyplay`/`tinycap` with `su root`
- `common/duvel_device.py`: `data/barco_tone_2s.wav` generated once locally and pushed at `connect()`

### v1.3.0
- OOP refactoring — no behaviour change, public API unchanged

### v1.2.0
- `common/duvel_device.py`: add `test_speaker(duration)` and `test_mic(duration, rms_threshold)`
- `test_peripheral.py`: speaker and mic steps with independent timing

### v1.1.1
- Bug fixes: `connect()`/`disconnect()`, `reboot()` timeout handling, streaming test ADB timeout
- `tools/v4l2_stream_test.c`: 5 s AF/AE/AWB warm-up before saving frame

### v1.1.0
- `common/duvel_device.py`: add `test_audio_loopback()`, `_get_usb_audio_card()`

### v1.0.0
- Initial release: peripheral boot-time measurement (camera / mic / speaker)
- `common/duvel_device.py`: reusable ADB wrapper with 4-step boot detection
- `tools/v4l2_stream_test`: static ARM64 binary compiled with NDK r28

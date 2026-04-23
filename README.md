# BarcoUtils

Standalone test utilities for Barco Duvel (ClickShare base unit).  
No dependency on TEnTo or the Wave4 BSP — only `adb` in PATH and Python 3.10+.

---

## Repository Structure

```
BarcoUtils/
├── common/
│   └── duvel_device.py     # DuvelDevice — ADB wrapper (reusable)
├── tools/
│   ├── v4l2_stream_test.c  # Minimal V4L2 streaming test (source)
│   └── v4l2_stream_test    # Precompiled static ARM64 binary (Android 26+)
└── test_peripheral.py      # Peripheral boot-time measurement script
```

---

## test_peripheral.py

Measures how long after reboot it takes for the camera (UVC), microphone, and speaker to become ready.  
Supports stress testing (configurable iterations) and logs results to a dated file.

### What it tests

| Step | Method | Pass condition |
|------|--------|----------------|
| Boot complete | `getprop sys.boot_completed` + `init.svc.bootanim` + `pm list packages` | All three pass |
| Camera streaming | sysfs `uvcvideo` driver check → `v4l2_stream_test` STREAMON + DQBUF | Frame delivered within 5 s |
| Audio (mic/speaker) | `/proc/asound/cards` — prefers USB-Audio card over internal SOC | Card enumerated by kernel |

A captured JPEG frame is saved locally for every camera check.

### Usage

```bash
# USB serial
python test_peripheral.py --serial 1882000501 --iterations 5

# ADB over TCP/IP
python test_peripheral.py --ip 192.168.1.100 --iterations 3

# Custom output directory
python test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs
```

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--serial SERIAL` | — | USB ADB serial number (mutually exclusive with `--ip`) |
| `--ip IP[:PORT]` | — | ADB over TCP/IP (default port 5555) |
| `--iterations N` | 1 | Number of test rounds |
| `--output-dir DIR` | `.` | Directory for log file and captured frames |
| `--boot-timeout SEC` | 300 | Max seconds to wait for boot |
| `--device-timeout SEC` | 120 | Max seconds to wait for camera / audio |

### Output

Console (per round):
```
[Round 1/3] PASS
  Reboot triggered    : 14:30:00.123
  Boot ready          : 14:30:44.901  (+44.8s)
  Camera working      : 14:31:05.210  (+20.3s from boot) [/dev/video0  Rally Camera]
  Frame saved         : ./frames/round01.jpg
  Audio working       : 14:31:06.400  (+21.5s from boot) [RallyCamera  Rally Camera]
  Total (reboot→audio): 66.3s

=== Summary (3/3 PASS) ===
  Total time    min/avg/max: 64.1s / 66.3s / 68.7s
  Boot time     min/avg/max: 43.2s / 44.8s / 46.1s
  Camera ready  min/avg/max: 19.5s / 20.3s / 21.0s
  Audio ready   min/avg/max: 20.8s / 21.5s / 22.3s
```

Log file: `<output-dir>/YYYYMMDD.txt` (appended on each run)  
Frames: `<output-dir>/frames/round01.jpg`, `round02.jpg`, …

---

## common/duvel_device.py

Reusable `DuvelDevice` class.  
All ADB interaction lives here — import it in other test scripts as needed.

```python
from common.duvel_device import DuvelDevice

device = DuvelDevice(serial="192.168.1.100:5555", is_ip=True)
device.connect()                                    # adb connect + push test binary
device.reboot()
device.wait_for_boot(timeout=300)
dev, name = device.wait_for_camera_working(120, frame_save_path="frame.jpg")
card, full = device.wait_for_audio_working(120)
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

`tinymix` requires root. `/proc/asound/cards` is readable without root and confirms the kernel has enumerated the audio device.  
USB-Audio cards (external camera mic/speaker) are preferred over the internal MT8195 SOC audio.

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

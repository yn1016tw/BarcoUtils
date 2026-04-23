# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Standalone ADB-based test utilities for the Barco Duvel (ClickShare base unit). No dependency on TEnTo or the Wave4 BSP — only requires `adb` in PATH and Python 3.10+.

## Running the test

```bash
# USB
python test_peripheral.py --serial 1882000501 --iterations 5

# TCP/IP
python test_peripheral.py --ip 192.168.1.100 --iterations 3

# With custom output dir
python test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs
```

No install step — run directly from the repo root. There are no automated tests, linting config, or build system.

## Recompiling the ARM64 binary

```bash
NDK=$ANDROID_HOME/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin
$NDK/aarch64-linux-android26-clang -static -o tools/v4l2_stream_test tools/v4l2_stream_test.c
```

## Architecture

```
common/duvel_device.py   — DuvelDevice class (all ADB logic lives here)
test_peripheral.py       — CLI entry point + TestResult / ResultWriter / PeripheralTestRunner
tools/v4l2_stream_test   — Static ARM64 binary pushed to device at connect() time
common/version.py        — VERSION string (bump manually on releases)
```

**Data flow in test_peripheral.py:**
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
- `test_audio_loopback(duration, rms_threshold)` → `(passed, rms, card_name)`

**Key implementation details:**
- Camera check uses a two-stage approach: sysfs UVC enumeration (no `v4l2-ctl`) → `v4l2_stream_test` STREAMON + 5s AF/AE warm-up + DQBUF
- Audio card detection reads `/proc/asound/cards` (no root required); prefers USB-Audio cards over internal SOC
- `_adb_raw()` never raises; `_adb()` raises on non-zero exit. Internal polling uses `_poll_until()` with a 2s interval
- `connect()` must be called before any device operations; for TCP/IP it runs `adb connect`, for USB it verifies presence in `adb devices`
- Log file is appended to `<output-dir>/YYYYMMDD.txt`; frames go to `<output-dir>/frames/roundNN.jpg`

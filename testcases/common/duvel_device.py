"""
DuvelDevice — ADB wrapper for Barco Duvel base unit.
Provides reboot, boot-wait, camera, and audio device checks.

Requires `adb` in PATH.
"""

import math
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path

_POLL_INTERVAL = 2  # seconds between polls

_DATA_DIR = Path(__file__).parent.parent / "data"

# Precompiled static ARM64 binary; pushed once per test run to /data/local/tmp/
_STREAM_TEST_BIN_LOCAL = str(Path(__file__).parent.parent / "tools" / "v4l2_stream_test")
_STREAM_TEST_BIN_REMOTE = "/data/local/tmp/v4l2_stream_test"

# 1 kHz / 2 s tone WAV; generated locally if absent, pushed once at connect()
_TONE_WAV_2S_LOCAL  = str(_DATA_DIR / "barco_tone_2s.wav")
_TONE_WAV_2S_REMOTE = "/data/local/tmp/barco_tone_2s.wav"

_REC_PCM_REMOTE = "/data/local/tmp/rec_loopback.pcm"


class DuvelDevice:
    def __init__(self, serial: str, is_ip: bool):
        self._serial = serial      # e.g. "ABC123" or "192.168.1.100:5555"
        self._is_ip = is_ip
        self._ui = None            # lazily created by .ui property

    @property
    def ui(self) -> "MtrUi":
        """Return the MtrUi controller for this device (created on first access)."""
        if self._ui is None:
            from common.ui_mtr import MtrUi
            self._ui = MtrUi(self._serial)
        return self._ui

    @property
    def label(self) -> str:
        return self._serial

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self._is_ip:
            result = subprocess.run(
                ["adb", "connect", self._serial],
                capture_output=True, text=True, timeout=15,
            )
            out = result.stdout.strip()
            if "connected" not in out.lower() and "already" not in out.lower():
                raise ConnectionError(f"adb connect failed: {out}")
        else:
            result = self._adb_raw(["devices"], timeout=10)
            if self._serial not in result.stdout:
                raise ConnectionError(f"Device {self._serial} not found in adb devices")
        self._push_stream_test_bin()
        self._push_tone_wav()

    def disconnect(self) -> None:
        if self._is_ip:
            subprocess.run(["adb", "disconnect", self._serial], capture_output=True, timeout=5)

    # ------------------------------------------------------------------
    # Boot lifecycle
    # ------------------------------------------------------------------

    def reboot(self) -> None:
        # adb reboot drops the connection as the device shuts down — ignore timeout/errors
        try:
            self._adb_raw(["reboot"], timeout=10)
        except subprocess.TimeoutExpired:
            pass
        deadline = time.time() + 30
        while time.time() < deadline:
            result = self._adb_raw(["get-state"], timeout=3)
            if result.returncode != 0 or "device" not in result.stdout:
                return
            time.sleep(1)

    def wait_for_boot(self, timeout: int) -> None:
        """Mirror TEnTo wait_for_base_unit_running():
        1. wait-for-device
        2. sys.boot_completed == 1
        3. init.svc.bootanim == stopped
        4. pm list packages responds
        """
        deadline = time.time() + timeout

        remaining = max(1, int(deadline - time.time()))
        result = self._adb_raw(["wait-for-device"], timeout=remaining)
        if result.returncode != 0:
            raise TimeoutError("Device not detected by ADB within timeout")

        self._poll_until(
            lambda: self._getprop("sys.boot_completed") == "1",
            deadline,
            "sys.boot_completed never reached 1",
        )
        self._poll_until(
            lambda: self._getprop("init.svc.bootanim") == "stopped",
            deadline,
            "Boot animation never stopped",
        )
        self._poll_until(
            lambda: self._pm_list_responds(),
            deadline,
            "Package manager never responded",
        )

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    def wait_for_camera_working(self, timeout: int, frame_save_path: str | None = None) -> tuple[str, str]:
        """Wait until any UVC camera can stream.
        Returns (device_path, camera_name), e.g. ('/dev/video0', 'HD Pro Webcam C920').
        If frame_save_path is given, pulls one captured JPEG frame to that local path.
        """
        found = [None]

        def check():
            result = self._find_working_camera(frame_save_path)
            if result:
                found[0] = result
                return True
            return False

        self._poll_until(check, time.time() + timeout, "No working camera found within timeout")
        return found[0]

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    def wait_for_audio_working(self, timeout: int) -> tuple[str, str]:
        """Wait until an audio device is enumerated in /proc/asound/cards.
        Returns (short_name, full_name), e.g. ('C920', 'HD Pro Webcam C920').
        """
        found = [None]

        def check():
            result = self._find_working_audio()
            if result:
                found[0] = result
                return True
            return False

        self._poll_until(check, time.time() + timeout, "No working audio device found within timeout")
        return found[0]

    def test_speaker(self, duration: int = 2) -> bool:
        """Play a 1kHz tone through the speaker.  Returns True if tinyplay exits 0."""
        card_info = self._get_usb_audio_card()
        if card_info is None:
            raise RuntimeError("No audio card found on device")
        card_num, _, _ = card_info
        result = self._adb_raw(["shell", f"su root tinyplay {_TONE_WAV_2S_REMOTE} -D {card_num} -d 0"], timeout=duration + 5)
        return result.returncode == 0

    def test_mic(self, duration: int = 2, rms_threshold: float = 100.0) -> tuple[bool, float]:
        """Record from the mic for duration seconds and measure RMS.

        Returns (passed, rms).
          passed : True if rms > rms_threshold (ambient noise is sufficient)
          rms    : RMS amplitude (0-32767 scale for 16-bit audio)
        """
        card_info = self._get_usb_audio_card()
        if card_info is None:
            raise RuntimeError("No audio card found on device")
        card_num, _, _ = card_info
        local_rec = tempfile.mktemp(suffix=".pcm")
        try:
            shell_cmd = f"su root tinycap {_REC_PCM_REMOTE} -D {card_num} -d 0 -r 48000 -b 16 -c 2 -T {duration}"
            self._adb_raw(["shell", shell_cmd], timeout=duration + 5)
            self._pull_file(_REC_PCM_REMOTE, local_rec)
            try:
                rms = self._compute_rms(Path(local_rec).read_bytes())
            except OSError:
                return (False, 0.0)
            return (rms > rms_threshold, rms)
        finally:
            self._adb_raw(["shell", f"rm -f {_REC_PCM_REMOTE}"], timeout=5)
            Path(local_rec).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Camera helpers
    # ------------------------------------------------------------------

    def clear_camera_tmp(self) -> None:
        """Remove stale remote frame file before a camera test."""
        self._adb_raw(["shell", f"rm -f /data/local/tmp/v4l2_frame_tmp"], timeout=5)

    def _push_stream_test_bin(self) -> None:
        self._push_file(_STREAM_TEST_BIN_LOCAL, _STREAM_TEST_BIN_REMOTE)
        self._adb_raw(["shell", f"chmod +x {_STREAM_TEST_BIN_REMOTE}"], timeout=5)

    def _find_working_camera(self, frame_save_path: str | None = None) -> tuple[str, str] | None:
        """Returns (dev_path, camera_name) for the first UVC node that can stream.

        Step 1 — sysfs: find UVC capture nodes (driver=uvcvideo, index=0).
        Step 2 — v4l2_stream_test: open, STREAMON, dequeue one frame.
                 If frame_save_path is given, frame bytes are saved on device then
                 pulled to that local path (MJPEG -> .jpg, YUYV -> .yuv).
        """
        cmd = (
            "for node in $(ls /sys/class/video4linux/); do "
            "  drv=$(readlink /sys/class/video4linux/$node/device/driver 2>/dev/null); "
            "  idx=$(cat /sys/class/video4linux/$node/index 2>/dev/null); "
            "  if echo \"$drv\" | grep -q uvcvideo && [ \"$idx\" = '0' ]; then "
            "    echo /dev/$node; "
            "    cat /sys/class/video4linux/$node/name 2>/dev/null; "
            "    echo '---'; "
            "  fi; "
            "done"
        )
        result = self._adb_raw(["shell", cmd], timeout=10)
        if result.returncode != 0 or not result.stdout.strip():
            return None

        candidates: list[tuple[str, str]] = []
        lines = result.stdout.strip().splitlines()
        i = 0
        while i < len(lines):
            dev = lines[i].strip()
            if not dev.startswith("/dev/video"):
                i += 1
                continue
            name = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1].strip() != "---" else dev
            candidates.append((dev, name))
            i += 3

        remote_frame = "/data/local/tmp/v4l2_frame_tmp"
        for dev, name in candidates:
            run_cmd = f"{_STREAM_TEST_BIN_REMOTE} {dev}"
            if frame_save_path:
                run_cmd += f" {remote_frame}"
            r = self._adb_raw(["shell", run_cmd], timeout=25)
            if r.returncode == 0:
                if frame_save_path:
                    self._pull_frame(remote_frame, frame_save_path, r.stdout)
                return (dev, name)
        return None

    def _pull_frame(self, remote_path: str, local_path: str, binary_stdout: str) -> None:
        """Pull captured frame from device to local path."""
        ext = ".jpg"
        for line in binary_stdout.splitlines():
            if line.startswith("format"):
                if "YUYV" in line or "YUY2" in line:
                    ext = ".yuv"
                break

        local = Path(local_path)
        if local.suffix.lower() not in (".jpg", ".yuv"):
            local = local.with_suffix(ext)
        local.parent.mkdir(parents=True, exist_ok=True)

        self._pull_file(remote_path, str(local))
        self._adb_raw(["shell", f"rm -f {remote_path}"], timeout=5)

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    def _find_working_audio(self) -> tuple[str, str] | None:
        """Returns (short_name, full_name) from /proc/asound/cards, else None."""
        info = self._get_usb_audio_card()
        if info is None:
            return None
        _, short, full = info
        return (short, full)

    def _get_usb_audio_card(self) -> tuple[int, str, str] | None:
        """Return (card_num, short_name, full_name) for the USB-Audio card, else None.

        Prefers USB-Audio cards (external camera) over internal SOC audio.
        Line format: "0 [C920           ]: USB-Audio - HD Pro Webcam C920"
        """
        result = self._adb_raw(["shell", "cat /proc/asound/cards"], timeout=5)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        text = result.stdout
        if "no soundcards" in text.lower():
            return None

        usb_entry = None
        any_entry = None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or not stripped[0].isdigit():
                continue
            try:
                card_num = int(stripped.split()[0])
            except ValueError:
                continue
            short = stripped.split("[", 1)[1].split("]")[0].strip() if "[" in stripped else stripped.split()[0]
            full = stripped.split(" - ", 1)[1].strip() if " - " in stripped else short
            if any_entry is None:
                any_entry = (card_num, short, full)
            if "USB-Audio" in stripped:
                usb_entry = (card_num, short, full)
                break

        return usb_entry or any_entry

    # ------------------------------------------------------------------
    # ADB transport helpers
    # ------------------------------------------------------------------

    def _push_file(self, local_path: str, remote_path: str, timeout: int = 15) -> None:
        r = subprocess.run(
            ["adb", "-s", self._serial, "push", local_path, remote_path],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode != 0:
            raise RuntimeError(f"adb push {local_path} failed: {r.stderr.strip()}")

    def _pull_file(self, remote_path: str, local_path: str, timeout: int = 15) -> None:
        subprocess.run(
            ["adb", "-s", self._serial, "pull", remote_path, local_path],
            capture_output=True, timeout=timeout,
        )

    def _poll_until(self, condition, deadline: float, timeout_msg: str) -> None:
        while time.time() < deadline:
            try:
                if condition():
                    return
            except Exception:
                pass
            time.sleep(_POLL_INTERVAL)
        raise TimeoutError(timeout_msg)

    def fw_version(self) -> str:
        """Return ro.barco.build.version, or 'unknown' if not set."""
        result = self._adb_raw(["shell", "getprop", "ro.barco.build.version"], timeout=5)
        v = result.stdout.strip()
        return v if v else "unknown"

    def mdep_version(self) -> str:
        """Return ro.mdep.build.id, or 'unknown' if not set."""
        result = self._adb_raw(["shell", "getprop", "ro.mdep.build.id"], timeout=5)
        v = result.stdout.strip()
        return v if v else "unknown"

    def barco_platform(self) -> str:
        """Return ro.barco.platform (hardware platform, e.g. 'w4duvel'), or 'unknown'."""
        result = self._adb_raw(["shell", "getprop", "ro.barco.platform"], timeout=5)
        v = result.stdout.strip()
        return v if v else "unknown"

    def barco_product(self) -> str:
        """Return ro.barco.product (UI product name, e.g. 'Hub Pro'), or 'unknown'."""
        result = self._adb_raw(["shell", "getprop", "ro.barco.product"], timeout=5)
        v = result.stdout.strip()
        return v if v else "unknown"

    def barco_board_id(self) -> str:
        """Return ro.barco.board.id (hardware board revision, e.g. 'DVT2'), or 'unknown'."""
        result = self._adb_raw(["shell", "getprop", "ro.barco.board.id"], timeout=5)
        v = result.stdout.strip()
        return v if v else "unknown"

    def barco_build_type(self) -> str:
        """Return ro.barco.build.type (debug/test/release), or 'unknown'."""
        result = self._adb_raw(["shell", "getprop", "ro.barco.build.type"], timeout=5)
        v = result.stdout.strip()
        return v if v else "unknown"

    def barco_minimal_version(self) -> str:
        """Return ro.barco.build.minimal_version (minimum OTA-compatible version), or 'unknown'."""
        result = self._adb_raw(["shell", "getprop", "ro.barco.build.minimal_version"], timeout=5)
        v = result.stdout.strip()
        return v if v else "unknown"

    def _getprop(self, prop: str) -> str:
        result = self._adb(["shell", "getprop", prop], timeout=5)
        return result.stdout.strip()

    def _pm_list_responds(self) -> bool:
        result = self._adb_raw(["shell", "pm", "list", "packages", "-f"], timeout=10)
        return result.returncode == 0 and "package:" in result.stdout

    def _adb(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        result = self._adb_raw(args, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def _adb_raw(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        prefix = ["-s", self._serial] if self._serial else []
        cmd = ["adb"] + prefix + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    def _push_tone_wav(self) -> None:
        """Generate ./data/barco_tone_2s.wav if absent, then push to device once."""
        path = Path(_TONE_WAV_2S_LOCAL)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            self._generate_tone_wav(str(path), duration=2)
        self._push_file(_TONE_WAV_2S_LOCAL, _TONE_WAV_2S_REMOTE)

    @staticmethod
    def _generate_tone_wav(path: str, freq: int = 1000, duration: int = 3,
                           sample_rate: int = 48000, channels: int = 2) -> None:
        """Write a RIFF WAV file containing a sine-wave tone (16-bit LE, stereo)."""
        n_frames = sample_rate * duration
        amplitude = 16000  # ~half full-scale to avoid clipping
        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for i in range(n_frames):
                sample = int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate))
                wf.writeframesraw(struct.pack("<h", sample) * channels)

    @staticmethod
    def _compute_rms(data: bytes) -> float:
        """Return RMS amplitude of raw 16-bit signed LE PCM data (0-32767 scale)."""
        n = len(data) // 2
        if n == 0:
            return 0.0
        samples = struct.unpack(f"<{n}h", data[:n * 2])
        return math.sqrt(sum(s * s for s in samples) / n)

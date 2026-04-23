"""
DuvelDevice — ADB wrapper for Barco Duvel base unit.
Provides reboot, boot-wait, camera, and audio device checks.

Requires `adb` in PATH.
"""

import subprocess
import time

_POLL_INTERVAL = 2  # seconds between polls


class DuvelDevice:
    def __init__(self, serial: str, is_ip: bool):
        self._serial = serial      # e.g. "ABC123" or "192.168.1.100:5555"
        self._is_ip = is_ip

    @property
    def label(self) -> str:
        return self._serial

    def connect(self) -> None:
        if self._is_ip:
            result = self._adb_raw(["connect", self._serial], timeout=10)
            out = result.stdout.strip()
            if "connected" not in out.lower() and "already" not in out.lower():
                raise ConnectionError(f"adb connect failed: {out}")
            print(f"  [ADB] Connected to {self._serial}")
        else:
            result = self._adb_raw(["devices"], timeout=10)
            if self._serial not in result.stdout:
                raise ConnectionError(f"Device {self._serial} not found in adb devices")
            print(f"  [ADB] USB device {self._serial} found")

    def disconnect(self) -> None:
        if self._is_ip:
            self._adb_raw(["disconnect", self._serial], timeout=5)

    def reboot(self) -> None:
        self._adb(["reboot"], timeout=10)
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

        # Step 1: ADB detects device
        remaining = max(1, int(deadline - time.time()))
        result = self._adb_raw(["wait-for-device"], timeout=remaining)
        if result.returncode != 0:
            raise TimeoutError("Device not detected by ADB within timeout")

        # Step 2: sys.boot_completed == 1
        self._poll_until(
            lambda: self._getprop("sys.boot_completed") == "1",
            deadline,
            "sys.boot_completed never reached 1",
        )

        # Step 3: boot animation stopped
        self._poll_until(
            lambda: self._getprop("init.svc.bootanim") == "stopped",
            deadline,
            "Boot animation never stopped",
        )

        # Step 4: package manager responds
        self._poll_until(
            lambda: self._pm_list_responds(),
            deadline,
            "Package manager never responded",
        )

    def wait_for_camera_working(self, timeout: int) -> tuple[str, str]:
        """Wait until any UVC camera is found.
        Returns (device_path, camera_name), e.g. ('/dev/video0', 'HD Pro Webcam C920').
        """
        found = [None]

        def check():
            result = self._find_working_camera()
            if result:
                found[0] = result
                return True
            return False

        self._poll_until(check, time.time() + timeout, "No working camera found within timeout")
        return found[0]

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

    # ------------------------------------------------------------------
    # Camera helpers
    # ------------------------------------------------------------------

    def _find_working_camera(self) -> tuple[str, str] | None:
        """Returns (dev_path, camera_name) for the first UVC capture node found via sysfs.

        v4l2-ctl is not available on Duvel. sysfs is used instead:
        - device/driver symlink contains 'uvcvideo' → USB camera bound to UVC driver
        - index == 0 → video capture node (index 1 is metadata-only)
        Both the device path and human-readable name are emitted on separate lines.
        """
        cmd = (
            "for node in $(ls /sys/class/video4linux/); do "
            "  drv=$(readlink /sys/class/video4linux/$node/device/driver 2>/dev/null); "
            "  idx=$(cat /sys/class/video4linux/$node/index 2>/dev/null); "
            "  if echo \"$drv\" | grep -q uvcvideo && [ \"$idx\" = '0' ]; then "
            "    echo /dev/$node; "
            "    cat /sys/class/video4linux/$node/name 2>/dev/null; "
            "    break; "
            "  fi; "
            "done"
        )
        result = self._adb_raw(["shell", cmd], timeout=10)
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().splitlines()
        if not lines or not lines[0].startswith("/dev/video"):
            return None
        dev = lines[0].strip()
        name = lines[1].strip() if len(lines) > 1 else dev
        return (dev, name)

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    def _find_working_audio(self) -> tuple[str, str] | None:
        """Returns (short_name, full_name) from /proc/asound/cards, else None.

        tinymix requires root. /proc/asound/cards is readable without root and
        confirms the kernel has enumerated the audio device (mic+speaker ready).
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
            short = stripped.split("[", 1)[1].split("]")[0].strip() if "[" in stripped else stripped.split()[0]
            full = stripped.split(" - ", 1)[1].strip() if " - " in stripped else short
            if any_entry is None:
                any_entry = (short, full)
            if "USB-Audio" in stripped:
                usb_entry = (short, full)
                break

        return usb_entry or any_entry

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _poll_until(self, condition, deadline: float, timeout_msg: str) -> None:
        while time.time() < deadline:
            try:
                if condition():
                    return
            except Exception:
                pass
            time.sleep(_POLL_INTERVAL)
        raise TimeoutError(timeout_msg)

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

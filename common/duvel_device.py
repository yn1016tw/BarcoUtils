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

    def wait_for_camera_working(self, timeout: int) -> str:
        """Wait until any UVC camera with VIDEO_CAPTURE capability is found.
        Returns the device path (e.g. /dev/video7).
        Uses v4l2-ctl --all to verify actual capture capability, not just node presence.
        """
        found = [None]

        def check():
            dev = self._find_working_camera()
            if dev:
                found[0] = dev
                return True
            return False

        self._poll_until(check, time.time() + timeout, "No working camera found within timeout")
        return found[0]

    def wait_for_audio_working(self, timeout: int) -> str:
        """Wait until audio mixer (mic+speaker) responds via tinymix.
        Returns the card name found.
        """
        found = [None]

        def check():
            card = self._find_working_audio()
            if card:
                found[0] = card
                return True
            return False

        self._poll_until(check, time.time() + timeout, "No working audio device found within timeout")
        return found[0]

    # ------------------------------------------------------------------
    # Camera helpers
    # ------------------------------------------------------------------

    def _find_working_camera(self) -> str | None:
        """Returns first /dev/videoX that has VIDEO_CAPTURE+STREAMING capability."""
        result = self._adb_raw(["shell", "ls /dev/video*"], timeout=5)
        if result.returncode != 0 or not result.stdout.strip():
            return None

        for line in result.stdout.strip().splitlines():
            dev = line.strip()
            if not dev.startswith("/dev/video"):
                continue
            if self._camera_can_capture(dev):
                return dev
        return None

    def _camera_can_capture(self, dev: str) -> bool:
        """Check if device reports VIDEO_CAPTURE capability via v4l2-ctl."""
        result = self._adb_raw(["shell", f"v4l2-ctl --all -d {dev}"], timeout=8)
        if result.returncode != 0:
            return False
        # v4l2-ctl expands capability bits to human-readable names.
        # The "Capabilities" line includes 0x80000000 (Device Caps flag), so hex matching
        # against 0x04200001 fails. Checking for the expanded "Video Capture" text is reliable.
        return "Video Capture" in result.stdout

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    def _find_working_audio(self) -> str | None:
        """Returns audio card name if tinymix responds, else None."""
        result = self._adb_raw(["shell", "cat /proc/asound/cards"], timeout=5)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        lines = result.stdout.strip().splitlines()
        if not lines or "no soundcards" in result.stdout.lower():
            return None

        # Prefer non-zero card index (external USB audio over internal)
        card_index = None
        card_name = None
        for line in lines:
            parts = line.split()
            if parts and parts[0].isdigit():
                idx = int(parts[0])
                if idx > 0:
                    card_index = idx
                    card_name = " ".join(parts[2:]) if len(parts) > 2 else f"card{idx}"
                    break
                elif card_index is None:
                    card_index = idx
                    card_name = " ".join(parts[2:]) if len(parts) > 2 else f"card{idx}"

        if card_index is None:
            return None

        result = self._adb_raw(["shell", f"tinymix -D {card_index} -a"], timeout=8)
        if result.returncode == 0 and result.stdout.strip():
            return card_name
        return None

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

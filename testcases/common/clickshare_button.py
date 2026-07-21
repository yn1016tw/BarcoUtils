"""
ClickShareButton — ADB wrapper for the ClickShare Button (Gen5), for simulating
physical short/long presses via the button's on-device g5configcli tool.

Requires `adb` in PATH. Gen5 only — Gen4 buttons have no equivalent mechanism.

Author: James Yang <james.yang@barco.com>
"""

import subprocess
import time


class ClickShareButton:
    SHORT_PRESS_DURATION = 0.2  # seconds
    LONG_PRESS_DURATION = 3     # seconds

    def __init__(self, serial: str, is_ip: bool):
        self._serial = serial  # e.g. "ABC123" or "192.168.1.100:5555"
        self._is_ip = is_ip

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

    def disconnect(self) -> None:
        if self._is_ip:
            subprocess.run(["adb", "disconnect", self._serial], capture_output=True, timeout=5)

    # ------------------------------------------------------------------
    # Press simulation
    # ------------------------------------------------------------------

    def press(self, long_press: bool = False, timeout: float | None = None) -> None:
        """Simulate a short (0.2s) or long (3s) press. `timeout` overrides the hold duration."""
        if timeout is not None:
            sleep_time = timeout
        elif long_press:
            sleep_time = self.LONG_PRESS_DURATION
        else:
            sleep_time = self.SHORT_PRESS_DURATION

        self._set_g5config_value("button.press", "ringButton.pressed")
        time.sleep(sleep_time)
        self._set_g5config_value("button.press", "ringButton.released")

    def _set_g5config_value(self, key: str, value: str, value_type: str = "string") -> None:
        self._adb(["shell", "g5configcli", "-E", "-s", key, "-t", value_type, "-v", value], timeout=10)

    # ------------------------------------------------------------------
    # ADB helpers
    # ------------------------------------------------------------------

    def _adb(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        result = self._adb_raw(args, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def _adb_raw(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        prefix = ["-s", self._serial] if self._serial else []
        cmd = ["adb"] + prefix + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

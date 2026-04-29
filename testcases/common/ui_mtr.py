"""
MtrUi — ADB-based UI controller for Microsoft Teams Rooms on Duvel.

Provides tap/swipe/key input, uiautomator-based element finding, screenshot
capture, app lifecycle control, and MTR-specific helpers.

Requires `adb` in PATH and an already-connected device (USB or TCP/IP).

Usage:
    from common.ui_mtr import MtrUi
    ui = MtrUi(serial="192.168.1.100:5555")
    ui.launch_teams()
    ui.wait_for_element(timeout=15, text="Join")
    ui.tap_element(text="Join")
    ui.screenshot("logs/screen.png")
"""

from __future__ import annotations

import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.ui_main import MainPage
    from common.ui_invite_people import InvitePeoplePage
    from common.ui_in_call import InCallPage
    from common.ui_more_menu import MoreMenuPage
    from common.ui_settings import SettingsPage
    from common.ui_device_settings import DeviceSettingsPage

_MTR_PACKAGE = "com.microsoft.skype.teams.ipphone"
_POLL_INTERVAL = 1  # seconds between element polls
_UI_DUMP_REMOTE = "/data/local/tmp/ui_dump.xml"

# Android keycodes
KEY_HOME     = 3
KEY_BACK     = 4
KEY_RECENT   = 187
KEY_ENTER    = 66
KEY_DPAD_UP    = 19
KEY_DPAD_DOWN  = 20
KEY_DPAD_LEFT  = 21
KEY_DPAD_RIGHT = 22
KEY_DPAD_CENTER = 23
KEY_VOLUME_UP   = 24
KEY_VOLUME_DOWN = 25


class MtrUi:
    def __init__(self, serial: str):
        self._serial = serial  # e.g. "ABC123" or "192.168.1.100:5555"
        self._main = None           # lazily created by .main property
        self._invite_people = None  # lazily created by .invite_people property
        self._in_call = None        # lazily created by .in_call property
        self._more_menu = None      # lazily created by .more_menu property
        self._settings = None         # lazily created by .settings property
        self._device_settings = None  # lazily created by .device_settings property

    @property
    def main(self) -> "MainPage":
        """Return the MainPage page object for this device (created on first access)."""
        if self._main is None:
            from common.ui_main import MainPage
            self._main = MainPage(self)
        return self._main

    @property
    def invite_people(self) -> "InvitePeoplePage":
        """Return the InvitePeoplePage page object (created on first access)."""
        if self._invite_people is None:
            from common.ui_invite_people import InvitePeoplePage
            self._invite_people = InvitePeoplePage(self)
        return self._invite_people

    @property
    def in_call(self) -> "InCallPage":
        """Return the InCallPage page object (created on first access)."""
        if self._in_call is None:
            from common.ui_in_call import InCallPage
            self._in_call = InCallPage(self)
        return self._in_call

    @property
    def more_menu(self) -> "MoreMenuPage":
        """Return the MoreMenuPage page object (created on first access)."""
        if self._more_menu is None:
            from common.ui_more_menu import MoreMenuPage
            self._more_menu = MoreMenuPage(self)
        return self._more_menu

    @property
    def settings(self) -> "SettingsPage":
        """Return the SettingsPage page object (created on first access)."""
        if self._settings is None:
            from common.ui_settings import SettingsPage
            self._settings = SettingsPage(self)
        return self._settings

    @property
    def device_settings(self) -> "DeviceSettingsPage":
        """Return the DeviceSettingsPage page object (created on first access)."""
        if self._device_settings is None:
            from common.ui_device_settings import DeviceSettingsPage
            self._device_settings = DeviceSettingsPage(self)
        return self._device_settings

    # ------------------------------------------------------------------
    # ADB transport (mirrors DuvelDevice pattern)
    # ------------------------------------------------------------------

    def _adb_raw(self, args: list, timeout: int = 10) -> subprocess.CompletedProcess:
        cmd = ["adb", "-s", self._serial] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def _adb(self, args: list, timeout: int = 10) -> subprocess.CompletedProcess:
        r = self._adb_raw(args, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"adb {' '.join(str(a) for a in args)} failed: {r.stderr.strip()}")
        return r

    def _adb_bytes(self, args: list, timeout: int = 10) -> bytes:
        cmd = ["adb", "-s", self._serial] + args
        return subprocess.run(cmd, capture_output=True, timeout=timeout).stdout

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def tap(self, x: int, y: int) -> None:
        self._adb(["shell", "input", "tap", str(x), str(y)])

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        self._adb(["shell", "input", "swipe",
                   str(x), str(y), str(x), str(y), str(duration_ms)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._adb(["shell", "input", "swipe",
                   str(x1), str(y1), str(x2), str(y2), str(duration_ms)])

    def keyevent(self, keycode: int | str) -> None:
        self._adb(["shell", "input", "keyevent", str(keycode)])

    def input_text(self, text: str) -> None:
        # ADB input text requires spaces as %s; other special chars passed through as-is
        self._adb(["shell", "input", "text", text.replace(" ", "%s")])

    # ------------------------------------------------------------------
    # Navigation shortcuts
    # ------------------------------------------------------------------

    def home(self) -> None:
        self.keyevent(KEY_HOME)

    def back(self) -> None:
        self.keyevent(KEY_BACK)

    def recent_apps(self) -> None:
        self.keyevent(KEY_RECENT)

    # ------------------------------------------------------------------
    # Screen capture
    # ------------------------------------------------------------------

    def screenshot(self, local_path: str) -> None:
        """Capture the screen and write a PNG to local_path."""
        data = self._adb_bytes(["exec-out", "screencap", "-p"], timeout=15)
        p = Path(local_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    # ------------------------------------------------------------------
    # UI hierarchy
    # ------------------------------------------------------------------

    def dump_ui(self) -> str:
        """Dump the current UI hierarchy and return raw XML, or '' if dump fails."""
        self._adb_raw(["shell", f"uiautomator dump {_UI_DUMP_REMOTE} >/dev/null 2>&1"], timeout=15)
        result = self._adb_raw(["shell", "cat", _UI_DUMP_REMOTE], timeout=10)
        self._adb_raw(["shell", "rm", "-f", _UI_DUMP_REMOTE], timeout=5)
        return result.stdout

    def find_element(
        self,
        text: str | None = None,
        text_contains: str | None = None,
        content_desc: str | None = None,
        resource_id: str | None = None,
        cls: str | None = None,
    ) -> dict | None:
        """Return the first node matching all supplied attributes, or None.

        Returned dict keys: text, content-desc, resource-id, class, bounds, center.
        center is an (x, y) tuple suitable for tap(); None if bounds are missing.
        """
        try:
            root = ET.fromstring(self.dump_ui())
        except ET.ParseError:
            return None

        for node in root.iter("node"):
            if text is not None and node.get("text") != text:
                continue
            if text_contains is not None and text_contains not in (node.get("text") or ""):
                continue
            if content_desc is not None and node.get("content-desc") != content_desc:
                continue
            if resource_id is not None and node.get("resource-id") != resource_id:
                continue
            if cls is not None and node.get("class") != cls:
                continue
            return {
                "text":         node.get("text"),
                "content-desc": node.get("content-desc"),
                "resource-id":  node.get("resource-id"),
                "class":        node.get("class"),
                "bounds":       node.get("bounds", ""),
                "center":       _bounds_center(node.get("bounds", "")),
            }
        return None

    def tap_element(
        self,
        text: str | None = None,
        text_contains: str | None = None,
        content_desc: str | None = None,
        resource_id: str | None = None,
        cls: str | None = None,
    ) -> bool:
        """Find an element and tap its center. Returns True if found and tapped."""
        el = self.find_element(
            text=text, text_contains=text_contains,
            content_desc=content_desc, resource_id=resource_id, cls=cls,
        )
        if el and el["center"]:
            self.tap(*el["center"])
            return True
        return False

    def wait_for_element(
        self,
        timeout: int,
        text: str | None = None,
        text_contains: str | None = None,
        content_desc: str | None = None,
        resource_id: str | None = None,
        cls: str | None = None,
    ) -> bool:
        """Poll until the element appears. Returns True if found within timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.find_element(
                text=text, text_contains=text_contains,
                content_desc=content_desc, resource_id=resource_id, cls=cls,
            ):
                return True
            time.sleep(_POLL_INTERVAL)
        return False

    def wait_for_element_gone(
        self,
        timeout: int,
        text: str | None = None,
        text_contains: str | None = None,
        content_desc: str | None = None,
        resource_id: str | None = None,
        cls: str | None = None,
    ) -> bool:
        """Poll until the element disappears. Returns True if gone within timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.find_element(
                text=text, text_contains=text_contains,
                content_desc=content_desc, resource_id=resource_id, cls=cls,
            ):
                return True
            time.sleep(_POLL_INTERVAL)
        return False

    def current_activity(self) -> str:
        """Return 'package/activity' for the foreground window, or '' if unknown."""
        # Try activity manager first (reliable on AOSP/MTR devices)
        result = self._adb_raw(["shell", "dumpsys", "activity", "activities"], timeout=10)
        for line in result.stdout.splitlines():
            if "topResumedActivity" in line or "ResumedActivity" in line:
                # format: ActivityRecord{... package/activity} ...
                for token in line.split():
                    if "/" in token and "}" not in token:
                        return token.rstrip("}")
                    if "/" in token:
                        return token.rstrip("}")
        # Fallback: window manager
        result = self._adb_raw(["shell", "dumpsys", "window", "windows"], timeout=10)
        for line in result.stdout.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                candidate = line.rsplit(" ", 1)[-1].rstrip("}")
                if "/" in candidate:
                    return candidate
        return ""

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------

    def launch(self, package: str, activity: str | None = None) -> None:
        """Launch a package by LAUNCHER intent, or a specific activity if given."""
        if activity:
            self._adb(["shell", "am", "start", "-n", f"{package}/{activity}"], timeout=10)
        else:
            self._adb(["shell", "monkey", "-p", package,
                       "-c", "android.intent.category.LAUNCHER", "1"], timeout=10)

    def force_stop(self, package: str) -> None:
        self._adb(["shell", "am", "force-stop", package], timeout=10)

    # ------------------------------------------------------------------
    # MTR-specific helpers
    # ------------------------------------------------------------------

    def launch_teams(self) -> None:
        """Bring Microsoft Teams Rooms to the foreground."""
        self.launch(_MTR_PACKAGE)

    def is_teams_foreground(self) -> bool:
        return _MTR_PACKAGE in self.current_activity()

    def end_call(self) -> bool:
        """Tap the hang-up / leave button if visible. Returns True if found."""
        return self.in_call.hang_up()


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _bounds_center(bounds: str) -> tuple[int, int] | None:
    """Parse '[x1,y1][x2,y2]' → center (x, y), or None on error."""
    try:
        parts = bounds.replace("][", ",").strip("[]").split(",")
        x1, y1, x2, y2 = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    except (ValueError, IndexError):
        return None

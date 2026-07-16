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

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import subprocess
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.ui_main import MainPage
    from common.ui_invite_people import InvitePeoplePage
    from common.ui_in_call import InCallPage
    from common.ui_more_menu import MoreMenuPage
    from common.ui_settings import SettingsPage
    from common.ui_device_settings import DeviceSettingsPage
    from common.ui_norden_call import NordenCallPage
    from common.ui_join_with_id import JoinWithIdPage
    from common.ui_device_setup_wizard import DeviceSetupWizardPage
    from common.ui_device_setup_provider import SetupProviderPage
    from common.ui_device_setup_language import SetupLanguagePage
    from common.ui_device_setup_network import SetupNetworkPage
    from common.ui_device_setup_datetime import SetupDatetimePage
    from common.ui_device_setup_update import SetupUpdatePage
    from common.ui_device_setup_xms_cloud import SetupXmsCloudPage
    from common.ui_device_setup_admin_password import SetupAdminPasswordPage
    from common.ui_device_setup_confirm import SetupConfirmPage
    from common.ui_device_setup_terms import SetupTermsPage
    from common.ui_device_setup_privacy import SetupPrivacyPage
    from common.ui_device_setup_complete import SetupCompletePage
    from common.ui_teams_sign_in import TeamsSignInPage
    from common.ui_teams_sign_in_email import TeamsSignInEmailPage
    from common.ui_azure_auth_webview import AzureAuthWebViewPage
    from common.ui_clickshare_main import ClickShareMainPage

_MTR_PACKAGE = "com.microsoft.skype.teams.ipphone"
_POLL_INTERVAL = 1  # seconds between element polls
_UI_DUMP_REMOTE = "/data/local/tmp/ui_dump.xml"
_UI_CACHE_TTL = 0.5  # seconds; only active inside ui_dump_cache() context

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
        self._norden_call = None      # lazily created by .norden_call property
        self._join_with_id = None            # lazily created by .join_with_id property
        self._device_setup_wizard = None     # lazily created by .device_setup_wizard property
        self._setup_provider = None          # lazily created by .setup_provider property
        self._setup_language = None          # lazily created by .setup_language property
        self._setup_network = None           # lazily created by .setup_network property
        self._setup_datetime = None          # lazily created by .setup_datetime property
        self._setup_update = None            # lazily created by .setup_update property
        self._setup_xms_cloud = None         # lazily created by .setup_xms_cloud property
        self._setup_admin_password = None    # lazily created by .setup_admin_password property
        self._setup_confirm = None           # lazily created by .setup_confirm property
        self._setup_terms = None             # lazily created by .setup_terms property
        self._setup_privacy = None           # lazily created by .setup_privacy property
        self._setup_complete = None          # lazily created by .setup_complete property
        self._teams_sign_in = None           # lazily created by .teams_sign_in property
        self._teams_sign_in_email = None     # lazily created by .teams_sign_in_email property
        self._azure_auth_webview = None      # lazily created by .azure_auth_webview property
        self._clickshare_main = None         # lazily created by .clickshare_main property
        self._ui_cache_enabled: bool = False
        self._ui_cache_xml: str = ""
        self._ui_cache_ts: float = 0.0

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

    @property
    def norden_call(self) -> "NordenCallPage":
        """Return the NordenCallPage page object (created on first access)."""
        if self._norden_call is None:
            from common.ui_norden_call import NordenCallPage
            self._norden_call = NordenCallPage(self)
        return self._norden_call

    @property
    def join_with_id(self) -> "JoinWithIdPage":
        """Return the JoinWithIdPage page object (created on first access)."""
        if self._join_with_id is None:
            from common.ui_join_with_id import JoinWithIdPage
            self._join_with_id = JoinWithIdPage(self)
        return self._join_with_id

    @property
    def setup_xms_cloud(self) -> "SetupXmsCloudPage":
        """Return the SetupXmsCloudPage page object (created on first access)."""
        if self._setup_xms_cloud is None:
            from common.ui_device_setup_xms_cloud import SetupXmsCloudPage
            self._setup_xms_cloud = SetupXmsCloudPage(self)
        return self._setup_xms_cloud

    @property
    def setup_admin_password(self) -> "SetupAdminPasswordPage":
        """Return the SetupAdminPasswordPage page object (created on first access)."""
        if self._setup_admin_password is None:
            from common.ui_device_setup_admin_password import SetupAdminPasswordPage
            self._setup_admin_password = SetupAdminPasswordPage(self)
        return self._setup_admin_password

    @property
    def setup_confirm(self) -> "SetupConfirmPage":
        """Return the SetupConfirmPage page object (created on first access)."""
        if self._setup_confirm is None:
            from common.ui_device_setup_confirm import SetupConfirmPage
            self._setup_confirm = SetupConfirmPage(self)
        return self._setup_confirm

    @property
    def setup_terms(self) -> "SetupTermsPage":
        """Return the SetupTermsPage page object (created on first access)."""
        if self._setup_terms is None:
            from common.ui_device_setup_terms import SetupTermsPage
            self._setup_terms = SetupTermsPage(self)
        return self._setup_terms

    @property
    def setup_privacy(self) -> "SetupPrivacyPage":
        """Return the SetupPrivacyPage page object (created on first access)."""
        if self._setup_privacy is None:
            from common.ui_device_setup_privacy import SetupPrivacyPage
            self._setup_privacy = SetupPrivacyPage(self)
        return self._setup_privacy

    @property
    def setup_complete(self) -> "SetupCompletePage":
        """Return the SetupCompletePage page object (created on first access)."""
        if self._setup_complete is None:
            from common.ui_device_setup_complete import SetupCompletePage
            self._setup_complete = SetupCompletePage(self)
        return self._setup_complete

    @property
    def teams_sign_in(self) -> "TeamsSignInPage":
        """Return the TeamsSignInPage page object (created on first access)."""
        if self._teams_sign_in is None:
            from common.ui_teams_sign_in import TeamsSignInPage
            self._teams_sign_in = TeamsSignInPage(self)
        return self._teams_sign_in

    @property
    def teams_sign_in_email(self) -> "TeamsSignInEmailPage":
        """Return the TeamsSignInEmailPage page object (created on first access)."""
        if self._teams_sign_in_email is None:
            from common.ui_teams_sign_in_email import TeamsSignInEmailPage
            self._teams_sign_in_email = TeamsSignInEmailPage(self)
        return self._teams_sign_in_email

    @property
    def azure_auth_webview(self) -> "AzureAuthWebViewPage":
        """Return the AzureAuthWebViewPage page object (created on first access)."""
        if self._azure_auth_webview is None:
            from common.ui_azure_auth_webview import AzureAuthWebViewPage
            self._azure_auth_webview = AzureAuthWebViewPage(self)
        return self._azure_auth_webview

    @property
    def setup_update(self) -> "SetupUpdatePage":
        """Return the SetupUpdatePage page object (created on first access)."""
        if self._setup_update is None:
            from common.ui_device_setup_update import SetupUpdatePage
            self._setup_update = SetupUpdatePage(self)
        return self._setup_update

    @property
    def device_setup_wizard(self) -> "DeviceSetupWizardPage":
        """Return the DeviceSetupWizardPage page object (created on first access)."""
        if self._device_setup_wizard is None:
            from common.ui_device_setup_wizard import DeviceSetupWizardPage
            self._device_setup_wizard = DeviceSetupWizardPage(self)
        return self._device_setup_wizard

    @property
    def setup_provider(self) -> "SetupProviderPage":
        """Return the SetupProviderPage page object (created on first access)."""
        if self._setup_provider is None:
            from common.ui_device_setup_provider import SetupProviderPage
            self._setup_provider = SetupProviderPage(self)
        return self._setup_provider

    @property
    def setup_language(self) -> "SetupLanguagePage":
        """Return the SetupLanguagePage page object (created on first access)."""
        if self._setup_language is None:
            from common.ui_device_setup_language import SetupLanguagePage
            self._setup_language = SetupLanguagePage(self)
        return self._setup_language

    @property
    def setup_network(self) -> "SetupNetworkPage":
        """Return the SetupNetworkPage page object (created on first access)."""
        if self._setup_network is None:
            from common.ui_device_setup_network import SetupNetworkPage
            self._setup_network = SetupNetworkPage(self)
        return self._setup_network

    @property
    def setup_datetime(self) -> "SetupDatetimePage":
        """Return the SetupDatetimePage page object (created on first access)."""
        if self._setup_datetime is None:
            from common.ui_device_setup_datetime import SetupDatetimePage
            self._setup_datetime = SetupDatetimePage(self)
        return self._setup_datetime

    @property
    def clickshare_main(self) -> "ClickShareMainPage":
        """Return the ClickShareMainPage page object (created on first access)."""
        if self._clickshare_main is None:
            from common.ui_clickshare_main import ClickShareMainPage
            self._clickshare_main = ClickShareMainPage(self)
        return self._clickshare_main

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
        self.invalidate_ui_cache()

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        self._adb(["shell", "input", "swipe",
                   str(x), str(y), str(x), str(y), str(duration_ms)])
        self.invalidate_ui_cache()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._adb(["shell", "input", "swipe",
                   str(x1), str(y1), str(x2), str(y2), str(duration_ms)])
        self.invalidate_ui_cache()

    def keyevent(self, keycode: int | str) -> None:
        self._adb(["shell", "input", "keyevent", str(keycode)])
        self.invalidate_ui_cache()

    def input_text(self, text: str) -> None:
        # ADB input text requires spaces as %s; other special chars passed through as-is
        self._adb(["shell", "input", "text", text.replace(" ", "%s")])
        self.invalidate_ui_cache()

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
        if self._ui_cache_enabled:
            now = time.monotonic()
            if self._ui_cache_xml and (now - self._ui_cache_ts) < _UI_CACHE_TTL:
                return self._ui_cache_xml
        raw = self._adb_bytes(
            ["shell", f"uiautomator dump {_UI_DUMP_REMOTE} >/dev/null 2>&1"
             f" && cat {_UI_DUMP_REMOTE} && rm -f {_UI_DUMP_REMOTE}"],
            timeout=20,
        )
        xml = raw.decode("utf-8", errors="replace") if raw else ""
        if self._ui_cache_enabled:
            self._ui_cache_xml = xml
            self._ui_cache_ts = time.monotonic()
        return xml

    def invalidate_ui_cache(self) -> None:
        """Expire the UI cache immediately; called after any write operation."""
        self._ui_cache_ts = 0.0

    @contextmanager
    def ui_dump_cache(self):
        """Share a single dump_ui() result within each poll iteration.

        Use in setup_tool.py only:
            with ui.ui_dump_cache():
                while ...:
                    ...
        Cache is disabled and cleared on context exit.
        """
        self._ui_cache_enabled = True
        self._ui_cache_ts = 0.0
        try:
            yield
        finally:
            self._ui_cache_enabled = False
            self._ui_cache_xml = ""
            self._ui_cache_ts = 0.0

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

    def go_to_main_page(self, timeout: int = 15) -> bool:
        """Navigate to the Teams Rooms home screen from any state.

        Returns True if the home screen becomes visible within timeout seconds.
        Strategy:
          1. Already visible → return True immediately.
          2. In-call screen visible → hang_up(), then wait up to 5s.
          3. Press BACK up to 5 times (1s apart), checking after each press.
          4. Fallback: launch_teams() (monkey LAUNCHER intent) + wait.
        """
        if self.main.is_visible():
            return True

        if self.in_call.is_visible():
            self.in_call.hang_up()
            time.sleep(2)
            if self.main.is_visible(timeout=5):
                return True

        for _ in range(5):
            self.back()
            time.sleep(1)
            if self.main.is_visible():
                return True

        self.launch_teams()
        return self.main.is_visible(timeout=timeout)


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

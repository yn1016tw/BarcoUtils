"""
EdgeController — automates the Windows Microsoft Edge desktop application.

Requires:
    pip install pywinauto pywin32

Usage:
    from common.edge_desktop import EdgeController

    ctrl = EdgeController()
    ctrl.connect()                        # attach to running Edge, launch if not running
    ctrl.navigate("https://example.com")
    print(ctrl.get_title(), ctrl.get_url())
    ctrl.screenshot("C:/logs/edge.png")
    ctrl.new_tab("https://example.com")
    ctrl.close_tab()
    ctrl.close()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import subprocess
import time
from typing import Optional

try:
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    _PYWINAUTO = True
except ImportError:
    _PYWINAUTO = False

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_POLL_INTERVAL = 0.5


class EdgeController:
    """Automates the Windows Microsoft Edge desktop application (msedge.exe).

    Public API:
        connect(launch, timeout)        — attach to running Edge, launch if not running
        navigate(url, timeout)          — load a URL in the current tab
        get_title()                     — current tab window title
        get_url(timeout)                — current tab URL (via address bar)
        new_tab(url)                    — open a new tab, optionally navigate it
        close_tab()                     — close the current tab (Ctrl+W)
        close()                         — close the whole Edge window
        screenshot(path)                — save a screenshot of the Edge window
    """

    def __init__(self):
        if not _PYWINAUTO:
            raise ImportError("pywinauto is required: pip install pywinauto pywin32")
        self._app: Optional[Application] = None

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------

    @staticmethod
    def get_version() -> str | None:
        """Return the running Edge version (e.g. '126.0.2592.68'), or None.

        Reads FileVersion from the msedge.exe path — requires Edge to be
        running and psutil to be installed.
        """
        if not _PSUTIL:
            raise ImportError("psutil is required: pip install psutil")
        import win32api

        for proc in psutil.process_iter(["name", "exe"]):
            if proc.info["name"] == "msedge.exe" and proc.info["exe"]:
                try:
                    info = win32api.GetFileVersionInfo(proc.info["exe"], "\\")
                    ms, ls = info["FileVersionMS"], info["FileVersionLS"]
                    return "%d.%d.%d.%d" % (
                        ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF,
                    )
                except Exception:
                    continue
        return None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, launch: bool = True, timeout: int = 30) -> None:
        """Attach to the running Edge process (msedge).

        If Edge is not running and launch=True, starts it and waits.
        """
        deadline = time.time() + timeout
        while True:
            try:
                self._app = Application(backend="uia").connect(
                    path="msedge.exe", timeout=3
                )
                return
            except Exception:
                pass
            if not launch or time.time() > deadline:
                raise ConnectionError("Could not connect to Edge desktop application")
            subprocess.Popen(["cmd", "/c", "start", "msedge"], shell=False)
            time.sleep(3)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str, timeout: int = 15) -> bool:
        """Load a URL in the current tab via the address bar (Ctrl+L)."""
        win = self._main_window()
        try:
            win.set_focus()
        except Exception:
            pass
        send_keys("^l")
        time.sleep(0.3)
        send_keys(url.replace("%", "{%}"), with_spaces=True)
        send_keys("{ENTER}")
        return self._wait_for_title_change(timeout)

    def new_tab(self, url: str | None = None) -> bool:
        """Open a new tab (Ctrl+T), optionally navigating it to url."""
        win = self._main_window()
        try:
            win.set_focus()
        except Exception:
            pass
        send_keys("^t")
        time.sleep(0.5)
        if url:
            return self.navigate(url)
        return True

    def close_tab(self) -> bool:
        """Close the current tab (Ctrl+W)."""
        win = self._main_window()
        try:
            win.set_focus()
        except Exception:
            pass
        send_keys("^w")
        time.sleep(0.5)
        return True

    def close(self) -> None:
        """Close the whole Edge window."""
        try:
            self._main_window().close()
        except Exception:
            pass
        self._app = None

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def get_title(self) -> str | None:
        """Return the current tab/window title, or None."""
        try:
            return self._main_window().window_text()
        except Exception:
            return None

    def get_url(self, timeout: int = 5) -> str | None:
        """Return the current tab URL by reading the address bar (Ctrl+L, copy)."""
        win = self._main_window()
        try:
            win.set_focus()
        except Exception:
            pass
        try:
            addr = win.child_window(control_type="Edit", title_re=".*[Ss]earch or enter.*")
            if not addr.exists(timeout=timeout):
                addr = win.child_window(control_type="Edit")
            return addr.get_value() if hasattr(addr, "get_value") else addr.window_text()
        except Exception:
            return None

    def screenshot(self, path: str) -> bool:
        """Save a screenshot of the Edge window to path."""
        try:
            self._main_window().capture_as_image().save(path)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._app is None:
            self.connect()

    def _main_window(self):
        self._ensure_connected()
        return self._app.top_window()

    def _wait_for_title_change(self, timeout: int) -> bool:
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            title = self.get_title()
            if title and title != "New Tab" and title == last:
                return True
            last = title
            time.sleep(_POLL_INTERVAL)
        return last is not None

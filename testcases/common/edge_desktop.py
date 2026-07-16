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
            # msedge.exe spawns many helper processes (renderer/GPU/etc.) with
            # no window — connecting by path can attach to one of those, so
            # match the actual browser window by title/class instead.
            try:
                self._app = Application(backend="uia").connect(
                    title_re=".*Microsoft.*Edge.*", timeout=3
                )
                self._maximize()
                return
            except Exception:
                pass
            try:
                self._app = Application(backend="uia").connect(
                    class_name="Chrome_WidgetWin_1", timeout=3
                )
                if self._is_edge_app(self._app):
                    self._maximize()
                    return
                self._app = None
            except Exception:
                self._app = None
            if not launch or time.time() > deadline:
                raise ConnectionError("Could not connect to Edge desktop application")
            subprocess.Popen(["cmd", "/c", "start", "msedge"], shell=False)
            time.sleep(3)

    @staticmethod
    def _is_edge_app(app: "Application") -> bool:
        try:
            if not _PSUTIL:
                return True
            proc = psutil.Process(app.process)
            return proc.name().lower() == "msedge.exe"
        except Exception:
            return False

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

    def refresh(self, timeout: int = 15) -> bool:
        """Reload the current tab (F5)."""
        win = self._main_window()
        try:
            win.set_focus()
        except Exception:
            pass
        send_keys("{F5}")
        time.sleep(0.5)
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
        """Return the current tab URL by reading the address bar text.

        The address bar Edit control (automation_id "view_1021") shows the
        current URL directly in its window_text() — no Ctrl+L/copy needed.
        """
        win = self._main_window()
        try:
            addr = win.child_window(control_type="Edit", auto_id="view_1021")
            if addr.exists(timeout=timeout):
                return addr.window_text() or None
        except Exception:
            pass
        try:
            edits = win.descendants(control_type="Edit")
            for e in edits:
                text = e.window_text()
                if text:
                    return text
        except Exception:
            pass
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

    def _maximize(self) -> None:
        """Maximize the Edge window so page elements are at predictable
        coordinates/visible extents for UI Automation."""
        try:
            win = self._app.top_window()
            win.maximize()
        except Exception:
            pass

    def maximize(self) -> None:
        """Public wrapper to maximize the connected Edge window on demand."""
        self._ensure_connected()
        self._maximize()

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

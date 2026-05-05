"""
TeamsDesktopController — automates the Windows Teams desktop application.

Requires:
    pip install pywinauto pywin32

Usage:
    from common.teams_desktop import TeamsDesktopController

    ctrl = TeamsDesktopController()
    ctrl.connect()
    info = ctrl.create_meeting()   # dict: join_url, meeting_id, passcode
    ctrl.wait_for_incoming_call(timeout=60)
    ctrl.accept_call()
    ctrl.end_call()
"""

from __future__ import annotations

import re
import subprocess
import time
from typing import Optional

try:
    import win32api
    import win32clipboard
    import win32con
    _WIN32 = True
except ImportError:
    _WIN32 = False

try:
    from pywinauto import Application, Desktop
    from pywinauto.keyboard import send_keys
    _PYWINAUTO = True
except ImportError:
    _PYWINAUTO = False

_POLL_INTERVAL = 0.5

# Navigation buttons that appear on every Teams page — filtered out in dumps
_NAV_BUTTONS = frozenset([
    "Minimize", "Maximize", "Close", "Back", "Forward",
    "Settings and more", "Collapse app bar", "View more apps", "Apps",
])


# ---------------------------------------------------------------------------
# Clipboard helper
# ---------------------------------------------------------------------------

def _clipboard_text() -> str:
    if not _WIN32:
        return ""
    try:
        win32clipboard.OpenClipboard()
        try:
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) or ""
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return ""


def _clear_clipboard() -> None:
    if not _WIN32:
        return
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# TeamsDesktopController
# ---------------------------------------------------------------------------

class TeamsDesktopController:
    """Automates the Windows Teams desktop client (new Teams / ms-teams).

    Public API:
        connect()                       — attach to running Teams
        create_meeting()                — Calendar → Meet now → Start → Meeting info
                                          returns dict(join_url, meeting_id, passcode)
        wait_for_incoming_call(timeout) — poll for incoming call toast
        accept_call()                   — accept audio call
        accept_video_call()             — accept video call
        decline_call()                  — decline incoming call
        end_call()                      — hang up active call
        mute() / toggle_camera()        — in-call controls
    """

    def __init__(self):
        if not _PYWINAUTO:
            raise ImportError("pywinauto is required: pip install pywinauto pywin32")
        self._app: Optional[Application] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, launch: bool = True, timeout: int = 30) -> None:
        """Attach to the running Teams process (ms-teams).

        If Teams is not running and launch=True, starts it and waits.
        """
        deadline = time.time() + timeout
        while True:
            # Try connecting by window title (works even with multiple processes)
            try:
                self._app = Application(backend="uia").connect(
                    title_re=".*Microsoft Teams.*", timeout=3
                )
                return
            except Exception:
                pass
            # Try by process name
            for proc in ("ms-teams.exe", "Teams.exe", "msteams.exe"):
                try:
                    self._app = Application(backend="uia").connect(
                        path=proc, timeout=3
                    )
                    return
                except Exception:
                    pass
            if not launch or time.time() > deadline:
                raise ConnectionError("Could not connect to Teams desktop application")
            subprocess.Popen(["explorer", "msteams:"])
            time.sleep(3)

    # ------------------------------------------------------------------
    # Meeting creation  (Calendar → Meet now → start → get info)
    # ------------------------------------------------------------------

    def create_meeting(self, timeout: int = 30) -> dict:
        """Start an instant Meet Now meeting and return meeting info.

        Flow:
          1. Navigate to Calendar tab
          2. Click Meet now → Get a link to share (grabs URL)
          3. Click Start meeting → Join now (enter the call)
          4. More → Meeting info (read ID + passcode from panel)
          5. Click Copy join info for full clipboard backup

        Returns dict with keys: join_url, meeting_id, passcode (any may be '').
        """
        self._ensure_connected()

        # Step 1 — go to Calendar
        main = self._main_window()
        main.set_focus()
        time.sleep(0.5)
        self._click(main, "Calendar (Ctrl+7)", ctrl_type="Button")
        time.sleep(2)

        # Step 2 — click Meet now
        main = self._main_window()
        main.set_focus()
        time.sleep(0.3)
        self._click(main, "Meet now", ctrl_type="Button")
        time.sleep(2)

        # Step 3 — grab link before entering meeting
        _clear_clipboard()
        main = self._main_window()
        main.set_focus()
        self._click(main, "Get a link to share", ctrl_type="Button")
        time.sleep(1.5)
        self._click(main, "Copy link", ctrl_type="Button")
        time.sleep(1)
        join_url = _clipboard_text()
        if "teams" not in join_url.lower():
            join_url = ""

        # Step 4 — start meeting
        main = self._main_window()
        main.set_focus()
        self._click(main, "Start meeting", ctrl_type="Button")
        time.sleep(4)

        # Step 5 — join now (pre-join screen)
        call_win = self._wait_for_call_window(timeout=15)
        if call_win is None:
            raise RuntimeError("Meeting call window did not appear")

        # Retry clicking Join now until Leave button confirms we are in the call
        deadline = time.time() + 25
        while time.time() < deadline:
            call_win = self._call_window()
            if call_win is None:
                time.sleep(1)
                continue
            if self._click_exists(call_win, "Leave"):
                break  # already in the call
            call_win.set_focus()
            time.sleep(0.5)
            self._click(call_win, "Join now", ctrl_type="Button")
            time.sleep(3)
        else:
            raise RuntimeError("Timed out waiting to join the meeting")

        # Wait for in-call controls to fully settle
        time.sleep(2)

        # Step 6 — open More → Meeting info panel
        call_win = self._call_window()
        info = self._open_meeting_info(call_win)
        info["join_url"] = info.get("join_url") or join_url
        return info

    def _open_meeting_info(self, call_win, timeout: int = 10) -> dict:
        """Open More → Meeting info panel and read ID + passcode."""
        # Click More
        self._click(call_win, "More", ctrl_type="Button")
        time.sleep(1.5)

        # Click Meeting info (CheckBox in the More menu)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                mi = call_win.child_window(title="Meeting info", control_type="CheckBox")
                if mi.exists():
                    mi.click_input()
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Could not find 'Meeting info' in More menu")

        time.sleep(1.5)

        # Read Meeting ID and Passcode from the panel text elements
        meeting_id = ""
        passcode = ""
        join_url = ""

        texts = []
        for el in call_win.descendants(control_type="Text"):
            try:
                t = el.window_text().strip()
                if t:
                    texts.append(t)
            except Exception:
                pass

        for i, t in enumerate(texts):
            if t == "Meeting ID:" and i + 1 < len(texts):
                meeting_id = texts[i + 1].strip()
            elif t == "Passcode:" and i + 1 < len(texts):
                passcode = texts[i + 1].strip()

        # Fallback: regex on concatenated text
        if not meeting_id:
            all_text = " ".join(texts)
            m = re.search(r"Meeting ID[:\s]+([0-9 ]{6,})", all_text)
            if m:
                meeting_id = m.group(1).strip()

        if not passcode:
            all_text = " ".join(texts)
            m = re.search(r"Passcode[:\s]+(\S+)", all_text)
            if m:
                passcode = m.group(1).strip()

        # Click Copy join info for URL backup
        try:
            _clear_clipboard()
            self._click(call_win, "Copy join info", ctrl_type="Button")
            time.sleep(0.8)
            clip = _clipboard_text()
            if clip:
                m = re.search(r"https?://[^\s]+", clip)
                if m:
                    join_url = m.group(0).rstrip(".")
        except Exception:
            pass

        return {"meeting_id": meeting_id, "passcode": passcode, "join_url": join_url}

    # ------------------------------------------------------------------
    # Incoming call
    # ------------------------------------------------------------------

    def wait_for_incoming_call(self, timeout: int = 60) -> bool:
        """Block until an incoming call toast appears. Returns True if found."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._incoming_call_window() is not None:
                return True
            time.sleep(_POLL_INTERVAL)
        return False

    def get_caller_name(self) -> str:
        """Return caller name from the incoming call toast, or ''."""
        w = self._incoming_call_window()
        if w is None:
            return ""
        try:
            title = w.window_text() or ""
            m = re.match(r"^(.+?)\s+(is calling|is video calling)", title, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return ""

    def accept_call(self) -> bool:
        """Accept the incoming call, or Admit from lobby. Returns True on success."""
        # Lobby popup buttons (Admit/Deny) are rendered in WebView2 and not accessible
        # via UIA — use coordinate-based clicking instead.
        if self._click_lobby_button("admit"):
            return True
        return self._click_on_incoming([
            "Accept", "Accept audio call", "Accept call", "Answer", "Audio",
        ])

    def accept_video_call(self) -> bool:
        """Accept the incoming video call, or Admit from lobby. Returns True on success."""
        if self._click_lobby_button("admit"):
            return True
        return self._click_on_incoming([
            "Accept video", "Video", "Accept with video", "Accept video call",
        ])

    def decline_call(self) -> bool:
        """Decline the incoming call, or Deny from lobby. Returns True on success."""
        if self._click_lobby_button("deny"):
            return True
        return self._click_on_incoming(["Decline", "Reject", "Decline call"])

    # ------------------------------------------------------------------
    # Active call controls
    # ------------------------------------------------------------------

    def end_call(self) -> bool:
        """Hang up the active call. Returns True on success."""
        self._ensure_connected()
        call_win = self._call_window()
        if call_win is None:
            return False
        for label in ("Leave", "Hang up", "End call", "Hang Up"):
            if self._click(call_win, label, ctrl_type="Button"):
                return True
        return False

    def mute(self) -> bool:
        """Toggle microphone mute. Returns True on success."""
        call_win = self._call_window()
        if call_win is None:
            return False
        for label in ("Mute", "Unmute", "Unmute mic", "Mute mic"):
            if self._click(call_win, label, ctrl_type="Button"):
                return True
        return False

    def toggle_camera(self) -> bool:
        """Toggle camera on/off. Returns True on success."""
        call_win = self._call_window()
        if call_win is None:
            return False
        for label in ("Turn camera off", "Turn camera on"):
            if self._click(call_win, label, ctrl_type="Button"):
                return True
        return False

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._app is None:
            raise RuntimeError("Not connected — call connect() first")

    def _main_window(self):
        """Return the main Teams navigation window (Calendar, Chat, etc.).

        Must use Application.connect()-based lookup so pywinauto can fully
        traverse the WebView2 accessibility tree inside the Teams process.
        Desktop().windows() returns raw handles that lack this traversal.

        If Teams is minimised to the system tray (hidden), the window won't be
        found by title — we restore it via the msteams: URI and retry once.
        """
        result = self._find_main_window()
        if result is not None:
            return result

        # Teams is likely hidden in the system tray — restore it and retry
        print("[teams] Main window not found — restoring Teams from tray...")
        subprocess.Popen(["explorer", "msteams:"])
        time.sleep(3)

        result = self._find_main_window()
        if result is not None:
            return result

        raise RuntimeError("Could not find main Teams window")

    def _find_main_window(self):
        """Try to locate the main Teams nav window. Returns window or None."""
        _non_call_patterns = [
            r"Calendar \|.*Microsoft Teams",
            r"Chat \|.*Microsoft Teams",
            r"Activity \|.*Microsoft Teams",
            r".*\|.*Microsoft Teams",   # any page | Microsoft Teams
        ]
        for pattern in _non_call_patterns:
            try:
                app = Application(backend="uia").connect(title_re=pattern, timeout=3)
                return app.window(title_re=pattern)
            except Exception:
                pass
        # Fallback: connect by process (covers hidden windows) and pick first non-call window
        for visible_only in (True, False):
            try:
                app = Application(backend="uia").connect(path="ms-teams.exe", timeout=3)
                for w in app.windows(visible_only=visible_only):
                    try:
                        t = w.window_text() or ""
                        if "Microsoft Teams" in t and "Microsoft Teams meeting" not in t:
                            return w
                    except Exception:
                        pass
            except Exception:
                pass
        return None

    def _call_window(self):
        """Return the active call/meeting window, or None.

        Uses Application.connect() so the returned wrapper can traverse
        the WebView2 accessibility tree inside Teams.
        """
        _call_patterns = [
            r"Microsoft Teams meeting \| Microsoft Teams",
            r"Meeting with.*\| Microsoft Teams",
        ]
        for pattern in _call_patterns:
            try:
                app = Application(backend="uia").connect(title_re=pattern, timeout=2)
                w = app.window(title_re=pattern)
                if w.exists():
                    return w
            except Exception:
                pass
        return None

    def _wait_for_call_window(self, timeout: int = 15):
        """Poll until the call window appears. Returns the window or None."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            w = self._call_window()
            if w is not None:
                return w
            time.sleep(0.5)
        return None

    _ACCEPT_LABELS = ("Accept", "Accept audio call", "Accept call", "Answer", "Audio")
    _DECLINE_LABELS = ("Decline", "Reject", "Decline call")

    def _lobby_group(self):
        """Return the 'Waiting in the lobby' popup Group element inside the call window, or None.

        The Admit/Deny buttons inside this popup are rendered in WebView2 and are not
        exposed via UIA — use _click_lobby_button() for coordinate-based clicking.
        """
        call_win = self._call_window()
        if call_win is None:
            return None
        for el in call_win.descendants(control_type="Group"):
            try:
                rect = el.rectangle()
                # Lobby popup is roughly 280-420 px wide and 70-180 px tall
                if not (250 < rect.width() < 450 and 60 < rect.height() < 200):
                    continue
                # Confirm it contains lobby-related text
                for text_el in el.descendants(control_type="Text"):
                    try:
                        if "lobby" in (text_el.window_text() or "").lower():
                            return el
                    except Exception:
                        pass
            except Exception:
                pass
        return None

    # Admit/Deny button positions relative to the lobby popup Group bounding rect.
    # Calibrated from live Teams UI: Admit is the right blue button, Deny is left white.
    _LOBBY_ADMIT_X_FRAC = 0.73
    _LOBBY_DENY_X_FRAC  = 0.40
    _LOBBY_BTN_Y_FRAC   = 0.82   # buttons are near the bottom of the popup

    def _click_lobby_button(self, action: str = "admit") -> bool:
        """Click Admit or Deny in the lobby popup via coordinate-based mouse click.

        The Admit/Deny buttons are not accessible via UIA (WebView2 rendering), so
        we calculate their screen position from the popup Group's bounding rectangle.

        Returns True if the lobby popup was found and the click was sent.
        """
        call_win = self._call_window()
        group = self._lobby_group()
        if group is None or call_win is None:
            return False

        call_win.set_focus()
        time.sleep(0.5)

        x_frac = self._LOBBY_ADMIT_X_FRAC if action == "admit" else self._LOBBY_DENY_X_FRAC

        def _do_click(grp) -> None:
            rect = grp.rectangle()
            rel_x = int(rect.width() * x_frac)
            rel_y = int(rect.height() * self._LOBBY_BTN_Y_FRAC)
            grp.click_input(coords=(rel_x, rel_y))

        try:
            _do_click(group)
        except Exception:
            # SetCursorPos can fail transiently (window animation / focus change).
            # Re-read the lobby element and retry once after a short pause.
            time.sleep(0.5)
            group = self._lobby_group()
            if group is None:
                return True  # popup already gone — admitted concurrently
            _do_click(group)

        return True

    def _incoming_call_window(self):
        """Return the window containing an incoming call or lobby request, or None.

        Handles two scenarios:
          1. Incoming call toast — separate window whose title contains 'is calling'
          2. Lobby request ('Waiting in the lobby') — popup inside the active call window;
             buttons are in WebView2 (not UIA-accessible), detected via _lobby_group()
        """
        # Scenario 2: lobby popup inside active call window (most common with MTR devices)
        if self._lobby_group() is not None:
            return self._call_window()

        # Scenario 1: classic incoming call toast or in-app notification with UIA buttons
        _all_labels = self._ACCEPT_LABELS + self._DECLINE_LABELS
        try:
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    title = w.window_text() or ""
                    if re.search(r"(is calling|Incoming call|incoming video)", title, re.IGNORECASE):
                        return w
                    if re.search(r"teams", title, re.IGNORECASE):
                        for label in _all_labels:
                            try:
                                btn = w.child_window(title=label, control_type="Button")
                                if btn.exists(timeout=0.3):
                                    return w
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback: main window in-app notification banner
        try:
            main = self._main_window()
            for label in _all_labels:
                try:
                    btn = main.child_window(title=label, control_type="Button")
                    if btn.exists():
                        return main
                except Exception:
                    pass
        except Exception:
            pass

        return None

    def dump_incoming_call_info(self) -> None:
        """Print all visible window titles and Teams button names — call this when a call
        arrives and auto-accept is not working, to find the correct button/title strings."""
        print("[dump] Scanning all desktop windows...")
        try:
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    title = w.window_text() or "(no title)"
                    print(f"  window: {title!r}")
                    if re.search(r"teams|calling|incoming", title, re.IGNORECASE):
                        for btn in w.descendants(control_type="Button"):
                            try:
                                print(f"    button: {btn.window_text()!r}")
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception as e:
            print(f"  [dump error] {e}")

    def _click_on_incoming(self, labels: list[str]) -> bool:
        w = self._incoming_call_window()
        if w is None:
            return False
        for label in labels:
            if self._click(w, label, ctrl_type="Button"):
                return True
        return False

    # ------------------------------------------------------------------
    # Generic click helper
    # ------------------------------------------------------------------

    @staticmethod
    def _click(parent, title: str, ctrl_type: str = "Button") -> bool:
        """Click the first child matching title (exact then regex). Returns True on success."""
        for use_regex in (False, True):
            try:
                kwargs = (
                    {"title_re": f".*{re.escape(title)}.*", "control_type": ctrl_type}
                    if use_regex
                    else {"title": title, "control_type": ctrl_type}
                )
                el = parent.child_window(**kwargs)
                if el.exists():
                    el.click_input()
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _click_exists(parent, title: str, ctrl_type: str = "Button") -> bool:
        """Return True if a child with the given title exists (does not click)."""
        for use_regex in (False, True):
            try:
                kwargs = (
                    {"title_re": f".*{re.escape(title)}.*", "control_type": ctrl_type}
                    if use_regex
                    else {"title": title, "control_type": ctrl_type}
                )
                el = parent.child_window(**kwargs)
                if el.exists():
                    return True
            except Exception:
                pass
        return False

    # keep old name for backwards compat
    @staticmethod
    def _find_button(parent, title: str):
        for use_regex in (False, True):
            try:
                kwargs = (
                    {"title_re": f".*{re.escape(title)}.*", "control_type": "Button"}
                    if use_regex
                    else {"title": title, "control_type": "Button"}
                )
                btn = parent.child_window(**kwargs)
                if btn.exists():
                    return btn
            except Exception:
                pass
        return None

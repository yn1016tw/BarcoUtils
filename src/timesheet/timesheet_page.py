"""
TimesheetPage — automates the SAP Fiori "My Timesheet" page inside an
already-open Windows Edge browser window, using EdgeController (pywinauto /
UI Automation). No DOM access — this drives the page purely through the
accessibility tree, the same way a sighted user would click through it.

⚠️ This operates on your REAL SAP account. fill_day()/autofill_day() write
real timesheet entries and submit() saves them — there is no dry-run mode.
Always verify with a screenshot before calling submit() in new scenarios.

Usage:
    from datetime import date
    import sys
    sys.path.insert(0, r"C:\\Project\\BarcoUtils\\testcases")
    from common.edge_desktop import EdgeController
    from timesheet_page import TimesheetPage

    ctrl = EdgeController()
    ctrl.connect()
    ts = TimesheetPage(ctrl)
    ts.open()                                    # navigate + wait for load, auto-refresh on login pages
    ts.autofill_day(date(2026, 7, 20), "Duvel", 8.0)

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "testcases"))
from common.edge_desktop import EdgeController  # noqa: E402

try:
    from pywinauto.keyboard import send_keys
except ImportError:
    send_keys = None  # EdgeController import above already validates pywinauto is present


SAP_URL_DEFAULT = (
    "https://core.barco.com/sap/bc/ui2/flp?sap-client=100&sap-language=EN#TimeEntry-manageTimesheet"
)

# Browser tab titles shown when the SAP session is not (yet) authenticated —
# either SAP's own ABAP "Logon" page or a Microsoft SSO sign-in step.
_LOGIN_TITLE_MARKERS = (
    "logon",
    "sign in",
    "pick an account",
    "enter password",
    "stay signed in",
    "verify your identity",
    "approve sign in",
    "help us protect your account",
)

_MAX_REFRESH_RETRIES = 10
_REFRESH_INTERVAL_S = 10
_INITIAL_LOAD_WAIT_S = 8

# Full date row label as SAP renders it, e.g. "Monday, July 20, 2026"
_DATE_ROW_RE = re.compile(r"^[A-Za-z]+, [A-Za-z]+ \d{1,2}, \d{4}$")


class LoginPageError(Exception):
    """Raised when a login page is still shown after all refresh retries."""


class TimesheetPage:
    """Automates the SAP Fiori 'My Timesheet' app via UI Automation on a real Edge window.

    Public API:
        open()                                     — navigate + wait for load (auto-refresh on login pages)
        go_to_week(target_date)                     — select the week containing target_date
        enter_edit_mode()                           — reveal editable Assignment/Hours controls
        row_status(target_date)                     — dict describing the current row (recorded/target/assignment/status)
        fill_day(target_date, assignment, hours)    — set Assignment + Hours for one row (edit mode must be active)
        submit()                                    — save entered records
        cancel()                                    — discard unsaved edits, exit edit mode
        autofill_day(target_date, assignment, hours, skip_if_filled=True) — full single-day flow
    """

    def __init__(self, ctrl: EdgeController, url: str = SAP_URL_DEFAULT):
        self.ctrl = ctrl
        self.url = url

    # ------------------------------------------------------------------
    # Load / login handling
    # ------------------------------------------------------------------
    @staticmethod
    def _is_login_page(title: str) -> bool:
        t = (title or "").lower()
        return any(marker in t for marker in _LOGIN_TITLE_MARKERS)

    def open(self) -> str:
        """Navigate to the timesheet URL and wait for it to finish loading.

        If SAP's own Logon page or a Microsoft sign-in page is shown instead
        (expired session), refresh (F5) and retry up to _MAX_REFRESH_RETRIES
        times. Returns the final page title; raises LoginPageError if still
        stuck on a login page after all retries.
        """
        self.ctrl.navigate(self.url, timeout=30)
        time.sleep(_INITIAL_LOAD_WAIT_S)

        for _attempt in range(1, _MAX_REFRESH_RETRIES + 1):
            title = self.ctrl.get_title() or ""
            if not self._is_login_page(title):
                return title
            self.ctrl.refresh(timeout=30)
            time.sleep(_REFRESH_INTERVAL_S)

        title = self.ctrl.get_title() or ""
        if self._is_login_page(title):
            raise LoginPageError(
                f"Timesheet failed to load after {_MAX_REFRESH_RETRIES} reload(s) "
                f"— still on login page ('{title}')."
            )
        return title

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _win(self):
        return self.ctrl._main_window()

    def _focus_window(self):
        """Bring the Edge window to the foreground.

        Confirmed via live testing that skipping this can cause clicks to
        land on whatever window happens to overlap the target screen
        coordinates (e.g. another visible app) instead of the Edge page.
        """
        try:
            self._win().set_focus()
            time.sleep(0.3)
        except Exception:
            pass

    def _find(self, title: str, control_type: Optional[str] = None) -> list:
        win = self._win()
        kwargs = {"title": title}
        if control_type:
            kwargs["control_type"] = control_type
        try:
            return win.descendants(**kwargs)
        except Exception:
            return []

    @staticmethod
    def _invoke(el) -> bool:
        """Trigger a control via the UIA Invoke pattern (works even if the
        element is currently scrolled out of view); falls back to a
        coordinate click if Invoke isn't supported."""
        try:
            el.invoke()
            return True
        except Exception:
            try:
                el.set_focus()
            except Exception:
                pass
            try:
                el.click_input()
                return True
            except Exception:
                return False

    def _visible_date_rows(self) -> list:
        """Ordered, de-duplicated list of visible full date row labels
        (e.g. 'Monday, July 20, 2026'), matching the table's top-to-bottom order."""
        win = self._win()
        labels = []
        for e in win.descendants(control_type="DataItem"):
            try:
                name = e.window_text()
            except Exception:
                continue
            if name and _DATE_ROW_RE.match(name) and name not in labels:
                labels.append(name)
        return labels

    @staticmethod
    def _row_label(target_date: date) -> str:
        return (
            f"{target_date.strftime('%A')}, {target_date.strftime('%B')} "
            f"{target_date.day}, {target_date.year}"
        )

    # ------------------------------------------------------------------
    # Navigation within the timesheet
    # ------------------------------------------------------------------
    def go_to_week(self, target_date: date, retries: int = 8) -> bool:
        """Click the mini-calendar cell for target_date to load its week into the table.

        Retries since the calendar may not be fully rendered yet immediately
        after open()/navigation completes — on a cold page load the mini
        calendar widget can take noticeably longer to render than the tab
        title takes to stabilize.
        """
        self._focus_window()
        label = f"{target_date.strftime('%B')} {target_date.day}, {target_date.year}"
        for attempt in range(retries):
            cells = self._find(label)
            if cells:
                self._invoke(cells[-1])
                time.sleep(2)
                return True
            time.sleep(1.5)
        return False

    def enter_edit_mode(self) -> bool:
        """Click 'Enter Records' to reveal editable Assignment/Hours controls for the visible week."""
        self._focus_window()
        btns = self._find("Enter Records", control_type="Button")
        if not btns:
            return False
        self._invoke(btns[-1])
        time.sleep(2)
        return True

    # ------------------------------------------------------------------
    # Reading row state
    # ------------------------------------------------------------------
    def row_status(self, target_date: date) -> dict | None:
        """Return {'recorded': float, 'target': float, 'assignment': str, 'status': str}
        for target_date's row, or None if the row isn't currently visible
        (call go_to_week() first)."""
        win = self._win()
        label = self._row_label(target_date)
        rows = self._visible_date_rows()
        if label not in rows:
            return None
        idx = rows.index(label)

        # SAP renders both a short DataItem ("0,00 / 8,00 Object Status") and a
        # longer combined one for the same row ("0,00 / 8,00 Object Status
        # Assignment Entered 0 Hours ... Attributes :") — both start with the
        # same ratio text, so anchor to the short form only or indices double up.
        recorded_items = [
            e for e in win.descendants(control_type="DataItem")
            if re.fullmatch(r"\d+,\d\d\s*/\s*\d+,\d\d\s*Object Status", e.window_text() or "")
        ]
        assignment_items = [
            e for e in win.descendants(control_type="DataItem")
            if (e.window_text() or "").startswith("Assignment ")
        ]
        status_items = [
            e for e in win.descendants(control_type="DataItem")
            if "Object Status" in (e.window_text() or "") and "/" not in (e.window_text() or "")
        ]

        def _parse_ratio(text: str) -> tuple:
            m = re.match(r"^(\d+,\d\d)\s*/\s*(\d+,\d\d)", text)
            if not m:
                return (0.0, 0.0)
            return (float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", ".")))

        recorded, target = (0.0, 0.0)
        if idx < len(recorded_items):
            recorded, target = _parse_ratio(recorded_items[idx].window_text() or "")
        assignment = ""
        if idx < len(assignment_items):
            assignment = (assignment_items[idx].window_text() or "").replace("Assignment", "", 1).strip()
        status = ""
        if idx < len(status_items):
            status = (status_items[idx].window_text() or "").replace("Object Status", "").strip()

        return {"recorded": recorded, "target": target, "assignment": assignment, "status": status}

    # ------------------------------------------------------------------
    # Filling a day
    # ------------------------------------------------------------------
    def fill_day(self, target_date: date, assignment: str, hours: float) -> bool:
        """Set the Assignment combo and Hours field for target_date's row.

        enter_edit_mode() must already have been called (and the correct
        week must be visible via go_to_week()) so the row's edit controls exist.
        """
        self._focus_window()
        win = self._win()
        rows = self._visible_date_rows()
        label = self._row_label(target_date)
        if label not in rows:
            return False
        idx = rows.index(label)

        combos = win.descendants(control_type="ComboBox")
        if idx >= len(combos):
            return False

        # Assignment combo — click, type, confirm with Enter
        combo = combos[idx]
        try:
            combo.set_focus()
        except Exception:
            pass
        combo.click_input()
        time.sleep(0.5)
        send_keys(assignment.replace(" ", "{SPACE}"))
        time.sleep(1.5)
        send_keys("{ENTER}")
        time.sleep(1)

        # Re-fetch the Spinner list — selecting the assignment re-renders the
        # row (adds an Attributes line), which invalidates any Spinner
        # element handle fetched before this point and causes clicks to land
        # on stale (shifted) coordinates.
        spinners = win.descendants(control_type="Spinner")
        if idx >= len(spinners):
            return False
        spinner = spinners[idx]
        try:
            spinner.set_focus()
        except Exception:
            pass
        spinner.click_input()
        time.sleep(0.3)

        # NOTE: confirmed via live testing that this SAP StepInput widget does
        # NOT accept direct digit/comma typing via synthetic keyboard events —
        # only Ctrl+A/Delete and Up/Down arrow keys actually change the value
        # (Up = +1.00 per press). So only whole-hour values are supported here.
        if hours != int(hours):
            raise ValueError(
                "TimesheetPage.fill_day only supports whole-hour values "
                f"(SAP's Hours field rejects typed digits, only arrow-key "
                f"increments of 1.0 work) — got {hours}."
            )
        send_keys("^a{DEL}")
        time.sleep(0.3)
        for _ in range(int(hours)):
            send_keys("{UP}")
            time.sleep(0.15)
        send_keys("{TAB}")
        time.sleep(0.5)
        return True

    # ------------------------------------------------------------------
    # Commit / discard
    # ------------------------------------------------------------------
    def submit(self) -> bool:
        """Click 'Submit' to save entered records."""
        self._focus_window()
        btns = self._find("Submit", control_type="Button")
        if not btns:
            return False
        self._invoke(btns[-1])
        time.sleep(3)
        return True

    def cancel(self) -> bool:
        """Click 'Cancel' to discard unsaved edits and exit edit mode."""
        self._focus_window()
        btns = self._find("Cancel", control_type="Button")
        if not btns:
            return False
        self._invoke(btns[-1])
        time.sleep(2)
        return True

    # ------------------------------------------------------------------
    # Convenience: full single-day flow
    # ------------------------------------------------------------------
    def autofill_day(
        self,
        target_date: date,
        assignment: str,
        hours: float,
        skip_if_filled: bool = True,
    ) -> str:
        """Navigate to target_date's week, enter edit mode, fill and submit.

        Returns one of: "filled", "skipped_already_filled", "row_not_found".
        If skip_if_filled is True (default) and the row already has recorded
        hours > 0 or an Approved/Sent For Approval status, no changes are
        made and "skipped_already_filled" is returned.
        """
        if not self.go_to_week(target_date):
            return "row_not_found"

        status = self.row_status(target_date)
        if status is None:
            return "row_not_found"

        if skip_if_filled and (
            status["recorded"] > 0
            or status["status"].lower() in ("approved", "sent for approval")
        ):
            return "skipped_already_filled"

        if not self.enter_edit_mode():
            return "row_not_found"

        if not self.fill_day(target_date, assignment, hours):
            self.cancel()
            return "row_not_found"

        self.submit()
        return "filled"

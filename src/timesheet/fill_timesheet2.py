"""
TimesSheet Auto-Fill Tool v2 — Edge UI Automation variant.

Navigates the already-running Windows Edge browser (via EdgeController /
UI Automation) to the SAP Fiori timesheet page, waits for it to finish
loading, and auto-refreshes (F5) if a Microsoft sign-in page is shown
instead (expired SAP session cookie).

Usage:
    python src/timesheet/fill_timesheet2.py
    python src/timesheet/fill_timesheet2.py --url "https://core.barco.com/..."
"""

import logging
import os
import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "testcases"))
from common.edge_desktop import EdgeController  # noqa: E402

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Logging — writes to log/fill_timesheet2.log (appended) and stdout
# ---------------------------------------------------------------------------
_LOG_DIR = Path(__file__).parent / "log"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "fill_timesheet2.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def _print(*args):
    """Drop-in for print() that also writes to the log file."""
    log.info(" ".join(str(a) for a in args))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SAP_URL = os.getenv(
    "SAP_URL",
    "https://core.barco.com/sap/bc/ui2/flp?sap-client=100&sap-language=EN#TimeEntry-manageTimesheet",
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


class LoginPageError(Exception):
    """Raised when the login page is still shown after all refresh retries."""


def is_login_page(title: str) -> bool:
    """Return True if the given browser tab title looks like a Microsoft sign-in page."""
    t = (title or "").lower()
    return any(marker in t for marker in _LOGIN_TITLE_MARKERS)


def wait_for_timesheet(ctrl: EdgeController, url: str = SAP_URL) -> str:
    """Navigate to the timesheet page and wait for it to finish loading.

    If a Microsoft login page is shown instead (expired SAP session cookie),
    refresh the page (F5) and retry up to _MAX_REFRESH_RETRIES times.

    Returns the final page title. Raises LoginPageError if still on the
    login page after all retries.
    """
    _print(f"Navigating to timesheet page: {url}")
    ctrl.navigate(url, timeout=30)
    time.sleep(_INITIAL_LOAD_WAIT_S)

    for attempt in range(1, _MAX_REFRESH_RETRIES + 1):
        title = ctrl.get_title() or ""
        if not is_login_page(title):
            _print(f"Timesheet loaded: {title}")
            return title
        _print(
            f"[{attempt}/{_MAX_REFRESH_RETRIES}] Login page detected ('{title}') — refreshing ..."
        )
        ctrl.refresh(timeout=30)
        time.sleep(_REFRESH_INTERVAL_S)

    title = ctrl.get_title() or ""
    if is_login_page(title):
        raise LoginPageError(
            f"Timesheet failed to load after {_MAX_REFRESH_RETRIES} reload(s) "
            f"— still on login page ('{title}')."
        )
    return title


@click.command()
@click.option("--url", default=None, help="Override the timesheet URL to navigate to.")
def main(url: str | None):
    target_url = url or SAP_URL
    ctrl = EdgeController()
    ctrl.connect()
    try:
        wait_for_timesheet(ctrl, target_url)
    except LoginPageError as e:
        _print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

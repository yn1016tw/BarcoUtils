"""
TimesSheet Auto-Fill Tool v2 — Edge UI Automation variant.

Uses EdgeController + TimesheetPage (pywinauto / UI Automation, no Playwright)
to navigate to the SAP Fiori timesheet page, auto-refresh through login pages,
fill and submit a single day's entry, and report the result to Telegram.

If the target date is already Approved / Sent For Approval, the fill is
skipped and Edge is closed immediately (no edit-mode is entered).

Usage:
    python src/timesheet/fill_timesheet2.py
    python src/timesheet/fill_timesheet2.py --date 2026-07-22
    python src/timesheet/fill_timesheet2.py --date 2026-07-22 --assignment Duvel --hours 8
    python src/timesheet/fill_timesheet2.py --skip
"""

import datetime
import logging
import os
import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "testcases"))
from common.edge_desktop import EdgeController  # noqa: E402
from timesheet_page import LoginPageError, TimesheetPage  # noqa: E402

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
DEFAULT_ASSIGNMENT = os.getenv("DEFAULT_ASSIGNMENT", "Duvel")
DEFAULT_HOURS = float(os.getenv("DEFAULT_HOURS", "8"))


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------
def send_telegram_result(message: str) -> None:
    """Send a text message to Telegram via Bot API (no-op if not configured)."""
    import json
    import urllib.request

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        _print("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing). Skipping.")
        return

    payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            _print(f"Telegram notification sent (HTTP {resp.status})")
    except Exception as e:
        _print(f"WARNING: Telegram notification failed: {e}")


@click.command()
@click.option("--date", "date_str", default=None, help="Date to fill (YYYY-MM-DD). Defaults to today.")
@click.option("--hours", default=None, type=float, help="Override hours.")
@click.option("--assignment", default=None, help="Override assignment.")
@click.option("--skip", is_flag=True, help="Exit without filling any entry.")
@click.option("--url", default=None, help="Override the timesheet URL to navigate to.")
def main(date_str, hours, assignment, skip, url):
    target_date = (
        datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    )
    target_assignment = assignment or DEFAULT_ASSIGNMENT
    target_hours = hours if hours is not None else DEFAULT_HOURS
    target_url = url or SAP_URL

    if skip:
        _print(f"Timesheet fill skipped (--skip): {target_date}")
        send_telegram_result(f"Timesheet skipped (--skip): {target_date}")
        return

    ctrl = EdgeController()
    ctrl.connect()
    ts = TimesheetPage(ctrl, url=target_url)

    try:
        ts.open()

        result = ts.autofill_day(target_date, target_assignment, target_hours)
        time.sleep(1)
        final_status = ts.row_status(target_date)
        _print(f"autofill_day result: {result}, row_status: {final_status}")

        if final_status:
            message = (
                f"Timesheet {result} for {target_date}: {final_status['recorded']}/"
                f"{final_status['target']} h, {final_status['assignment']}, "
                f"status={final_status['status']}"
            )
        else:
            message = f"Timesheet fill FAILED for {target_date}: result={result}"

        send_telegram_result(message)
    except LoginPageError as e:
        _print(f"ERROR: {e}")
        send_telegram_result(f"Timesheet fill FAILED for {target_date}: {e}")
        sys.exit(1)
    except Exception as e:
        _print(f"ERROR: {e}")
        send_telegram_result(f"Timesheet fill FAILED for {target_date}: {e}")
        raise
    finally:
        ctrl.close()


if __name__ == "__main__":
    main()

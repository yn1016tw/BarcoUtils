"""
TimesSheet Auto-Fill Tool v2 — Edge UI Automation variant.

Uses EdgeController + TimesheetPage (pywinauto / UI Automation, no Playwright)
to navigate to the SAP Fiori timesheet page, auto-refresh through login pages,
fill and submit a single day's entry (or backfill Monday..target_date), and
report the result for target_date to Telegram with an OK (✅) / FAIL (❌) icon,
attaching a screenshot of the Edge window at the time of reporting.
The message is OK when target_date was filled this run or was already
filled/approved before this run (skipped_already_filled); it's only
reported as FAIL when the row itself couldn't be located or an exception
was raised.

By default, every weekday from Monday of target_date's week up to and
including target_date is checked; any day that is not already Approved /
Sent For Approval is filled too (pass --no-backfill to only touch
target_date). Days already Approved / Sent For Approval / recorded are
skipped and Edge is closed without entering edit mode for them.

Usage:
    python src/timesheet/fill_timesheet2.py
    python src/timesheet/fill_timesheet2.py --date 2026-07-22
    python src/timesheet/fill_timesheet2.py --date 2026-07-22 --assignment Duvel --hours 8
    python src/timesheet/fill_timesheet2.py --date 2026-07-22 --no-backfill
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


def get_week_dates_to_fill(target_date: datetime.date) -> list:
    """Return weekdays (Mon–Fri) from Monday of target_date's week up to and
    including target_date — used for backfill mode."""
    monday = target_date - datetime.timedelta(days=target_date.weekday())
    dates = []
    current = monday
    while current <= target_date:
        if current.weekday() < 5:
            dates.append(current)
        current += datetime.timedelta(days=1)
    return dates


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------
def send_telegram_result(message: str, image_path: Path | None = None) -> None:
    """Send a text message (and optional photo) to Telegram via Bot API
    (no-op if not configured)."""
    import json
    import urllib.request

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        _print("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing). Skipping.")
        return

    base = f"https://api.telegram.org/bot{token}"

    if image_path and image_path.exists():
        with open(image_path, "rb") as f:
            img_data = f.read()
        boundary = "----TGBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{message}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="result.png"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{base}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
    else:
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(
            f"{base}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            _print(f"Telegram notification sent (HTTP {resp.status})")
    except Exception as e:
        _print(f"WARNING: Telegram notification failed: {e}")


def _build_ok_or_fail_message(target_date, result, status) -> str:
    """Build a short Telegram confirmation for target_date, prefixed with
    an OK/FAIL icon. Considered OK whenever the day ended up filled this run
    ("filled") or was already filled/approved before this run
    ("skipped_already_filled") — i.e. any outcome other than a failure to
    even locate the row ("row_not_found")."""
    status_text = (status or {}).get("status", "").strip()
    ok = result in ("filled", "skipped_already_filled")

    icon = "✅" if ok else "❌"
    if status:
        detail = (
            f"{status['recorded']}/{status['target']} h, {status['assignment']}, "
            f"status={status_text or 'unknown'}"
        )
    else:
        detail = "no row status available"

    return f"{icon} Timesheet {target_date} — result={result} ({detail})"


@click.command()
@click.option("--date", "date_str", default=None, help="Date to fill (YYYY-MM-DD). Defaults to today.")
@click.option("--hours", default=None, type=float, help="Override hours.")
@click.option("--assignment", default=None, help="Override assignment.")
@click.option("--skip", is_flag=True, help="Exit without filling any entry.")
@click.option("--url", default=None, help="Override the timesheet URL to navigate to.")
@click.option(
    "--no-backfill",
    "no_backfill",
    is_flag=True,
    help="Only fill target date; skip auto-fill of earlier weekdays this week.",
)
def main(date_str, hours, assignment, skip, url, no_backfill):
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

    dates_to_process = [target_date] if no_backfill else get_week_dates_to_fill(target_date)
    if len(dates_to_process) > 1:
        _print(
            f"Backfill mode: checking {len(dates_to_process)} day(s) — "
            f"{dates_to_process[0]} to {dates_to_process[-1]}"
        )

    ctrl = EdgeController()
    ctrl.connect()
    ts = TimesheetPage(ctrl, url=target_url)

    try:
        ts.open()

        target_result = None
        target_final_status = None
        for d in dates_to_process:
            result = ts.autofill_day(d, target_assignment, target_hours)
            time.sleep(1)
            final_status = ts.row_status(d)
            _print(f"[{d}] autofill_day result: {result}, row_status: {final_status}")
            if d == target_date:
                target_result = result
                target_final_status = final_status

        screenshot_path = _LOG_DIR / f"debug_{target_date}.png"
        if ctrl.screenshot(str(screenshot_path)):
            _print(f"Screenshot saved: {screenshot_path}")
        else:
            screenshot_path = None
        send_telegram_result(
            _build_ok_or_fail_message(target_date, target_result, target_final_status),
            image_path=screenshot_path,
        )
    except LoginPageError as e:
        _print(f"ERROR: {e}")
        screenshot_path = _LOG_DIR / f"debug_{target_date}_error.png"
        if not ctrl.screenshot(str(screenshot_path)):
            screenshot_path = None
        send_telegram_result(f"❌ Timesheet fill FAILED for {target_date}: {e}", image_path=screenshot_path)
        sys.exit(1)
    except Exception as e:
        _print(f"ERROR: {e}")
        screenshot_path = _LOG_DIR / f"debug_{target_date}_error.png"
        if not ctrl.screenshot(str(screenshot_path)):
            screenshot_path = None
        send_telegram_result(f"❌ Timesheet fill FAILED for {target_date}: {e}", image_path=screenshot_path)
        raise
    finally:
        ctrl.close()


if __name__ == "__main__":
    main()

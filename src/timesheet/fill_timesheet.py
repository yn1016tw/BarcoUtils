"""
TimesSheet Auto-Fill Tool
Automatically fills SAP Fiori CATS timesheet for Barco ClickShare Hub Pro employees.
"""

import csv
import datetime
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, BrowserContext, Page

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Logging — writes to log/fill_timesheet.log (appended) and stdout
# ---------------------------------------------------------------------------
_LOG_DIR = Path(__file__).parent / "log"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / f"fill_timesheet.log"
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


def _print(*args, **kwargs):
    """Drop-in for print() that also writes to the log file."""
    msg = " ".join(str(a) for a in args)
    log.info(msg)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SAP_URL = os.getenv("SAP_URL", "")
DEFAULT_ASSIGNMENT = os.getenv("DEFAULT_ASSIGNMENT", "Duvel")
DEFAULT_HOURS = float(os.getenv("DEFAULT_HOURS", "8"))
HOLIDAY_ASSIGNMENT = os.getenv("HOLIDAY_ASSIGNMENT", "Holiday")
HOLIDAY_HOURS = float(os.getenv("HOLIDAY_HOURS", "8"))

HOLIDAYS_CSV = Path(__file__).parent / "2026_holidays.csv"
EDGE_USER_DATA = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"


# ---------------------------------------------------------------------------
# Holiday CSV parsing
# ---------------------------------------------------------------------------
def load_holidays(csv_path: Path) -> set:
    holidays = set()
    pending: dict = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = [(r["date"].strip(), r["holiday"].strip())
                for r in csv.DictReader(f) if r["date"].strip()]
    for date_str, name in rows:
        d = datetime.date.fromisoformat(date_str)
        if name.endswith("(start)"):
            pending[name[:-len("(start)")].strip()] = d
        elif name.endswith("(end)"):
            base = name[:-len("(end)")].strip()
            start = pending.pop(base, d)
            cur = start
            while cur <= d:
                holidays.add(cur)
                cur += datetime.timedelta(days=1)
        else:
            holidays.add(d)
    return holidays


# ---------------------------------------------------------------------------
# Day-type decision
# ---------------------------------------------------------------------------
def get_day_type(date: datetime.date, holidays: set) -> str:
    if date.weekday() >= 5:
        return "weekend"
    if date in holidays:
        return "holiday"
    return "workday"


def get_week_dates_to_fill(target_date: datetime.date) -> list:
    """Return all dates from Monday of target_date's week up to and including target_date."""
    monday = target_date - datetime.timedelta(days=target_date.weekday())
    dates = []
    current = monday
    while current <= target_date:
        dates.append(current)
        current += datetime.timedelta(days=1)
    return dates


class SessionExpiredError(Exception):
    """Raised when SAP returns 403, indicating the session cookie has expired."""


# ---------------------------------------------------------------------------
# Browser / session
# ---------------------------------------------------------------------------
def kill_edge():
    result = subprocess.run(["tasklist", "/fi", "imagename eq msedge.exe"],
                            capture_output=True, text=True)
    if "msedge.exe" in result.stdout:
        _print("Closing Edge to free profile ...")
        subprocess.run(["taskkill", "/f", "/im", "msedge.exe"], capture_output=True)
        time.sleep(2)


def open_browser(playwright, hidden: bool = False):
    kill_edge()
    _print(f"Launching Edge with real profile ({'headless' if hidden else 'headed'}) ...")
    if hidden:
        # --start-maximized has no effect in headless mode; set an explicit desktop-sized viewport
        # so SAP Fiori renders the full table layout instead of the narrow responsive/mobile view.
        return playwright.chromium.launch_persistent_context(
            str(EDGE_USER_DATA),
            channel="msedge",
            headless=True,
            args=["--no-first-run", "--no-default-browser-check"],
            viewport={"width": 1920, "height": 1080},
        )
    return playwright.chromium.launch_persistent_context(
        str(EDGE_USER_DATA),
        channel="msedge",
        headless=False,
        args=["--no-first-run", "--no-default-browser-check", "--start-maximized"],
        no_viewport=True,
    )


def refresh_session_headed(pw):
    """
    Open a visible Edge window, navigate to SAP, and wait until the Fiori launchpad loads.
    This lets Microsoft SSO refresh the session cookie into the persistent profile.
    If SSO can auto-renew the token, the browser closes by itself.
    If a password prompt appears, the user can type it in the visible window.
    After this call the profile has a fresh SAP session cookie.
    pw: the already-running Playwright instance from the caller's sync_playwright() context.
    """
    _print("Session expired — opening headed Edge to refresh SAP session via SSO ...")
    kill_edge()
    ctx = pw.chromium.launch_persistent_context(
        str(EDGE_USER_DATA),
        channel="msedge",
        headless=False,
        args=["--no-first-run", "--no-default-browser-check", "--start-maximized"],
        no_viewport=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    resp = page.goto(SAP_URL, wait_until="domcontentloaded", timeout=60_000)
    _print(f"Headed browser response status: {resp.status if resp else 'unknown'} | URL: {page.url}")
    page.wait_for_timeout(4000)

    # Handle "Pick an account" dialog
    try:
        pick = page.wait_for_selector("text=james.yang@barco.com", timeout=5_000)
        if pick:
            _print("Pick an account dialog — clicking james.yang@barco.com ...")
            pick.click()
            page.wait_for_timeout(4000)
    except Exception:
        pass

    # Wait for Fiori launchpad — look for "My Timesheet" tile (up to 3 minutes)
    # This handles all SSO redirect variations regardless of the final URL pattern.
    _print("Waiting for SAP Fiori launchpad 'My Timesheet' tile (up to 3 minutes) ...")
    try:
        page.wait_for_selector("text=My Timesheet", timeout=180_000)
        _print(f"SAP session refreshed successfully. URL: {page.url}")
    except Exception:
        _print(f"WARNING: 'My Timesheet' tile not detected within timeout. URL: {page.url}")
        _print("Proceeding anyway — session may still have been refreshed.")
    ctx.close()
    kill_edge()


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------
def go_to_timesheet(page: Page):
    """Start from Shell-home, click 'My Timesheet', wait for app to load."""
    _print("Opening Fiori launchpad ...")
    response = page.goto(SAP_URL, wait_until="domcontentloaded", timeout=60_000)
    if response and response.status == 403:
        raise SessionExpiredError("SAP returned 403 Forbidden — session cookie expired.")
    page.wait_for_timeout(8000)

    # Handle "Pick an account" dialog (Microsoft SSO)
    pick_account = page.query_selector("text=james.yang@barco.com")
    if pick_account:
        _print("Pick an account dialog detected — clicking james.yang@barco.com ...")
        pick_account.click()
        page.wait_for_timeout(8000)

    # Handle login if needed
    if page.query_selector("input[id*='logonuidfield'], #USERNAME_FIELD"):
        _print("Login required — waiting for user ...")
        page.wait_for_url("*Shell-home*", timeout=300_000)
        page.wait_for_timeout(8000)

    _print("Clicking 'My Timesheet' ...")
    page.click("text=My Timesheet")
    page.wait_for_timeout(8000)
    _print(f"Timesheet page: {page.url}")


def navigate_to_week(page: Page, target_date: datetime.date):
    """
    Navigate the CATS calendar to the week containing target_date.
    The calendar shows a month view; use Previous/Next to get to the right month,
    then click the date cell.
    """
    # SAP CATS opens on the current week. Check if target date is visible.
    date_text = _format_date_text(target_date)
    if page.query_selector(f"text={date_text}"):
        _print(f"Date '{date_text}' already visible.")
        return

    sap_day = target_date.strftime("%Y%m%d")
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]

    # Navigate calendar month until target date cell is visible, then click it
    for attempt in range(12):
        day_cell = page.query_selector(f"[data-sap-day='{sap_day}']")
        if day_cell:
            _print(f"Clicking date cell {target_date} in calendar ...")
            day_cell.click()
            page.wait_for_timeout(6000)
            break

        # Read current month label and navigate toward target
        current_month = page.evaluate("""() => {
            for (const b of document.querySelectorAll('button')) {
                const a = b.getAttribute('aria-label') || '';
                if (/^(January|February|March|April|May|June|July|August|September|October|November|December)$/.test(a))
                    return a;
            }
            return null;
        }""")

        if current_month and current_month in months:
            cur_idx = months.index(current_month)
            tgt_idx = target_date.month - 1
            cur_year = int(page.evaluate("""() => {
                for (const b of document.querySelectorAll('button')) {
                    if (/^\\d{4}$/.test((b.textContent||'').trim())) return b.textContent.trim();
                }
                return '0';
            }""") or 0)
            if (cur_year, cur_idx) < (target_date.year, tgt_idx):
                page.click("[aria-label='Next']")
            else:
                page.click("[aria-label='Previous']")
            page.wait_for_timeout(6000)
        else:
            _print(f"WARNING: Could not read calendar month (attempt {attempt+1})")
            break
    else:
        _print(f"WARNING: Could not navigate to {target_date} in calendar")


def _format_date_text(date: datetime.date) -> str:
    """Format date as SAP CATS shows it: 'Wednesday, March 18, 2026'"""
    return f"{date.strftime('%A')}, {date.strftime('%B')} {date.day}, {date.year}"


# ---------------------------------------------------------------------------
# Core fill logic
# ---------------------------------------------------------------------------
def find_row_for_date(page: Page, date: datetime.date) -> dict | None:
    """
    Find the assignment + hours input IDs for the given date row.
    Returns dict with keys: assignment_id, hours_id, assignment_value, hours_value
    or None if date row not found.
    """
    date_text = _format_date_text(date)
    result = page.evaluate("""(dateText) => {
        // Try multiple selectors in order of specificity
        let tbody = document.querySelector('[id$="idOverviewTable-tblBody"]');
        if (!tbody) tbody = document.querySelector('[id*="tblBody"]');
        if (!tbody) {
            // Fallback: find any tbody containing the date text
            for (const tb of document.querySelectorAll('tbody')) {
                if (tb.innerText.includes(dateText)) { tbody = tb; break; }
            }
        }
        if (!tbody) {
            // Last resort: search all tr elements on the whole page
            const allRows = Array.from(document.querySelectorAll('tr'));
            const debugSample = allRows.slice(0, 10).map(r => r.innerText.trim().substring(0, 80).replace(/\\n/g, ' | '));
            return {_debug: 'no tbody', allRowSample: debugSample};
        }

        const rows = Array.from(tbody.querySelectorAll('tr'));
        const debugRows = rows.slice(0, 15).map(r => r.innerText.trim().substring(0, 80).replace(/\\n/g, ' | '));

        for (let i = 0; i < rows.length; i++) {
            if (rows[i].innerText.trim().includes(dateText)) {
                // Table structure: date row → empty row → data row (with inputs)
                // Try i+2 first (normal pattern), then i+1 as fallback
                for (const offset of [2, 1]) {
                    const dataRow = rows[i + offset];
                    if (!dataRow) continue;
                    const inputs = dataRow.querySelectorAll('input');
                    if (inputs.length >= 2) {
                        return {
                            assignment_id: inputs[0].id,
                            hours_id: inputs[1].id,
                            assignment_value: inputs[0].value,
                            hours_value: inputs[1].value,
                            assignment_placeholder: inputs[0].placeholder,
                        };
                    }
                }
                // Date row found but no editable inputs — entry is read-only (approved/submitted)
                const sectionText = [rows[i], rows[i+1], rows[i+2]].filter(Boolean)
                    .map(r => r.innerText.trim()).join(' | ');
                return {already_approved: true, section_text: sectionText};
            }
        }
        return {_debug: 'row not found', rowCount: rows.length, rows: debugRows};
    }""", date_text)

    if result and "_debug" in result:
        _print(f"find_row_for_date debug: {result}")
        return None
    return result  # may contain already_approved=True or full input info


def fill_assignment(page: Page, input_id: str, value: str):
    """Fill SAP ComboBox assignment field and confirm selection."""
    locator = page.locator(f"#{input_id}")
    locator.click()
    page.wait_for_timeout(300)
    locator.fill(value)
    page.wait_for_timeout(1500)

    # Try to click the first matching dropdown item
    try:
        item = page.query_selector(f"li[id*='__item']:has-text('{value}')")
        if item and item.is_visible():
            item.click()
            page.wait_for_timeout(500)
            return
    except Exception:
        pass

    # Fallback: press Enter to accept
    locator.press("Enter")
    page.wait_for_timeout(500)


def fill_hours(page: Page, input_id: str, hours: float):
    """Fill SAP StepInput hours field (uses comma as decimal separator)."""
    locator = page.locator(f"#{input_id}")
    locator.click()
    page.wait_for_timeout(300)
    # SAP uses comma: 8.0 -> "8,00"
    value_str = f"{hours:.2f}".replace(".", ",")
    locator.click(click_count=3)
    locator.type(value_str)
    locator.press("Tab")
    page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------
def send_telegram_result(message: str, image_path: Path | None = None):
    """Send a text message (and optional photo) to Telegram via Bot API."""
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


# ---------------------------------------------------------------------------
# Main fill orchestration
# ---------------------------------------------------------------------------
def fill_timesheet(page: Page, date: datetime.date, assignment: str, hours: float):
    """Full flow: select week in calendar -> Enter Records -> find date row -> fill -> Submit."""

    # 1. Select the target date in the calendar first (loads the correct week on the right)
    navigate_to_week(page, date)

    # 2. Click "Enter Records"
    enter_btn = page.query_selector("text=Enter Records")
    if not enter_btn:
        raise RuntimeError("'Enter Records' button not found on page.")
    enter_btn.click()
    _print("Clicked 'Enter Records'")
    page.wait_for_timeout(8000)

    # 3. Find the row for our date
    row = find_row_for_date(page, date)
    if not row:
        raise RuntimeError(f"Date row for '{_format_date_text(date)}' not found in table.")

    # 4a. Row is approved/submitted (read-only, no input elements) — nothing to fill
    if row.get("already_approved"):
        _print(f"Row already approved (read-only). Skipping fill. [{row.get('section_text', '')}]")
        try:
            cancel_btn = page.locator("button:visible").filter(has_text="Cancel").last
            cancel_btn.click(timeout=5000)
        except Exception:
            page.keyboard.press("Escape")
        page.wait_for_timeout(2000)
        return

    _print(f"Found row: assignment='{row['assignment_value']}' hours='{row['hours_value']}'")

    # 4b. Check if already filled (editable but values present) — skip to avoid duplicate
    if row["assignment_value"] and row["assignment_value"] != "" and row["hours_value"] not in ("0,00", "0.00", ""):
        _print(f"Row already filled ({row['assignment_value']} {row['hours_value']}h). Skipping fill.")
        # Exit edit mode: click the form-level Cancel (bottom bar), fallback to Escape
        try:
            cancel_btn = page.locator("button:visible").filter(has_text="Cancel").last
            cancel_btn.click(timeout=5000)
        except Exception:
            page.keyboard.press("Escape")
        page.wait_for_timeout(2000)
        return

    # 5. Fill assignment
    _print(f"Filling assignment: {assignment}")
    fill_assignment(page, row["assignment_id"], assignment)

    # 6. Fill hours
    _print(f"Filling hours: {hours}")
    fill_hours(page, row["hours_id"], hours)

    # 7. Take screenshot before submit for verification
    try:
        page.screenshot(path=str(_LOG_DIR / "debug_before_submit.png"))
        _print("Screenshot before submit: log/debug_before_submit.png")
    except Exception as ss_err:
        _print(f"Screenshot (before submit) failed: {ss_err}")

    # 8. Submit
    submit_btn = page.query_selector("text=Submit")
    if not submit_btn:
        raise RuntimeError("'Submit' button not found.")
    submit_btn.click()
    _print("Clicked 'Submit'")
    page.wait_for_timeout(4000)

    # 9. Screenshot after submit
    try:
        page.screenshot(path=str(_LOG_DIR / "debug_after_submit.png"))
        _print("Screenshot after submit: log/debug_after_submit.png")
    except Exception as ss_err:
        _print(f"Screenshot (after submit) failed: {ss_err}")
    _print(f"Done: {_format_date_text(date)} | {assignment} | {hours}h")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
@click.command()
@click.option("--date", "date_str", default=None, help="Date to fill (YYYY-MM-DD). Defaults to today.")
@click.option("--hours", default=None, type=float, help="Override hours.")
@click.option("--assignment", default=None, help="Override assignment.")
@click.option("--skip", is_flag=True, help="Exit without filling any entry.")
@click.option("--hidden", is_flag=True, help="Run browser off-screen (no visible window).")
@click.option("--no-backfill", "no_backfill", is_flag=True, help="Only fill target date; skip auto-backfill of earlier days this week.")
def main(date_str, hours, assignment, skip, hidden, no_backfill):
    target_date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    _print(f"Target date: {target_date} ({target_date.strftime('%A')})")

    if skip:
        _print(f"Skipping {target_date} (manual --skip).")
        send_telegram_result(f"⏭️ Timesheet skipped (--skip): {target_date}")
        sys.exit(0)

    # Load holidays
    if HOLIDAYS_CSV.exists():
        holiday_dates = load_holidays(HOLIDAYS_CSV)
    else:
        _print(f"WARNING: {HOLIDAYS_CSV} not found. Holiday detection disabled.")
        holiday_dates = set()

    if not SAP_URL:
        _print("ERROR: SAP_URL is not set in .env")
        sys.exit(1)

    # Build list of dates to process: Mon–today (backfill) or just today
    if no_backfill:
        dates_to_process = [target_date]
    else:
        dates_to_process = get_week_dates_to_fill(target_date)
        if len(dates_to_process) > 1:
            _print(f"Backfill mode: will check {len(dates_to_process)} day(s) — "
                   f"{dates_to_process[0]} to {dates_to_process[-1]}")

    # Resolve fill params per date (holidays may differ per day)
    def resolve_params(d: datetime.date):
        day_type = get_day_type(d, holiday_dates)
        if day_type == "holiday":
            return day_type, assignment or HOLIDAY_ASSIGNMENT, hours if hours is not None else HOLIDAY_HOURS
        return day_type, assignment or DEFAULT_ASSIGNMENT, hours if hours is not None else DEFAULT_HOURS

    RETRY_WAIT_SECONDS = 600
    filled_summary = []

    with sync_playwright() as pw:
        context = open_browser(pw, hidden=hidden)
        page = context.pages[0] if context.pages else context.new_page()
        session_opened = False

        for date in dates_to_process:
            day_type, fill_assignment_val, fill_hours_val = resolve_params(date)

            if day_type == "weekend":
                _print(f"Skipping weekend: {date}")
                continue
            if day_type == "holiday":
                _print(f"Day type: holiday -> {fill_assignment_val} ({fill_hours_val}h) for {date}")
            else:
                _print(f"Day type: workday -> {fill_assignment_val} ({fill_hours_val}h) for {date}")

            attempt = 0
            while True:
                attempt += 1
                _print(f"[{date}] Attempt #{attempt} ...")
                try:
                    if not session_opened:
                        go_to_timesheet(page)
                        session_opened = True
                    fill_timesheet(page, date, fill_assignment_val, fill_hours_val)
                    filled_summary.append(f"✅ {date} | {fill_assignment_val} | {fill_hours_val}h")
                    result_image: Path | None = None
                    try:
                        page.screenshot(path=str(_LOG_DIR / "debug_after_submit.png"))
                        result_image = _LOG_DIR / "debug_after_submit.png"
                    except Exception as ss_err:
                        _print(f"Screenshot (after fill) failed: {ss_err}")
                    send_telegram_result(filled_summary[-1], result_image)
                    break  # next date
                except SessionExpiredError as e:
                    _print(f"ERROR [{date}] (attempt #{attempt}): {e}")
                    context.close()
                    kill_edge()
                    send_telegram_result(f"⚠️ SAP session 過期，正在自動重新登入 ...")
                    refresh_session_headed(pw)
                    _print("Session refreshed — retrying ...")
                    context = open_browser(pw, hidden=hidden)
                    page = context.pages[0] if context.pages else context.new_page()
                    session_opened = False  # re-navigate after session refresh
                except Exception as e:
                    _print(f"ERROR [{date}] (attempt #{attempt}): {e}")
                    error_image: Path | None = None
                    try:
                        page.screenshot(path=str(_LOG_DIR / "debug_error.png"))
                        _print("Error screenshot saved: log/debug_error.png")
                        error_image = _LOG_DIR / "debug_error.png"
                    except Exception as ss_err:
                        _print(f"Screenshot failed: {ss_err}")
                    send_telegram_result(
                        f"❌ Timesheet 填寫失敗 (第 {attempt} 次): {date}\n{e}",
                        error_image,
                    )
                    context.close()
                    kill_edge()
                    _print(f"Retrying in {RETRY_WAIT_SECONDS}s ...")
                    time.sleep(RETRY_WAIT_SECONDS)
                    context = open_browser(pw, hidden=hidden)
                    page = context.pages[0] if context.pages else context.new_page()
                    session_opened = False

        context.close()

    if len(filled_summary) > 1:
        summary = "📋 本週補填摘要:\n" + "\n".join(filled_summary)
        _print(summary)
        send_telegram_result(summary)


if __name__ == "__main__":
    main()

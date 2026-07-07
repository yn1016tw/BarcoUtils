"""
Duvel Setup Tool

Automates MDEP Device Setup Wizard + Teams sign-in via ADB.
Polls which page is currently active and handles it — resilient to
page-order differences across firmware versions.

Pages handled (in any order):
  - Confirm connection
  - Language selection
  - Network connectivity
  - Date & time / timezone
  - Terms & Conditions (EULA)
  - Microsoft Privacy
  - Firmware update prompt
  - XMS Cloud enrollment (skipped)
  - Admin password creation
  - Confirm installation
  - Setup complete
  - Teams sign-in (on-device flow)
  - Teams email entry
  - Azure auth WebView (password + device registration)

Usage:
    python scripts/setup_tool.py --ip 192.168.1.100
    python scripts/setup_tool.py --serial 1882000501
    python scripts/setup_tool.py --ip 192.168.1.100 ^
        --email user@domain.com --password MyPW --admin-password Admin123!

Author: James Yang <james.yang@barco.com>
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "testcases"))

from common.duvel_device import DuvelDevice  # noqa: E402

# ── timeouts ──────────────────────────────────────────────────────────────────
_POLL_INTERVAL   = 1    # seconds between page polls
_FLOW_TIMEOUT    = 600  # 10 min total budget
_NETWORK_TIMEOUT = 60   # wait for network connectivity

# ── defaults ──────────────────────────────────────────────────────────────────
_DEFAULT_EMAIL          = "mtr_p_02@barcomxtest.onmicrosoft.com"
_DEFAULT_PASSWORD       = "Duvel_02"
_DEFAULT_LANGUAGE       = "English"
_DEFAULT_TIMEZONE       = "Taipei"
_DEFAULT_ADMIN_PASSWORD = "Admin@123"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log(step: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{step}] {msg}")


def _ok(step: str) -> None:
    _log(step, "OK")


def _fail(step: str, reason: str) -> None:
    _log(step, f"FAILED — {reason}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Page handlers  (called only after the page is confirmed visible)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_confirm_connection(ui) -> None:
    page = ui.device_setup_wizard
    _log("confirm_connection", f"IP={page.get_ip_address()}  FW={page.get_version()}")
    if not page.confirm_connection():
        _fail("confirm_connection", "could not tap 'Confirm connection'")
    _ok("confirm_connection")


def _handle_language(ui, language: str) -> None:
    page = ui.setup_language
    current = page.get_selected_language()
    _log("language", f"current='{current}'  target='{language}'")
    if current != language:
        if not page.select_language(language):
            _fail("language", f"could not select '{language}'")
    if not page.click_continue():
        _fail("language", "could not tap Continue")
    _ok("language")


def _handle_network(ui) -> None:
    page = ui.setup_network
    deadline = time.time() + _NETWORK_TIMEOUT
    while time.time() < deadline:
        if page.is_connected():
            break
        time.sleep(2)
    connected = page.is_connected()
    _log("network", f"connected={connected}  msg='{page.get_connectivity_message()}'")
    if not connected:
        _fail("network", "device is not connected to the network")
    if not page.click_next():
        _fail("network", "could not tap Next")
    _ok("network")


def _handle_datetime(ui, timezone: str) -> None:
    page = ui.setup_datetime
    _log("datetime", f"current timezone='{page.get_timezone()}'  target='{timezone}'")
    if not page.set_timezone(timezone):
        _fail("datetime", f"could not set timezone to '{timezone}'")
    _log("datetime", f"timezone set → '{page.get_timezone()}'")
    if not page.click_next():
        _fail("datetime", "could not tap Next")
    _ok("datetime")


def _handle_terms(ui) -> None:
    page = ui.setup_terms
    _log("terms", "accepting EULA")
    if not page.click_accept():
        _fail("terms", "could not tap 'I accept' / 'Continue'")
    _ok("terms")


def _handle_privacy(ui) -> None:
    page = ui.setup_privacy
    _log("privacy", "accepting Microsoft Privacy")
    if not page.click_accept():
        _fail("privacy", "could not tap Accept")
    _ok("privacy")


def _handle_setup_update(ui) -> None:
    page = ui.setup_update
    _log("setup_update", f"FW={page.get_fw_version()}")
    if not page.click_continue():
        _fail("setup_update", "could not tap Continue")
    _ok("setup_update")


def _handle_xms_cloud(ui) -> None:
    page = ui.setup_xms_cloud
    _log("xms_cloud", "skipping QR code enrollment")
    if not page.click_skip():
        _fail("xms_cloud", "could not tap Skip")
    _ok("xms_cloud")


def _handle_admin_password(ui, password: str) -> None:
    page = ui.setup_admin_password
    _log("admin_password", "creating admin password")
    if not page.enter_new_password(password):
        _fail("admin_password", "could not enter new password")
    time.sleep(0.5)
    if not page.enter_confirm_password(password):
        _fail("admin_password", "could not enter confirm password")
    time.sleep(0.5)
    _log("admin_password", f"strength={page.get_password_strength()}")
    if not page.click_create_and_continue():
        _fail("admin_password", "could not tap 'Create and continue'")
    _ok("admin_password")


def _handle_confirm_installation(ui) -> None:
    page = ui.setup_confirm
    _log("confirm_installation", f"room='{page.get_room_name()}'  status='{page.get_setup_status()}'")
    if not page.click_confirm_installation():
        _fail("confirm_installation", "could not tap 'Confirm installation'")
    _ok("confirm_installation")


def _handle_setup_complete(ui) -> None:
    page = ui.setup_complete
    _log("setup_complete", f"title='{page.get_title()}'")
    if not page.click_continue():
        _fail("setup_complete", "could not tap 'Continue to Microsoft Teams'")
    _ok("setup_complete")


def _handle_teams_sign_in(ui) -> None:
    page = ui.teams_sign_in
    _log("teams_sign_in", f"device-code='{page.get_login_code()}' — switching to on-device sign-in")
    if not page.click_sign_in_on_device():
        _fail("teams_sign_in", "could not tap 'Sign in on this device'")
    _ok("teams_sign_in")


def _handle_teams_email(ui, email: str) -> None:
    page = ui.teams_sign_in_email
    _log("teams_email", f"entering email '{email}'")
    if not page.enter_email(email):
        _fail("teams_email", "could not enter email")
    if not page.click_sign_in():
        _fail("teams_email", "could not tap Sign in")
    _ok("teams_email")


def _handle_azure_password(ui, password: str) -> None:
    page = ui.azure_auth_webview
    _log("azure_password", f"account='{page.get_display_name()}'")
    if not page.enter_password(password):
        _fail("azure_password", "could not enter password")
    if not page.click_sign_in():
        _fail("azure_password", "could not tap Sign in")
    _ok("azure_password")


def _handle_device_registration(ui) -> None:
    page = ui.azure_auth_webview
    _log("device_registration", f"heading='{page.get_heading()}'")
    if not page.click_register():
        _fail("device_registration", "could not tap Register")
    _ok("device_registration")


# ─────────────────────────────────────────────────────────────────────────────
# Main polling loop
# ─────────────────────────────────────────────────────────────────────────────

def _run_flow(ui, args: argparse.Namespace) -> None:
    handlers = [
        (
            "confirm_connection",
            lambda: ui.device_setup_wizard.is_visible(),
            lambda: _handle_confirm_connection(ui),
        ),
        (
            "language",
            lambda: ui.setup_language.is_visible(),
            lambda: _handle_language(ui, args.language),
        ),
        (
            "network",
            lambda: ui.setup_network.is_visible(),
            lambda: _handle_network(ui),
        ),
        (
            "datetime",
            lambda: ui.setup_datetime.is_visible(),
            lambda: _handle_datetime(ui, args.timezone),
        ),
        (
            "terms",
            lambda: ui.setup_terms.is_visible(),
            lambda: _handle_terms(ui),
        ),
        (
            "privacy",
            lambda: ui.setup_privacy.is_visible(),
            lambda: _handle_privacy(ui),
        ),
        (
            "setup_update",
            lambda: ui.setup_update.is_visible(),
            lambda: _handle_setup_update(ui),
        ),
        (
            "xms_cloud",
            lambda: ui.setup_xms_cloud.is_visible(),
            lambda: _handle_xms_cloud(ui),
        ),
        (
            "admin_password",
            lambda: ui.setup_admin_password.is_visible(),
            lambda: _handle_admin_password(ui, args.admin_password),
        ),
        (
            "confirm_installation",
            lambda: ui.setup_confirm.is_visible(),
            lambda: _handle_confirm_installation(ui),
        ),
        (
            "setup_complete",
            lambda: ui.setup_complete.is_visible(),
            lambda: _handle_setup_complete(ui),
        ),
        (
            "teams_sign_in",
            lambda: ui.teams_sign_in.is_visible(),
            lambda: _handle_teams_sign_in(ui),
        ),
        (
            "teams_email",
            lambda: ui.teams_sign_in_email.is_visible(),
            lambda: _handle_teams_email(ui, args.email),
        ),
        (
            "azure_password",
            lambda: ui.azure_auth_webview.is_visible() and ui.azure_auth_webview.is_password_page(),
            lambda: _handle_azure_password(ui, args.password),
        ),
        (
            "device_registration",
            lambda: ui.azure_auth_webview.is_visible() and ui.azure_auth_webview.is_device_registration_page(),
            lambda: _handle_device_registration(ui),
        ),
    ]

    completed: set[str] = set()
    deadline = time.time() + _FLOW_TIMEOUT

    with ui.ui_dump_cache():
        while time.time() < deadline:
            if ui.main.is_visible():
                break

            matched = False
            for name, check_fn, handle_fn in handlers:
                if name in completed:
                    continue
                if check_fn():
                    handle_fn()
                    completed.add(name)
                    matched = True
                    break

            if not matched:
                time.sleep(_POLL_INTERVAL)
        else:
            _fail("flow", f"timed out after {_FLOW_TIMEOUT}s — completed: {sorted(completed)}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Automate MDEP setup wizard + Teams sign-in on Duvel",
    )
    conn = p.add_mutually_exclusive_group(required=True)
    conn.add_argument("--ip",     metavar="HOST[:PORT]", help="Device IP (TCP/IP ADB)")
    conn.add_argument("--serial", metavar="SERIAL",      help="Device USB serial number")

    p.add_argument("--email",    default=_DEFAULT_EMAIL,
                   help=f"Teams account email (default: {_DEFAULT_EMAIL})")
    p.add_argument("--password", default=_DEFAULT_PASSWORD,
                   help=f"Teams account password (default: {_DEFAULT_PASSWORD})")
    p.add_argument("--admin-password", default=_DEFAULT_ADMIN_PASSWORD,
                   metavar="PASS",
                   help=f"Admin password for setup wizard (default: {_DEFAULT_ADMIN_PASSWORD})")
    p.add_argument("--language", default=_DEFAULT_LANGUAGE,
                   help=f"Language to select (default: {_DEFAULT_LANGUAGE})")
    p.add_argument("--timezone", default=_DEFAULT_TIMEZONE,
                   help=f"Timezone city name to select (default: {_DEFAULT_TIMEZONE})")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    if args.ip:
        device = DuvelDevice(serial=args.ip, is_ip=True)
    else:
        device = DuvelDevice(serial=args.serial, is_ip=False)
    device.connect()

    fw = device.barco_fw_version()
    print(f"\n{'=' * 60}")
    print(f"  Device : {args.ip or args.serial}")
    print(f"  FW     : {fw}")
    print(f"  Email  : {args.email}")
    print(f"  TZ     : {args.timezone}")
    print(f"{'=' * 60}\n")

    _run_flow(device.ui, args)

    print(f"\n{'=' * 60}")
    print("  Setup flow complete.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()

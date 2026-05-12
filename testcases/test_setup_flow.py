"""
MDEP Device Setup Automation

Automates the complete MDEP Device Setup Wizard flow and Teams sign-in:
  1.  Confirm connection (wizard entry screen)
  2.  Language     — select English, continue
  3.  Network      — click Next (assumes Ethernet already connected)
  4.  Date & time  — set timezone to Taipei, click Next
  5.  Terms        — accept EULA
  6.  Privacy      — accept Microsoft Privacy
  7.  XMS Cloud    — skip QR-code enrollment
  8.  Admin password (dialog) — create password if prompted
  9.  Confirm installation
  10. Setup complete → Continue to Microsoft Teams
  11. Teams sign-in (DCF screen) → Sign in on this device
  12. Teams email entry → enter email, Sign in
  13. Azure auth WebView → enter password, Sign in
  14. Device registration (if prompted) → Register

Each step checks whether the screen is visible before acting. Steps that
are already past (screen not shown) are silently skipped.

Usage:
    python testcases/test_setup_flow.py --ip 192.168.1.100
    python testcases/test_setup_flow.py --serial 1882000501
    python testcases/test_setup_flow.py --ip 192.168.1.100 \\
        --email user@domain.com --password MyPW --admin-password Admin123!
"""

import argparse
import sys
import time
from datetime import datetime

from common.duvel_device import DuvelDevice

# ── timeouts (seconds) ────────────────────────────────────────────────────────
_WIZARD_TIMEOUT  = 30   # wizard / language / datetime / terms / privacy / xms
_NETWORK_TIMEOUT = 60   # network step may wait for IP
_TEAMS_TIMEOUT   = 120  # Teams app launch after setup complete
_AUTH_TIMEOUT    = 60   # Azure WebView MSAL page load

# ── defaults ──────────────────────────────────────────────────────────────────
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


def _skip(step: str) -> None:
    _log(step, "not visible — skipped")


def _fail(step: str, reason: str) -> None:
    _log(step, f"FAILED — {reason}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Setup steps
# ─────────────────────────────────────────────────────────────────────────────

def step_confirm_connection(ui) -> None:
    page = ui.device_setup_wizard
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("confirm_connection")
        return
    _log("confirm_connection", f"IP={page.get_ip_address()}  FW={page.get_version()}")
    if not page.confirm_connection():
        _fail("confirm_connection", "could not tap 'Confirm connection'")
    _ok("confirm_connection")


def step_language(ui, language: str) -> None:
    page = ui.setup_language
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("language")
        return
    current = page.get_selected_language()
    _log("language", f"current='{current}'  target='{language}'")
    if current != language:
        if not page.select_language(language):
            _fail("language", f"could not select '{language}'")
    if not page.click_continue():
        _fail("language", "could not tap Continue")
    _ok("language")


def step_network(ui) -> None:
    page = ui.setup_network
    if not page.is_visible(timeout=_NETWORK_TIMEOUT):
        _skip("network")
        return
    connected = page.is_connected()
    _log("network", f"connected={connected}  msg='{page.get_connectivity_message()}'")
    if not connected:
        _fail("network", "device is not connected to the network")
    if not page.click_next():
        _fail("network", "could not tap Next")
    _ok("network")


def step_datetime(ui, timezone: str) -> None:
    page = ui.setup_datetime
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("datetime")
        return
    _log("datetime", f"current timezone='{page.get_timezone()}'  target='{timezone}'")
    if not page.set_timezone(timezone):
        _fail("datetime", f"could not set timezone to '{timezone}'")
    _log("datetime", f"timezone set → '{page.get_timezone()}'")
    if not page.click_next():
        _fail("datetime", "could not tap Next")
    _ok("datetime")


def step_terms(ui) -> None:
    page = ui.setup_terms
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("terms")
        return
    _log("terms", "accepting EULA")
    if not page.click_accept():
        _fail("terms", "could not tap 'I accept'")
    _ok("terms")


def step_privacy(ui) -> None:
    page = ui.setup_privacy
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("privacy")
        return
    _log("privacy", "accepting Microsoft Privacy")
    if not page.click_accept():
        _fail("privacy", "could not tap Accept")
    _ok("privacy")


def step_xms_cloud(ui) -> None:
    page = ui.setup_xms_cloud
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("xms_cloud")
        return
    _log("xms_cloud", "skipping QR code enrollment")
    if not page.click_skip():
        _fail("xms_cloud", "could not tap Skip")
    _ok("xms_cloud")


def step_admin_password(ui, password: str) -> None:
    page = ui.setup_admin_password
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("admin_password")
        return
    _log("admin_password", "creating admin password")
    if not page.enter_new_password(password):
        _fail("admin_password", "could not enter new password")
    time.sleep(0.5)
    if not page.enter_confirm_password(password):
        _fail("admin_password", "could not enter confirm password")
    time.sleep(0.5)
    strength = page.get_password_strength()
    _log("admin_password", f"strength={strength}")
    if not page.click_create_and_continue():
        _fail("admin_password", "could not tap 'Create and continue'")
    _ok("admin_password")


def step_confirm_installation(ui) -> None:
    page = ui.setup_confirm
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("confirm_installation")
        return
    _log("confirm_installation", f"room='{page.get_room_name()}'  status='{page.get_setup_status()}'")
    if not page.click_confirm_installation():
        _fail("confirm_installation", "could not tap 'Confirm installation'")
    _ok("confirm_installation")


def step_setup_complete(ui) -> None:
    page = ui.setup_complete
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("setup_complete")
        return
    _log("setup_complete", f"title='{page.get_title()}'")
    if not page.click_continue():
        _fail("setup_complete", "could not tap 'Continue to Microsoft Teams'")
    _ok("setup_complete")


def step_teams_sign_in(ui) -> None:
    page = ui.teams_sign_in
    if not page.is_visible(timeout=_TEAMS_TIMEOUT):
        _skip("teams_sign_in")
        return
    code = page.get_login_code()
    _log("teams_sign_in", f"device-code='{code}' — switching to on-device sign-in")
    if not page.click_sign_in_on_device():
        _fail("teams_sign_in", "could not tap 'Sign in on this device'")
    _ok("teams_sign_in")


def step_teams_email(ui, email: str) -> None:
    page = ui.teams_sign_in_email
    if not page.is_visible(timeout=_WIZARD_TIMEOUT):
        _skip("teams_email")
        return
    _log("teams_email", f"entering email '{email}'")
    if not page.enter_email(email):
        _fail("teams_email", "could not enter email")
    if not page.click_sign_in():
        _fail("teams_email", "could not tap Sign in")
    _ok("teams_email")


def step_azure_password(ui, password: str) -> None:
    page = ui.azure_auth_webview
    if not page.is_visible(timeout=_AUTH_TIMEOUT):
        _skip("azure_password")
        return

    # Wait for the password sub-page to load inside the WebView.
    deadline = time.time() + _AUTH_TIMEOUT
    while time.time() < deadline:
        if page.is_password_page():
            break
        time.sleep(1)
    else:
        _fail("azure_password", "password page did not load inside WebView")

    display_name = page.get_display_name()
    _log("azure_password", f"account='{display_name}'")
    if not page.enter_password(password):
        _fail("azure_password", "could not enter password")
    if not page.click_sign_in():
        _fail("azure_password", "could not tap Sign in")
    _ok("azure_password")


def step_device_registration(ui) -> None:
    page = ui.azure_auth_webview
    # Registration prompt appears inside the same WebView after password sign-in.
    deadline = time.time() + _AUTH_TIMEOUT
    while time.time() < deadline:
        if page.is_device_registration_page():
            _log("device_registration", f"heading='{page.get_heading()}'")
            if not page.click_register():
                _fail("device_registration", "could not tap Register")
            _ok("device_registration")
            return
        # Also check if Teams main page is already up (registration skipped).
        if ui.main.is_visible():
            _skip("device_registration")
            return
        time.sleep(2)
    _skip("device_registration")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Automate MDEP setup wizard + Teams sign-in on Duvel",
    )
    conn = p.add_mutually_exclusive_group(required=True)
    conn.add_argument("--ip",     metavar="HOST[:PORT]", help="Device IP (TCP/IP ADB)")
    conn.add_argument("--serial", metavar="SERIAL",      help="Device USB serial number")

    p.add_argument("--email",    default="mtr_p_25@barcomxdev.onmicrosoft.com",
                   help="Teams account email (default: mtr_p_25@barcomxdev.onmicrosoft.com)")
    p.add_argument("--password", default="Devel_25",
                   help="Teams account password (default: Devel_25)")
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

    serial = args.ip if args.ip else args.serial
    device = DuvelDevice(serial=serial)
    device.connect()

    fw = device.barco_fw_version()
    print(f"\n{'=' * 60}")
    print(f"  Device : {serial}")
    print(f"  FW     : {fw}")
    print(f"  Email  : {args.email}")
    print(f"  TZ     : {args.timezone}")
    print(f"{'=' * 60}\n")

    ui = device.ui

    # ── Setup wizard ──────────────────────────────────────────────────────────
    step_confirm_connection(ui)
    step_language(ui, args.language)
    step_network(ui)
    step_datetime(ui, args.timezone)
    step_terms(ui)
    step_privacy(ui)
    step_xms_cloud(ui)
    step_admin_password(ui, args.admin_password)
    step_confirm_installation(ui)
    step_setup_complete(ui)

    # ── Teams sign-in ─────────────────────────────────────────────────────────
    step_teams_sign_in(ui)
    step_teams_email(ui, args.email)
    step_azure_password(ui, args.password)
    step_device_registration(ui)

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  Setup flow complete.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()

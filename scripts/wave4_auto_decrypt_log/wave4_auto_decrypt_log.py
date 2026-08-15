#!/usr/bin/env python3
"""
wave4_auto_decrypt_log.py
Auto-decrypts Wave4 log files via the Barco MX decrypt portal.

Usage:
    python wave4_auto_decrypt_log.py <path_to_zip_file>
"""

import glob
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

PORTAL_URL = "https://mx.barco.com:5900/"
DOWNLOAD_DIR = Path.home() / "Downloads"

DECRYPT_TIMEOUT = 300_000  # ms — time to wait for decrypt to complete
DOWNLOAD_TIMEOUT = 120_000  # ms — time to wait for file download

# ---------------------------------------------------------------------------
# Edge CDP profile (verified working approach)
# ---------------------------------------------------------------------------
# Chromium/Edge unconditionally refuses to expose remote debugging (CDP) when
# --user-data-dir points at the REAL default profile path
# (%LOCALAPPDATA%\Microsoft\Edge\User Data) — a built-in anti-automation
# restriction with no command-line override, unrelated to the IT
# "RemoteDebuggingAllowed" group policy (confirmed unset). This is why
# launch_persistent_context() against the real profile used to work and then
# silently stopped. Workaround: copy the real profile (keeps cookies/session)
# into a separate folder, launch Edge from that copy with an explicit
# --remote-debugging-port, and attach via connect_over_cdp().
EDGE_USER_DATA = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"
EDGE_EXE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
CDP_PROFILE_DIR = Path(os.environ.get("LOCALAPPDATA", r"C:\temp")) / "BarcoUtilsEdgeCdpProfile"
CDP_PORT = int(os.environ.get("EDGE_CDP_PORT", "9334"))


# ---------------------------------------------------------------------------
# Zip helpers
# ---------------------------------------------------------------------------

def find_pgp_in_zip(zip_path: str) -> list[str]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        return [n for n in zf.namelist() if n.lower().endswith(".pgp")]


def extract_pgp_files(zip_path: str, dest_dir: str) -> list[str]:
    """Extract all .pgp files from zip into dest_dir. Returns extracted absolute paths."""
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".pgp"):
                zf.extract(name, dest_dir)
                extracted.append(str(Path(dest_dir) / name))
    return extracted


# ---------------------------------------------------------------------------
# Browser (CDP-based — see "Edge CDP profile" notes above)
# ---------------------------------------------------------------------------

def _find_edge_exe() -> str:
    for exe in EDGE_EXE_CANDIDATES:
        if os.path.exists(exe):
            return exe
    raise RuntimeError("msedge.exe not found; please confirm Edge is installed.")


def kill_cdp_edge() -> None:
    """Close only the msedge.exe processes running against our copied CDP
    profile (never touches the user's real, everyday Edge windows)."""
    subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{CDP_PROFILE_DIR}*' }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    time.sleep(1.5)


def patch_exit_type() -> None:
    """Reset exit_type/exited_cleanly in every Preferences file under the
    copied profile back to 'Normal'/true, avoiding a 'Restore pages?' dialog
    that would otherwise block unattended runs (we always close Edge via
    Stop-Process -Force, which Chromium marks as a crash)."""
    for prefs_path in glob.glob(str(CDP_PROFILE_DIR / "*" / "Preferences")):
        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                content = f.read()
            patched = re.sub(r'"exit_type":"[^"]*"', '"exit_type":"Normal"', content)
            patched = re.sub(r'"exited_cleanly":\s*false', '"exited_cleanly":true', patched)
            if patched != content:
                with open(prefs_path, "w", encoding="utf-8") as f:
                    f.write(patched)
        except Exception as e:
            print(f"[WARN] could not patch exit_type in {prefs_path}: {e}")


def _wait_cdp_ready(port: int, timeout: int = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _sync_cdp_profile(fresh: bool = False) -> None:
    """Copy the real default Edge profile (carrying cookies/session) into
    CDP_PROFILE_DIR, excluding large cache folders. Skipped if the copy
    already exists, unless fresh=True."""
    if fresh and CDP_PROFILE_DIR.exists():
        print(f"[*] Removing stale CDP profile copy: {CDP_PROFILE_DIR}")
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(CDP_PROFILE_DIR)], capture_output=True)

    if CDP_PROFILE_DIR.exists():
        return

    if not EDGE_USER_DATA.exists():
        raise RuntimeError(f"Default Edge profile not found: {EDGE_USER_DATA}")

    print(f"[*] Copying Edge profile: {EDGE_USER_DATA} -> {CDP_PROFILE_DIR} (excluding cache dirs) ...")
    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "robocopy", str(EDGE_USER_DATA), str(CDP_PROFILE_DIR),
            "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS",
            "/XD", "Cache", "Code Cache", "GPUCache", "DawnCache", "GrShaderCache",
            "ShaderCache", "component_crx_cache", "Service Worker", "blob_storage",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    # robocopy exit codes 0-7 are success; 8+ is a real failure.
    if result.returncode >= 8:
        raise RuntimeError(f"robocopy failed copying Edge profile (exit code {result.returncode}): {result.stdout}\n{result.stderr}")
    print("[*] Profile copy complete.")


def open_browser(playwright, hidden: bool = False, fresh_profile: bool = False):
    """Launch Edge (against a copied profile) with CDP enabled, then attach
    via Playwright's connect_over_cdp(). Avoids launch_persistent_context()
    against the real profile, which Chromium unconditionally refuses to
    expose over CDP. Returns (browser, context)."""
    kill_cdp_edge()
    _sync_cdp_profile(fresh=fresh_profile)
    patch_exit_type()

    edge_exe = _find_edge_exe()
    args = [
        edge_exe,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CDP_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-crash-restore-bubble",
        "--ignore-certificate-errors",
    ]
    if hidden:
        args += ["--headless=new", "--window-size=1920,1080"]
    else:
        args += ["--start-maximized"]

    print(f"[*] Launching Edge with copied profile ({'headless' if hidden else 'headed'}) ...")
    subprocess.Popen(args)

    if not _wait_cdp_ready(CDP_PORT):
        raise RuntimeError(f"Edge CDP did not become ready on port {CDP_PORT}.")

    browser = playwright.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    return browser, context


def close_browser(browser) -> None:
    """Disconnect Playwright and fully close the copied-profile Edge
    instance, then immediately repair exit_type so no 'Restore pages?'
    dialog appears next launch."""
    try:
        browser.close()
    except Exception:
        pass
    kill_cdp_edge()
    patch_exit_type()


# ---------------------------------------------------------------------------
# Decrypt flow
# ---------------------------------------------------------------------------

def run_decrypt(page: Page, pgp_path: str, output_dir: Path) -> None:
    abs_pgp = str(Path(pgp_path).resolve())

    # Navigate to portal
    print(f"[*] Navigating to {PORTAL_URL} ...")
    page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(2000)

    # Upload .pgp file
    print(f"[*] Uploading: {abs_pgp}")
    file_input = page.query_selector("input[type='file']")
    if file_input is None:
        raise RuntimeError("Could not find file upload input on the page.")
    file_input.set_input_files(abs_pgp)
    print("[*] Waiting for upload to complete (polling every second) ...")
    _wait_for_upload(page, Path(pgp_path).name, DECRYPT_TIMEOUT)
    print("[*] Upload complete.")

    # Click "Decrypt Log File"
    print("[*] Clicking 'Decrypt Log File' ...")
    decrypt_btn = _find_button(page, ["Decrypt Log File", "Decrypt"])
    if decrypt_btn is None:
        raise RuntimeError("Could not find 'Decrypt Log File' button.")
    decrypt_btn.click()
    print("[*] Waiting for decrypt to complete (polling every second) ...")

    # Wait for "Download File" button to appear — signals decrypt is done
    _wait_for_download_button(page, DECRYPT_TIMEOUT)
    print("[*] Decrypt complete!")

    # Click "Download File"
    print("[*] Clicking 'Download File' ...")
    download_btn = _find_button(page, ["Download File", "Download"])
    if download_btn is None:
        raise RuntimeError("Could not find 'Download File' button.")

    with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as dl_info:
        download_btn.click()

    download = dl_info.value
    downloaded_file = output_dir / download.suggested_filename
    download.save_as(str(downloaded_file))
    print(f"[OK] Downloaded: {downloaded_file}")

    # Extract downloaded file into a folder named after the .pgp file (no extension)
    folder_name = Path(pgp_path).stem
    extract_dir = output_dir / folder_name
    extract_dir.mkdir(exist_ok=True)
    print(f"[*] Extracting to: {extract_dir}")
    with zipfile.ZipFile(str(downloaded_file), "r") as zf:
        zf.extractall(str(extract_dir))
    print(f"[OK] Extracted to: {extract_dir}")

    # Remove the temporary downloaded zip after extraction
    try:
        os.remove(str(downloaded_file))
    except OSError:
        pass

    # Remove the .pgp file after successful decryption
    try:
        os.remove(pgp_path)
        print(f"[*] Removed .pgp file: {pgp_path}")
    except OSError as e:
        print(f"[WARN] Could not remove .pgp file {pgp_path}: {e}")


def _wait_for_upload(page: Page, filename: str, timeout_ms: int) -> None:
    """Poll every second until the page acknowledges the uploaded file by name."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        body_text = page.locator("body").inner_text()
        if filename.lower() in body_text.lower():
            return
        # Also accept if the Decrypt button becomes enabled/visible
        btn = _find_button(page, ["Decrypt Log File", "Decrypt"])
        if btn is not None:
            return
        time.sleep(1)
        print(".", end="", flush=True)
    print()
    raise RuntimeError("Upload did not complete within the timeout.")


def _find_button(page: Page, labels: list[str]):
    """Return the first visible button/link whose text matches any label."""
    for label in labels:
        el = page.query_selector(f"button:has-text('{label}')")
        if el and el.is_visible():
            return el
        el = page.query_selector(f"a:has-text('{label}')")
        if el and el.is_visible():
            return el
        el = page.query_selector(f"input[value*='{label}']")
        if el and el.is_visible():
            return el
    return None


def _wait_for_download_button(page: Page, timeout_ms: int) -> None:
    """Poll every second until a Download button appears or timeout."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        btn = _find_button(page, ["Download File", "Download"])
        if btn is not None:
            return
        time.sleep(1)
        print(".", end="", flush=True)
    print()
    raise RuntimeError("Decrypt did not complete within the timeout.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    hidden = "--hidden" in sys.argv

    if not args:
        print("Usage: python wave4_auto_decrypt_log.py [--hidden] <path_to_zip_file>")
        sys.exit(1)

    zip_path = args[0]

    if not os.path.isfile(zip_path):
        print(f"[ERROR] File not found: {zip_path}")
        sys.exit(1)

    if not zip_path.lower().endswith(".zip"):
        print(f"[ERROR] Expected a .zip file, got: {zip_path}")
        sys.exit(1)

    output_dir = Path(zip_path).resolve().parent
    print(f"[*] Processing: {zip_path}")
    print(f"[*] Output directory: {output_dir}")

    # Extract .pgp files from zip
    pgp_names = find_pgp_in_zip(zip_path)
    if not pgp_names:
        print("[ERROR] No .pgp files found inside the zip.")
        sys.exit(1)

    print(f"[*] Found {len(pgp_names)} .pgp file(s): {pgp_names}")

    tmp_dir = tempfile.mkdtemp()
    pgp_paths = extract_pgp_files(zip_path, tmp_dir)
    print(f"[*] Extracted: {pgp_paths}")

    # Run browser automation for each .pgp file
    with sync_playwright() as pw:
        browser, context = open_browser(pw, hidden=hidden)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for pgp_path in pgp_paths:
                print(f"\n[*] Processing: {pgp_path}")
                run_decrypt(page, pgp_path, output_dir)
        except Exception as e:
            print(f"[ERROR] {e}")
            raise
        finally:
            close_browser(browser)


if __name__ == "__main__":
    main()

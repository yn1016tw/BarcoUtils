#!/usr/bin/env python3
"""Automate Chrome Remote Desktop: connect to a remote computer via PIN,
log into Windows on the remote screen, run a program via Win+R, then disconnect.

CAVEAT: remotedesktop.google.com's DOM structure is not publicly documented and
may change. The selectors below (computer entry, PIN input, Disconnect button)
are best-effort text/role matches. If a step fails, re-run with --debug-pause
before that step to open the Playwright Inspector and adjust the selector
against the live page.

The remote screen itself is a <canvas> video stream with no DOM to introspect,
so Windows login/desktop readiness is judged via OCR (pytesseract) on
screenshots of that canvas.
"""

import argparse
import getpass
import io
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE_DIR = SCRIPT_DIR / "chrome_profile"
LOG_DIR = SCRIPT_DIR / "log"

DEFAULT_LOGIN_KEYWORDS = ["密碼", "Password", "PIN", "登入", "Sign in"]


def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_remote_login.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("remote_login")


def ocr_contains_any(image_bytes, keywords, tesseract_cmd=None):
    if pytesseract is None:
        raise RuntimeError("pytesseract/Pillow 未安裝，請執行: pip install pytesseract pillow")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image, lang="chi_tra+eng")
    return any(k in text for k in keywords)


def wait_for_canvas_text(canvas_locator, keywords, timeout, poll_interval, tesseract_cmd, log):
    if not keywords:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        screenshot = canvas_locator.screenshot()
        if ocr_contains_any(screenshot, keywords, tesseract_cmd):
            return True
        time.sleep(poll_interval)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--computer-name", required=True, help="Chrome Remote Desktop 遠端電腦顯示名稱")
    parser.add_argument("--pin", help="CRD PIN；未提供則互動輸入（不會顯示在畫面上）")
    parser.add_argument("--windows-password", help="遠端電腦 Windows 登入密碼；未提供則互動輸入")
    parser.add_argument("--program-path", required=True, help="登入後透過 Win+R 執行的完整路徑或指令")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR),
                         help="Chrome persistent profile 目錄；首次使用需手動以此 profile 開 Chrome 登入 Google 帳號")
    parser.add_argument("--tesseract-cmd", help="tesseract.exe 完整路徑（不在 PATH 時指定）")
    parser.add_argument("--login-keywords", default=",".join(DEFAULT_LOGIN_KEYWORDS),
                         help="OCR 判斷『已到 Windows 登入畫面』的關鍵字，逗號分隔")
    parser.add_argument("--desktop-keywords", default="",
                         help="OCR 判斷『已進桌面』的關鍵字，逗號分隔；留空則只用 --post-login-wait 固定等待")
    parser.add_argument("--login-timeout", type=float, default=60, help="等待登入畫面出現的逾時秒數")
    parser.add_argument("--desktop-timeout", type=float, default=60, help="等待桌面出現的逾時秒數（僅在有 --desktop-keywords 時使用）")
    parser.add_argument("--post-login-wait", type=float, default=8, help="送出密碼後、開始判斷桌面前的固定等待秒數")
    parser.add_argument("--post-launch-wait", type=float, default=5, help="執行完程式後、斷線前的固定等待秒數")
    parser.add_argument("--poll-interval", type=float, default=2, help="OCR 輪詢間隔秒數")
    parser.add_argument("--debug-pause", choices=["connect", "pin", "login", "launch"],
                         help="在指定步驟前呼叫 page.pause() 開啟 Playwright Inspector，方便對照實際畫面調整 selector")
    args = parser.parse_args()

    log = setup_logger()

    pin = args.pin or getpass.getpass("CRD PIN: ")
    windows_password = args.windows_password or getpass.getpass("Windows 密碼: ")
    login_keywords = [k.strip() for k in args.login_keywords.split(",") if k.strip()]
    desktop_keywords = [k.strip() for k in args.desktop_keywords.split(",") if k.strip()]

    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        log.info("啟動 Chrome（persistent profile: %s）", profile_dir)
        context = p.chromium.launch_persistent_context(
            str(profile_dir),
            channel="chrome",
            headless=False,
            viewport=None,
            args=["--start-maximized"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            log.info("開啟 remotedesktop.google.com/access")
            page.goto("https://remotedesktop.google.com/access", wait_until="domcontentloaded")

            if args.debug_pause == "connect":
                page.pause()

            log.info("尋找遠端電腦：%s", args.computer_name)
            computer_entry = page.get_by_text(args.computer_name, exact=False).first
            computer_entry.wait_for(state="visible", timeout=30000)
            computer_entry.click()

            if args.debug_pause == "pin":
                page.pause()

            log.info("輸入 PIN")
            pin_input = page.locator('input[type="password"]').first
            pin_input.wait_for(state="visible", timeout=15000)
            pin_input.fill(pin)
            page.keyboard.press("Enter")

            log.info("等待連線建立（Disconnect 按鈕出現）")
            disconnect_button = page.get_by_role("button", name="Disconnect")
            disconnect_button.wait_for(state="visible", timeout=60000)
            log.info("連線已建立")

            canvas = page.locator("canvas").first
            canvas.wait_for(state="visible", timeout=30000)
            canvas.click()

            if args.debug_pause == "login":
                page.pause()

            log.info("等待 Windows 登入畫面（OCR，逾時 %ss）", args.login_timeout)
            found = wait_for_canvas_text(canvas, login_keywords, args.login_timeout, args.poll_interval, args.tesseract_cmd, log)
            if not found:
                log.warning("OCR 逾時未偵測到登入畫面關鍵字，仍繼續嘗試輸入密碼")

            canvas.click()
            page.keyboard.type(windows_password)
            page.keyboard.press("Enter")
            log.info("已送出 Windows 密碼")

            time.sleep(args.post_login_wait)
            if desktop_keywords:
                log.info("等待桌面出現（OCR，逾時 %ss）", args.desktop_timeout)
                found = wait_for_canvas_text(canvas, desktop_keywords, args.desktop_timeout, args.poll_interval, args.tesseract_cmd, log)
                if not found:
                    log.warning("OCR 逾時未偵測到桌面關鍵字，仍繼續執行程式")

            if args.debug_pause == "launch":
                page.pause()

            log.info("送出 Win+R 並執行程式：%s", args.program_path)
            canvas.click()
            page.keyboard.press("Meta+r")
            time.sleep(1)
            page.keyboard.type(args.program_path)
            page.keyboard.press("Enter")

            time.sleep(args.post_launch_wait)
            log.info("斷線")
            disconnect_button.click()
            time.sleep(2)

        except PlaywrightTimeoutError as e:
            log.error("逾時失敗：%s", e)
            raise
        finally:
            context.close()

    log.info("完成")


if __name__ == "__main__":
    main()

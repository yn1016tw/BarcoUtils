#!/usr/bin/env python3
"""Automate Chrome Remote Desktop: connect to a remote computer via PIN,
log into Windows on the remote screen, run a program via Win+R, then disconnect.

Chromium refuses to expose DevTools remote debugging on a browser launched
against the real default profile directory (confirmed on both Chrome and Edge
-- a built-in restriction with no override flag). So this tool does not use
Playwright/CDP at all: it launches the real Chrome normally (a plain
subprocess, exactly like double-clicking it -- full access to the user's
actual signed-in Google session) and drives it purely at the OS level:
locating the window, taking screenshots, running OCR (pytesseract) to find
text, and sending real mouse clicks / keystrokes via pyautogui.

CAVEAT: element positions are found by OCR-ing the visible window, not by
inspecting a DOM, so wording/layout changes on remotedesktop.google.com can
break text matching. Adjust --*-keywords / timeouts as needed.
"""

import argparse
import ctypes
import getpass
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
import pyautogui
import pywintypes
import win32api
import win32con
import win32gui
import win32process

try:
    import pytesseract
except ImportError:
    pytesseract = None

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "log"
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEFAULT_TESSDATA_DIR = SCRIPT_DIR / "tessdata"
DEFAULT_TESSERACT_CMD = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

DEFAULT_LOGIN_KEYWORDS = ["密碼", "assword", "登入", "Sign in"]

pyautogui.PAUSE = 0.2

# --- scan-code-level keyboard input -----------------------------------------
# pyautogui.write()/press() send virtual-key (or, for unmappable characters,
# KEYEVENTF_UNICODE-"packet") keyboard input via SendInput. That's enough for
# normal local UI (e.g. typing worked fine in Chrome's own address bar), but
# was observed to silently not reach Chrome Remote Desktop's <canvas> session
# at all -- manual, real keyboard input into the exact same remote password
# field worked immediately. CRD's client JS forwards *real* key identities to
# the remote host, and low-level input consumers like this (same class of
# problem as games) are a well-known case where only KEYEVENTF_SCANCODE
# input -- which mimics actual hardware scan codes rather than a
# virtual-key/Unicode value -- gets recognized. So password/program-path
# typing goes through this instead of pyautogui.write().
_INPUT_KEYBOARD = 1
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_SCANCODE = 0x0008

# Arrow keys, Insert/Delete/Home/End/PageUp/PageDown, Windows keys, and a few
# others share their base scan code with a Numpad key (e.g. Down Arrow and
# Numpad-2 are both scan code 0x50) -- only the KEYEVENTF_EXTENDEDKEY flag
# tells the receiving end which one was meant. Forgetting it is exactly how
# wake()'s "press Down to nudge the screensaver" turned into typing a literal
# "2" over and over.
_EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D}

_ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_uint),
        ("time", ctypes.c_uint),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_uint),
        ("dwFlags", ctypes.c_uint),
        ("time", ctypes.c_uint),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_uint),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUT_UNION(ctypes.Union):
    # INPUT.type selects which of these is populated; SendInput validates the
    # whole struct's size against the real (union-sized, not just KEYBDINPUT-
    # sized) Windows INPUT struct, so this must be a real union of all three
    # variants -- a bare KEYBDINPUT-only struct undersizes it and SendInput
    # rejects the call outright with ERROR_INVALID_PARAMETER.
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint), ("u", _INPUT_UNION)]


def _send_scancode(scan, keyup=False, extended=False):
    flags = _KEYEVENTF_SCANCODE | (_KEYEVENTF_KEYUP if keyup else 0) | (_KEYEVENTF_EXTENDEDKEY if extended else 0)
    inp = _INPUT(type=_INPUT_KEYBOARD, u=_INPUT_UNION(ki=_KEYBDINPUT(0, scan, flags, 0, 0)))
    sent = ctypes.windll.user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


_SHIFT_SCANCODE = 0x2A


def _char_scancode(char):
    """(scancode, needs_shift) for char under the current keyboard layout, or
    None if it has no direct single-key mapping."""
    vk_scan = ctypes.windll.user32.VkKeyScanW(ord(char))
    if vk_scan == -1:
        return None
    vk_code = vk_scan & 0xFF
    needs_shift = bool((vk_scan >> 8) & 0x01)
    scan = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
    if scan == 0:
        return None
    return scan, needs_shift


def type_text_scancode(text, delay=0.015):
    for char in text:
        mapped = _char_scancode(char)
        if not mapped:
            continue  # no direct key mapping for this character on this layout
        scan, needs_shift = mapped
        if needs_shift:
            _send_scancode(_SHIFT_SCANCODE)
        _send_scancode(scan)
        time.sleep(delay)
        _send_scancode(scan, keyup=True)
        if needs_shift:
            _send_scancode(_SHIFT_SCANCODE, keyup=True)
        time.sleep(delay)


def press_key_scancode(vk_code):
    """Press+release a single key by virtual-key code (for non-character keys
    like Enter/arrows) via the same scan-code path."""
    scan = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
    ext = vk_code in _EXTENDED_VKS
    _send_scancode(scan, extended=ext)
    time.sleep(0.03)
    _send_scancode(scan, keyup=True, extended=ext)


def hotkey_scancode(*vk_codes):
    """Hold each key in order, then release in reverse (e.g. Win+R)."""
    scans = [(ctypes.windll.user32.MapVirtualKeyW(vk, 0), vk in _EXTENDED_VKS) for vk in vk_codes]
    for scan, ext in scans:
        _send_scancode(scan, extended=ext)
        time.sleep(0.03)
    for scan, ext in reversed(scans):
        _send_scancode(scan, keyup=True, extended=ext)
        time.sleep(0.03)


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


def launch_chrome(url, chrome_path):
    proc = subprocess.Popen([str(chrome_path), url])
    return proc.pid


def find_window_by_pid(root_pid, timeout, log, quiet=False):
    """Find the main top-level Chrome window belonging to root_pid or one of its
    descendant processes (Chrome's browser-UI window is usually owned by the
    process we launched, but match descendants too in case of relaunch/handoff)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            family_pids = {root_pid} | {p.pid for p in psutil.Process(root_pid).children(recursive=True)}
        except psutil.NoSuchProcess:
            family_pids = {root_pid}

        best_hwnd, best_area = None, 0

        def enum_handler(hwnd, _):
            nonlocal best_hwnd, best_area
            if not win32gui.IsWindowVisible(hwnd):
                return
            if not win32gui.GetWindowText(hwnd):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid not in family_pids:
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            area = max(0, right - left) * max(0, bottom - top)
            if area > best_area:
                best_hwnd, best_area = hwnd, area

        win32gui.EnumWindows(enum_handler, None)
        if best_hwnd:
            return best_hwnd
        time.sleep(0.5)
    if not quiet:
        log.error("逾時找不到 Chrome 視窗（pid=%s）", root_pid)
    return None


def find_any_chrome_window(timeout, log):
    """Find the largest visible top-level window owned by any chrome.exe process,
    regardless of which process launched it. Needed because Chrome Remote Desktop
    is installed as a PWA here: connecting opens its own fullscreen app window,
    which is not a child process of the browser window we originally launched."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        best_hwnd, best_area = None, 0

        def enum_handler(hwnd, _):
            nonlocal best_hwnd, best_area
            if not win32gui.IsWindowVisible(hwnd):
                return
            if not win32gui.GetWindowText(hwnd):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                if psutil.Process(pid).name().lower() != "chrome.exe":
                    return
            except psutil.NoSuchProcess:
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            area = max(0, right - left) * max(0, bottom - top)
            if area > best_area:
                best_hwnd, best_area = hwnd, area

        win32gui.EnumWindows(enum_handler, None)
        if best_hwnd:
            return best_hwnd
        time.sleep(0.5)
    log.error("逾時找不到任何 Chrome 視窗")
    return None


class ChromeWindow:
    """Wraps the launched Chrome process's main window, re-resolving the HWND
    whenever it goes stale (Chrome replaces its initial window during startup,
    which invalidates any handle captured too early). Falls back to matching any
    chrome.exe window once the original process's window disappears -- e.g. when
    Chrome Remote Desktop's installed PWA opens its own fullscreen app window for
    the connected session."""

    def __init__(self, pid, log):
        self.pid = pid
        self.log = log
        self.hwnd = None

    def ensure(self, timeout=20):
        if self.hwnd and win32gui.IsWindow(self.hwnd):
            return self.hwnd
        self.hwnd = (find_window_by_pid(self.pid, min(timeout, 5), self.log, quiet=True)
                     or find_any_chrome_window(timeout, self.log))
        if not self.hwnd:
            raise RuntimeError("找不到 Chrome 視窗")
        return self.hwnd

    def rect(self):
        hwnd = self.ensure()
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return left, top, right - left, bottom - top

    def is_fullscreen(self):
        """True if the window covers the whole screen with no window chrome
        (Chrome's own Fullscreen API state, not just maximized) -- compares
        the window rect against the actual monitor resolution."""
        _, _, width, height = self.rect()
        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        return width >= screen_w and height >= screen_h

    def ensure_fullscreen(self):
        """Win+R (and any other key meant for the remote session) only reaches
        the remote screen while CRD's viewer is in true fullscreen -- outside
        of it, Windows itself intercepts Win+R locally instead of forwarding
        it. F11 toggles fullscreen, so only press it when not already there."""
        self.activate()
        if not self.is_fullscreen():
            self.log.info("目前非全螢幕模式，按 F11 進入全螢幕")
            press_key_scancode(0x7A)  # VK_F11
            time.sleep(1)
            self.activate()

    def activate(self):
        """Windows blocks a background process from stealing keyboard focus via a
        plain SetForegroundWindow call (the "foreground lock") -- a silent no-op
        failure that was letting mouse clicks land on the Chrome window (clicks
        use absolute screen coordinates, so they don't need focus first) while
        all typed keystrokes kept going to whatever window actually still held
        focus (e.g. the terminal driving this script), not Chrome. Work around
        it the standard way: temporarily attach this thread's input queue to
        the current foreground window's thread, which makes SetForegroundWindow
        succeed for real."""
        hwnd = self.ensure()
        win32gui.ShowWindow(hwnd, 3)  # SW_MAXIMIZE

        fg_hwnd = win32gui.GetForegroundWindow()
        current_thread_id = win32api.GetCurrentThreadId()
        fg_thread_id = win32process.GetWindowThreadProcessId(fg_hwnd)[0] if fg_hwnd else None
        attached = False
        if fg_thread_id and fg_thread_id != current_thread_id:
            try:
                win32process.AttachThreadInput(current_thread_id, fg_thread_id, True)
                attached = True
            except pywintypes.error:
                pass
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        except pywintypes.error:
            pass
        finally:
            if attached:
                win32process.AttachThreadInput(current_thread_id, fg_thread_id, False)
        time.sleep(0.5)

    def screenshot(self):
        left, top, width, height = self.rect()
        image = pyautogui.screenshot(region=(left, top, width, height))
        return image, left, top

    def click_center(self):
        left, top, width, height = self.rect()
        pyautogui.click(left + width // 2, top + height // 2)

    def jiggle_click(self, x, y):
        """A plain instant click has been observed to not reliably register on
        the remote end -- the CRD canvas forwards input over WebRTC and seems
        to need an actual preceding mouse-move to pick up a click at all, not
        just land-and-click. Move near the target first, then click it."""
        pyautogui.moveTo(x - 20, y - 20, duration=0.1)
        pyautogui.moveTo(x, y, duration=0.1)
        pyautogui.click(x, y)

    def wake(self):
        """A single click doesn't reliably dismiss a Windows screensaver on the
        remote end -- it typically needs actual mouse movement, and clicking
        dead-center risked repeatedly landing on the user avatar tile itself
        (which sits at vertical-center on the lock screen) rather than revealing
        the password box below it. Jiggle the mouse, click below-center instead,
        then tap a real (non-modifier) key too -- an arrow key so that if it
        lands after a password field is already focused, it can't corrupt
        whatever's typed into it the way a letter or Space would."""
        left, top, width, height = self.rect()
        cx, cy = left + width // 2, top + int(height * 0.55)
        self.jiggle_click(cx, cy)
        press_key_scancode(0x28)  # VK_DOWN


def ocr_lines(image, tesseract_cmd=None):
    """Runs OCR at PSM 6 (single uniform text block) directly on the raw
    screenshot -- no grayscale/contrast/upscale preprocessing. Testing against
    real captures found no preprocessing combination (grayscale+autocontrast,
    with or without 4x/5x upscale) was consistently better than the others at
    picking up small low-contrast Latin UI text (e.g. a lock-screen "Password"
    placeholder) -- which one worked varied screenshot to screenshot, and
    plain raw RGB at native resolution did as well as any of them while being
    the cheapest by far. Runs separately per language (eng, then chi_tra) and
    merges results -- a combined "chi_tra+eng" pass is both much slower and
    less accurate for this kind of small UI text than two single-language
    passes."""
    if pytesseract is None:
        raise RuntimeError("pytesseract/Pillow 未安裝，請執行: pip install pytesseract pillow")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    lines = {}
    for lang in ("eng", "chi_tra"):
        data = pytesseract.image_to_data(image, lang=lang, config="--psm 6", output_type=pytesseract.Output.DICT)
        n = len(data["text"])
        for i in range(n):
            word = data["text"][i].strip()
            if not word:
                continue
            key = (lang, data["block_num"][i], data["par_num"][i], data["line_num"][i])
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            entry = lines.setdefault(key, {"words": [], "left": x, "top": y, "right": x + w, "bottom": y + h})
            entry["words"].append(word)
            entry["left"] = min(entry["left"], x)
            entry["top"] = min(entry["top"], y)
            entry["right"] = max(entry["right"], x + w)
            entry["bottom"] = max(entry["bottom"], y + h)
    return list(lines.values())


def find_line_center(lines, keywords):
    """Like ocr_find_text_center, but against an already-computed ocr_lines()
    result -- lets a caller that already ran OCR this iteration (to decide
    which branch to take) reuse it to locate a click target instead of paying
    for a second OCR pass."""
    for line in lines:
        text = " ".join(line["words"]).lower()
        if any(k.lower() in text for k in keywords):
            cx = (line["left"] + line["right"]) // 2
            cy = (line["top"] + line["bottom"]) // 2
            return cx, cy
    return None


def ocr_find_text_center(image, keyword, tesseract_cmd=None):
    return find_line_center(ocr_lines(image, tesseract_cmd), [keyword])


def ocr_contains_any(image, keywords, tesseract_cmd=None):
    if not keywords:
        return False
    for line in ocr_lines(image, tesseract_cmd):
        text = " ".join(line["words"]).lower()
        if any(k.lower() in text for k in keywords):
            return True
    return False


def wait_and_click_text(win, keyword, timeout, poll_interval, tesseract_cmd, log):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        win.activate()
        image, left, top = win.screenshot()
        found = ocr_find_text_center(image, keyword, tesseract_cmd)
        if found:
            x, y = found
            pyautogui.click(left + x, top + y)
            return True
        time.sleep(poll_interval)
    log.error("逾時找不到文字：%s", keyword)
    return False


def wait_for_any_text(win, keywords, timeout, poll_interval, tesseract_cmd, log):
    if not keywords:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        win.activate()
        image, _, _ = win.screenshot()
        if ocr_contains_any(image, keywords, tesseract_cmd):
            return True
        time.sleep(poll_interval)
    return False


def connect_and_login(win, windows_password, login_keywords, timeout, poll_interval, tesseract_cmd, log):
    """Single polling loop covering the whole post-click sequence: read the
    current on-screen state each iteration and act on it directly, rather than
    running separate fixed stages. Handles, in any order/combination:
      - a login screen -- Windows password entered, then done
      - a screensaver / still-connecting / anything else -- wake the remote
        screen (mouse jiggle + click + arrow key) and keep polling
    Returns "login" (password sent), or None on timeout.

    NOTE: PIN-box handling and CRD "Disconnect"-toolbar detection are
    intentionally not implemented here (both were removed, not just
    disabled): "Disconnect" belongs to the local browser chrome and can
    appear while connected regardless of what the remote screen is actually
    showing (still connecting / screensaver / login), so treating it as proof
    of "already at the desktop" was a false-positive risk; PIN entry was
    permanently disabled per this tool's actual usage (this computer is
    configured not to require one)."""
    deadline = time.monotonic() + timeout
    iteration = 0
    while time.monotonic() < deadline:
        iteration += 1
        remaining = deadline - time.monotonic()
        win.activate()
        image, left, top = win.screenshot()
        lines = ocr_lines(image, tesseract_cmd)
        seen_text = " | ".join(" ".join(l["words"]) for l in lines)[:300]
        log.info("[connect_and_login #%d] 剩餘 %.0fs，OCR 內容：%s", iteration, remaining, seen_text or "(空)")

        if any(k.lower() in seen_text.lower() for k in login_keywords):
            log.info("[connect_and_login #%d] 偵測到登入畫面關鍵字，輸入 Windows 密碼", iteration)
            # win.click_center() lands dead-center, which on a real Windows
            # lock screen is often the user-avatar tile, not the password box
            # sitting below it -- click the actual matched text's position
            # instead so the click reliably focuses the input field.
            found = find_line_center(lines, login_keywords)
            if found:
                x, y = found
                win.jiggle_click(left + x, top + y)
            else:
                win.wake()
            time.sleep(2)
            win.activate()
            type_text_scancode(windows_password)
            debug_path = LOG_DIR / "debug_after_password_typed.png"
            after_image, _, _ = win.screenshot()
            after_image.save(debug_path)
            log.info("已輸入密碼（尚未送出），除錯截圖：%s", debug_path)
            press_key_scancode(0x0D)  # VK_RETURN
            log.info("已送出 Windows 密碼")
            time.sleep(5)
            return "login"

        log.info("[connect_and_login #%d] 未偵測到已知狀態，執行喚醒動作", iteration)
        win.wake()
        time.sleep(poll_interval)
    log.error("[connect_and_login] 逾時")
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--computer-name", required=True, help="Chrome Remote Desktop 遠端電腦顯示名稱")
    parser.add_argument("--pin", help="CRD PIN；未提供則互動輸入（不會顯示在畫面上）")
    parser.add_argument("--windows-password", help="遠端電腦 Windows 登入密碼；未提供則互動輸入")
    parser.add_argument("--program-path", required=True, help="登入後透過 Win+R 執行的完整路徑或指令")
    parser.add_argument("--chrome-path", default=str(CHROME_PATH), help="chrome.exe 完整路徑")
    parser.add_argument("--tesseract-cmd", default=str(DEFAULT_TESSERACT_CMD) if DEFAULT_TESSERACT_CMD.is_file() else None,
                         help="tesseract.exe 完整路徑（不在 PATH 時指定）")
    parser.add_argument("--tessdata-dir", default=str(DEFAULT_TESSDATA_DIR) if DEFAULT_TESSDATA_DIR.is_dir() else None,
                         help="tessdata 目錄（含 chi_tra.traineddata / eng.traineddata）；"
                              "預設用 src/chrome-remote-desktop/tessdata/（需自行下載，不隨repo提供，見 README）")
    parser.add_argument("--login-keywords", default=",".join(DEFAULT_LOGIN_KEYWORDS),
                         help="OCR 判斷『已到 Windows 登入畫面』的關鍵字，逗號分隔")
    parser.add_argument("--desktop-keywords", default="",
                         help="OCR 判斷『已進桌面』的關鍵字，逗號分隔；留空則只用 --post-login-wait 固定等待")
    parser.add_argument("--connect-timeout", type=float, default=30, help="等待電腦清單出現、尋找 --computer-name 的逾時秒數")
    parser.add_argument("--session-timeout", type=float, default=60, help="等待連線建立（出現 Disconnect 按鈕）的逾時秒數")
    parser.add_argument("--login-timeout", type=float, default=60, help="等待 Windows 登入畫面出現的逾時秒數")
    parser.add_argument("--desktop-timeout", type=float, default=60, help="等待桌面出現的逾時秒數（僅在有 --desktop-keywords 時使用）")
    parser.add_argument("--post-login-wait", type=float, default=8, help="送出密碼後、開始判斷桌面前的固定等待秒數")
    parser.add_argument("--post-launch-wait", type=float, default=5, help="執行完程式後、斷線前的固定等待秒數")
    parser.add_argument("--poll-interval", type=float, default=2, help="OCR 輪詢間隔秒數")
    parser.add_argument("--pause-before", choices=["connect", "pin", "launch", "disconnect"],
                         help="在指定步驟前暫停等待按 Enter，方便對照實際畫面調整"
                              "（\"pin\" 是連線/PIN/登入合併迴圈開始前的唯一暫停點）")
    args = parser.parse_args()

    ctypes.windll.user32.SetProcessDPIAware()

    log = setup_logger()

    if args.tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = args.tessdata_dir

    pin = args.pin or getpass.getpass("CRD PIN: ")
    windows_password = args.windows_password or getpass.getpass("Windows 密碼: ")
    login_keywords = [k.strip() for k in args.login_keywords.split(",") if k.strip()]
    desktop_keywords = [k.strip() for k in args.desktop_keywords.split(",") if k.strip()]

    def pause_if(step):
        if args.pause_before == step:
            input(f"[pause-before={step}] 對照畫面確認後按 Enter 繼續...")

    log.info("啟動 Chrome：%s", args.chrome_path)
    pid = launch_chrome("https://remotedesktop.google.com/access", args.chrome_path)

    win = ChromeWindow(pid, log)
    try:
        win.ensure(timeout=20)
    except RuntimeError:
        sys.exit(1)
    win.activate()
    pyautogui.press("esc")  # dismiss any "restore pages?" infobar left over from a previous force-close
    log.info("Chrome 視窗已就緒")

    # remotedesktop.google.com's SPA content area is often still blank right after
    # navigation completes; one reload reliably renders the device list.
    time.sleep(2)
    win.click_center()
    pyautogui.press("f5")
    time.sleep(3)

    pause_if("connect")

    log.info("尋找遠端電腦：%s", args.computer_name)
    if not wait_and_click_text(win, args.computer_name, args.connect_timeout, args.poll_interval, args.tesseract_cmd, log):
        sys.exit(1)

    # Selecting a computer may open Chrome Remote Desktop's installed PWA as a
    # brand-new (often fullscreen) window while the original tab window stays
    # alive but hidden behind it -- force a fresh window search so we don't keep
    # screenshotting the now-stale original window.
    win.hwnd = None

    pause_if("pin")

    # One combined loop covers everything from here to a usable desktop: the
    # remote screen may need a screensaver-wake nudge (possibly more than
    # once) before anything useful renders, and once it does, the connection
    # is expected to land on the Windows login screen. connect_and_login()
    # re-reads the actual on-screen state every iteration and reacts to
    # whatever it currently sees, rather than assuming a fixed sequence.
    total_timeout = args.session_timeout + args.login_timeout
    log.info("等待連線並判斷畫面狀態（逾時 %ss）", total_timeout)
    outcome = connect_and_login(win, windows_password, login_keywords,
                                 total_timeout, args.poll_interval, args.tesseract_cmd, log)
    if outcome is None:
        log.error("逾時：無法判斷連線/登入狀態")
        sys.exit(1)
    if outcome == "login":
        time.sleep(args.post_login_wait)
        if desktop_keywords:
            log.info("等待桌面出現（OCR，逾時 %ss）", args.desktop_timeout)
            if not wait_for_any_text(win, desktop_keywords, args.desktop_timeout, args.poll_interval, args.tesseract_cmd, log):
                log.warning("OCR 逾時未偵測到桌面關鍵字，仍繼續執行程式")

    pause_if("launch")

    win.ensure_fullscreen()

    log.info("送出 Win+R 並執行程式：%s", args.program_path)
    win.click_center()
    hotkey_scancode(0x5B, 0x52)  # VK_LWIN, VK_R
    time.sleep(1)
    type_text_scancode(args.program_path)
    press_key_scancode(0x0D)  # VK_RETURN

    time.sleep(args.post_launch_wait)

    pause_if("disconnect")

    log.info("斷線")
    win.activate()
    left, top, _, _ = win.rect()
    pyautogui.moveTo(left + 50, top + 50)
    time.sleep(1)
    if not wait_and_click_text(win, "Disconnect", 10, 1, args.tesseract_cmd, log):
        log.warning("找不到 Disconnect 按鈕，改用 Ctrl+W 關閉分頁")
        pyautogui.hotkey("ctrl", "w")

    log.info("完成")


if __name__ == "__main__":
    main()

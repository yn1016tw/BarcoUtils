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
import json
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

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

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


def kill_existing_chrome(log):
    """Terminate any already-running chrome.exe before launching a fresh one.
    Without this, launching Chrome while a process from an earlier
    interrupted/crashed run is still alive just opens a new tab in that
    existing instance -- and if a leftover tab is still showing a connected,
    fullscreen CRD session (e.g. from a run that got killed mid-flow), that
    stale window is the LARGEST visible chrome.exe window on screen, so
    find_any_chrome_window() picks it over the freshly opened device-list
    tab. The whole script then drives the wrong remote session from the very
    first step. Confirmed live: a stale fullscreen "James NB" CRD session
    survived an earlier interrupted run and got selected instead of the
    intended target on every subsequent run, until the process was killed."""
    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == "chrome.exe":
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if killed:
        log.info("結束 %d 個殘留的 chrome.exe 程序", killed)
        time.sleep(1)


def clear_crash_flag(log):
    """Patch Chrome's Preferences file so it doesn't think last run crashed.
    Whenever Chrome is killed abruptly (force-closed, or the machine shuts
    down mid-run) rather than exiting cleanly, it records exit_type=Crashed.
    The NEXT launch then auto-restores the previous session's tabs -- and if
    one of those tabs was a live, fullscreen Chrome Remote Desktop session
    (its URL literally encodes the session id), the restore reconnects
    straight into THAT specific remote session instead of showing a fresh
    device list. Confirmed live: this is what silently landed the script in
    an old "James NB" session instead of the intended target, before any of
    this script's own window/OCR logic even ran. kill_existing_chrome() alone
    doesn't fix this -- it only helps if a stale process/window is still
    around; the crash flag itself persists across launches until cleared, so
    the very next interrupted run reintroduces the same bug. Best-effort:
    does a plain text substitution rather than a full JSON parse/rewrite to
    avoid any risk of corrupting the rest of this large, sensitive file."""
    pref_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data" / "Default" / "Preferences"
    if not pref_path.is_file():
        return
    try:
        text = pref_path.read_text(encoding="utf-8")
        patched = text.replace('"exit_type":"Crashed"', '"exit_type":"Normal"')
        patched = patched.replace('"exited_cleanly":false', '"exited_cleanly":true')
        if patched != text:
            pref_path.write_text(patched, encoding="utf-8")
            log.info("已清除 Chrome 當機還原標記")
    except OSError as e:
        log.warning("無法修改 Chrome Preferences（%s），略過", e)


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

    def _fullscreen_status(self):
        """(is_fullscreen, window_width, window_height, screen_width,
        screen_height) -- broken out from is_fullscreen() so callers that
        want to log/debug the raw numbers (not just the boolean) can, without
        querying rect()/GetSystemMetrics() a second time themselves."""
        _, _, width, height = self.rect()
        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        return width >= screen_w and height >= screen_h, width, height, screen_w, screen_h

    def is_fullscreen(self):
        """True if the window covers the whole screen with no window chrome
        (Chrome's own Fullscreen API state, not just maximized) -- compares
        the window rect against the actual monitor resolution."""
        is_fs, *_ = self._fullscreen_status()
        return is_fs

    def _save_debug_screenshot(self, name):
        """Best-effort debug screenshot -- never raises, since this is only
        ever called from a diagnostic path and shouldn't itself break the
        caller."""
        try:
            image, _, _ = self.screenshot()
            path = LOG_DIR / name
            image.save(path)
            self.log.info("除錯截圖：%s", path)
        except Exception as e:
            self.log.warning("無法儲存除錯截圖（%s）", e)

    def ensure_fullscreen(self, max_attempts=3):
        """Win+R (and any other key meant for the remote session) only reaches
        the remote screen while CRD's viewer is in true fullscreen -- outside
        of it, Windows itself intercepts Win+R locally instead of forwarding
        it. F11 toggles fullscreen, so only press it when not already there.

        Retries and re-verifies fullscreen status after each attempt instead
        of pressing F11 once and assuming it worked -- confirmed live: at a
        forced low resolution (1024x768, from booting with the monitor
        powered off) a single F11 press + 1s wait wasn't reliably enough, and
        the caller went ahead and sent Win+R anyway while still NOT
        fullscreen, so it never reached the remote session at all. Logs the
        raw window/screen dimensions on every attempt (not just the yes/no
        result) plus a debug screenshot whenever F11 is about to be pressed
        or the final attempt still failed -- root cause wasn't nailed down
        yet (candidates: GPU falls back to a software/basic display driver
        with no monitor attached, slowing Chrome's fullscreen transition;
        GetSystemMetrics not matching what Chrome can actually render to at a
        virtual/fallback resolution; a focus race between activate() and the
        F11 keypress), so this is meant to make the next occurrence
        diagnosable from the log + screenshots alone. Returns True if
        fullscreen was confirmed, False if it gave up after `max_attempts`
        (caller should treat that as "Win+R likely won't reach the remote")."""
        self.activate()
        for attempt in range(1, max_attempts + 1):
            is_fs, width, height, screen_w, screen_h = self._fullscreen_status()
            self.log.info("[ensure_fullscreen #%d/%d] 視窗尺寸=%dx%d 螢幕解析度=%dx%d 全螢幕=%s",
                           attempt, max_attempts, width, height, screen_w, screen_h, is_fs)
            if is_fs:
                return True
            self.log.info("目前非全螢幕模式，按 F11 進入全螢幕")
            self._save_debug_screenshot(f"debug_fullscreen_attempt{attempt}.png")
            press_key_scancode(0x7A)  # VK_F11
            time.sleep(1.5)
            self.activate()
        is_fs, width, height, screen_w, screen_h = self._fullscreen_status()
        self.log.info("[ensure_fullscreen 最終] 視窗尺寸=%dx%d 螢幕解析度=%dx%d 全螢幕=%s",
                       width, height, screen_w, screen_h, is_fs)
        if not is_fs:
            self.log.warning("多次嘗試後仍非全螢幕模式，Win+R 可能無法送達遠端")
            self._save_debug_screenshot("debug_fullscreen_failed.png")
            return False
        return True

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

    def wake(self, settle_wait=2):
        """A single click doesn't reliably dismiss a Windows screensaver on the
        remote end -- it typically needs actual mouse movement, and clicking
        dead-center risked repeatedly landing on the user avatar tile itself
        (which sits at vertical-center on the lock screen) rather than revealing
        the password box below it. Jiggle the mouse, click below-center instead,
        then tap a real (non-modifier) key too -- an arrow key so that if it
        lands after a password field is already focused, it can't corrupt
        whatever's typed into it the way a letter or Space would.

        `settle_wait`: seconds to wait (then reactivate the window) after the
        click+keypress, for a caller about to act on the result immediately
        (e.g. type a password next). Pass 0 to skip -- callers that already
        have their own wait afterward (a poll loop's fixed interval, or the
        next iteration's own win.activate()) should do that, so wake()'s
        default doesn't silently stack an extra 2s on top of a wait that was
        already there before wake() grew this built-in settle step."""
        left, top, width, height = self.rect()
        cx, cy = left + width // 2, top + int(height * 0.55)
        self.jiggle_click(cx, cy)
        press_key_scancode(0x28)  # VK_DOWN
        if settle_wait:
            time.sleep(settle_wait)
            self.activate()


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
            entry = lines.setdefault(key, {"words": [], "left": x, "top": y, "right": x + w, "bottom": y + h,
                                            "confs": []})
            entry["words"].append(word)
            entry["left"] = min(entry["left"], x)
            entry["top"] = min(entry["top"], y)
            entry["right"] = max(entry["right"], x + w)
            entry["bottom"] = max(entry["bottom"], y + h)
            conf = data["conf"][i]
            if isinstance(conf, (int, float)) and conf >= 0:
                entry["confs"].append(conf)
    result = list(lines.values())
    for entry in result:
        confs = entry.pop("confs")
        entry["conf"] = sum(confs) / len(confs) if confs else 0.0
    return result


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
    iteration = 0
    last_lines = []
    while time.monotonic() < deadline:
        iteration += 1
        win.activate()
        image, left, top = win.screenshot()
        lines = ocr_lines(image, tesseract_cmd)
        last_lines = lines
        seen_text = " | ".join(" ".join(l["words"]) for l in lines)[:300]
        log.info("[wait_and_click_text #%d] 尋找 %r，OCR 內容：%s", iteration, keyword, seen_text or "(空)")
        found = find_line_center(lines, [keyword])
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


def _text_overlap_ratio(box, lines, min_words=3, min_conf=70):
    """Fraction of box's area covered by OCR-recognized text line boxes --
    but only lines that look like genuine legible text (at least `min_words`
    words AND average OCR confidence >= `min_conf`) count. Confirmed live
    (visual-training capture of a real, on-screen password field): OCR
    attempting to read the blurry "Password" placeholder itself produces a
    handful of garbled, low-confidence tokens (e.g. "h..ass\\qmrd", "il", "-")
    whose bounding box happens to cover almost the entire input field -- if
    counted, that would make find_input_box() reject the field it's supposed
    to find. A real notification/label (e.g. CRD's local "Your desktop is
    currently shared with .../Stop Sharing" bar) reads as several legible,
    higher-confidence words instead, which is what this is meant to catch."""
    bx, by, bw, bh = box
    box_area = bw * bh
    if box_area == 0 or not lines:
        return 0.0
    overlap_total = 0
    for line in lines:
        if len(line["words"]) < min_words or line.get("conf", 0) < min_conf:
            continue
        ix0, iy0 = max(bx, line["left"]), max(by, line["top"])
        ix1, iy1 = min(bx + bw, line["right"]), min(by + bh, line["bottom"])
        if ix1 > ix0 and iy1 > iy0:
            overlap_total += (ix1 - ix0) * (iy1 - iy0)
    return overlap_total / box_area


# All absolute-pixel geometry in _analyze_boxes()/find_input_box() (min_width,
# the dilation kernel size) was tuned against real captures at this screen
# width. Confirmed live: booting with the monitor powered off made Windows
# fall back to 1024x768, and the login attempt failed completely (39
# iterations, 0 candidates ever detected) -- the un-scaled 180px min_width
# alone already doesn't mean anything at that resolution: a real password box
# there is only ~160px wide (scaled down from the ~601px-wide box measured at
# 3840), comfortably BELOW the un-scaled floor tuned for 3840. Rather than
# hardcode a lookup table per known resolution, every absolute-pixel value is
# scaled by the actual screenshot's width relative to this reference -- the
# screenshot width already tells us the current resolution directly, no
# separate detection needed.
_REFERENCE_SCREEN_WIDTH = 3840


def _analyze_boxes(image, min_width=180, min_height_ratio=0.015, max_height_ratio=0.06):
    """Shared contour-detection step for find_input_box() and the visual
    training logger (run_visual_training()): returns every contour that passes
    the basic size/aspect geometry filter, with its raw metrics -- NOT yet
    filtered by fill_ratio/corner count/text overlap, so training data can
    show every candidate a frame produced, not just the one that would have
    been picked under the current thresholds.

    A live CRD screenshot is a compressed video frame, not a crisp local
    capture -- confirmed by testing against a deliberately blurred +
    low-quality-JPEG-recompressed copy of a real login screenshot (simulating
    WebRTC degradation): the box's border breaks into several disconnected
    edge fragments instead of one closed rectangle outline, so a small
    dilation (kernel=3, iterations=1) isn't enough to bridge them back into a
    single contour -- kernel=5/iterations=3 was needed to reliably close the
    shape again without over-merging into neighboring elements (kernel=7+
    started merging the box with the avatar photo above it). Both `min_width`
    and the dilation kernel size are scaled to the actual screenshot
    resolution -- see _REFERENCE_SCREEN_WIDTH's comment above."""
    if cv2 is None or np is None:
        return []
    arr = np.array(image.convert("L"))
    h, w = arr.shape
    scale = w / _REFERENCE_SCREEN_WIDTH
    scaled_min_width = max(1, round(min_width * scale))
    kernel_size = max(3, round(5 * scale))
    edges = cv2.Canny(arr, 50, 150)
    edges = cv2.dilate(edges, np.ones((kernel_size, kernel_size), np.uint8), iterations=3)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    min_h = h * min_height_ratio
    max_h = h * max_height_ratio
    candidates = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw < scaled_min_width or not (min_h <= ch <= max_h):
            continue
        if cw / ch < 3:  # input fields are much wider than tall
            continue
        box_area = cw * ch
        if box_area == 0:
            continue
        # cv2.contourArea() is the area enclosed BY the traced path, not the
        # area of the stroke itself -- for a real box border (whether traced
        # as the outer or inner edge of the rectangle outline) this is close
        # to the full bounding-box area, NOT small. A low ratio instead means
        # a jagged/irregular contour (text fragments, gradient noise, etc.) --
        # not a clean box. Verified against a real captured login screen: the
        # genuine password field's contour has fill_ratio ~0.93-0.95 when
        # sharp, but drops to ~0.53 on a blur/compression-degraded copy of the
        # same screenshot (heavier dilation partially fills the shape but not
        # all the way).
        fill_ratio = cv2.contourArea(c) / box_area
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        candidates.append({
            "x": x, "y": y, "w": cw, "h": ch,
            "aspect": cw / ch,
            "fill_ratio": fill_ratio,
            "corners": len(approx),
        })
    return candidates


def find_input_box(image, lines=None, min_width=180, min_height_ratio=0.015, max_height_ratio=0.06,
                    max_text_overlap=0.6, min_fill_ratio=0.35):
    """Detect a text-input-field-shaped rectangle (wide, short, bordered box) via
    classic edge/contour detection -- a fallback signal for "this is a login
    screen" for when OCR can't read the password placeholder text at all.
    Confirmed live: on one real login screen OCR only ever picked up the
    account's display name, never the configured login keywords, even though
    the password input box itself was clearly visible on screen -- so text
    matching alone timed out without ever attempting the password.

    `lines` (an ocr_lines() result for the same image, if available) is used to
    reject candidates that overlap actual OCR-recognized text: also confirmed
    live, without this check the CRD toolbar's own local "Your desktop is
    currently shared with ... / Stop Sharing" notification bar -- itself a
    wide, short, bordered box -- was mistaken for the password field, so the
    password got typed and Enter sent into nothing, leaving the remote screen
    stuck on the account-tile login screen. A genuine empty input field has no
    full-sentence text (at most a faint placeholder), so any candidate whose
    area is mostly covered by recognized text is almost certainly a label,
    notification, or button instead.

    Returns the box's center (x, y) in image-local coordinates (same space as
    OCR coordinates -- add the window's left/top to get screen coordinates),
    or None if cv2/numpy aren't installed or no matching box is found."""
    if cv2 is None or np is None:
        return None
    best = None
    for c in _analyze_boxes(image, min_width, min_height_ratio, max_height_ratio):
        if c["fill_ratio"] < min_fill_ratio:
            continue
        if not (4 <= c["corners"] <= 8):
            continue
        box = (c["x"], c["y"], c["w"], c["h"])
        if _text_overlap_ratio(box, lines) > max_text_overlap:
            continue
        if best is None or c["w"] > best["w"]:
            best = c
    if best is None:
        return None
    return (best["x"] + best["w"] // 2, best["y"] + best["h"] // 2)


def run_visual_training(win, tesseract_cmd, log, output_dir, poll_interval, duration=None):
    """Passive-leaning data-collection loop: repeatedly screenshots the current
    window, runs OCR + box-candidate analysis, and logs every frame's raw
    numbers (JSONL, one record per frame) plus the screenshot itself. Meant to
    be run against a real remote login screen to build up a dataset of real
    screen states for tuning find_input_box()'s thresholds, instead of
    guessing from a handful of manually-captured reference images (which is
    how the kernel/fill_ratio constants in _analyze_boxes()/find_input_box()
    were originally, imprecisely, tuned).

    Never types anything (no real password risk), but DOES call win.wake() on
    EVERY frame, not just when no input box has been detected -- confirmed
    live: leaving several multi-second iterations in a row with zero real
    input reaching the remote (which happens whenever detection already found
    what it needed and had no reason to click/wake) let the remote's login
    screen time out and revert to the lock/screensaver view before the loop
    got a chance to act, even though the password box had just been detected.
    Also confirmed live: a plain mouse move alone does NOT reset the remote's
    inactivity timer -- wake()'s keyboard event (Down arrow, safe to send even
    into an already-focused text field) is what actually matters, so there's
    no safe way to keep the remote alive without it. No cap on the number of
    wake attempts: unlike connect_and_login(), this loop has no fixed timeout
    to race against, so stop it with Ctrl+C (or --visual-training-duration)
    once it's done its job, same as any other long-running observation tool.

    Runs until `duration` seconds elapse, or indefinitely (until Ctrl+C) if
    `duration` is None."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "frames.jsonl"
    log.info("視覺 training 模式啟動，輸出目錄：%s（%s，Ctrl+C 可隨時中止）", output_dir,
              "手動 Ctrl+C 結束" if duration is None else f"{duration:.0f} 秒後自動結束")
    deadline = time.monotonic() + duration if duration else None
    index = 0
    try:
        while deadline is None or time.monotonic() < deadline:
            index += 1
            win.activate()
            image, left, top = win.screenshot()
            lines = ocr_lines(image, tesseract_cmd)
            seen_text = " | ".join(" ".join(l["words"]) for l in lines)
            candidates = _analyze_boxes(image)
            for c in candidates:
                box = (c["x"], c["y"], c["w"], c["h"])
                c["text_overlap"] = round(_text_overlap_ratio(box, lines), 3)
                c["fill_ratio"] = round(c["fill_ratio"], 3)
                c["aspect"] = round(c["aspect"], 2)
            chosen = find_input_box(image, lines)

            log.info("[visual-training #%d] 執行喚醒動作（%s）", index,
                      "未偵測到輸入框" if chosen is None else "維持遠端連線 keep-alive")
            win.wake(settle_wait=0)  # loop's own time.sleep(poll_interval) + next iteration's win.activate() already cover this
            woke = True

            img_name = f"frame_{index:04d}.png"
            image.save(output_dir / img_name)
            record = {
                "index": index,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "image": img_name,
                "ocr_text": seen_text,
                "ocr_line_count": len(lines),
                "candidates": candidates,
                "chosen_input_box": chosen,
                "woke": woke,
            }
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            log.info("[visual-training #%d] OCR行數=%d 候選框=%d 選中=%s",
                      index, len(lines), len(candidates), chosen)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        log.info("視覺 training 模式手動中止")
    log.info("視覺 training 結束，共 %d 張畫面，資料存於：%s", index, output_dir)


def connect_and_login(win, windows_password, login_keywords, timeout, tesseract_cmd, log):
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
        win.wake(settle_wait=2)
        image, left, top = win.screenshot()
        lines = ocr_lines(image, tesseract_cmd)
        seen_text = " | ".join(" ".join(l["words"]) for l in lines)[:300]
        log.info("[connect_and_login #%d] 剩餘 %.0fs，OCR 內容：%s", iteration, remaining, seen_text or "(空)")
        win.wake(settle_wait=2)
        
        # Restored as a real detection basis (OR'd with find_input_box()) for
        # the actual login run -- OCR keyword match and visual box detection
        # are independent signals with different failure modes (OCR misses
        # when the placeholder text isn't legible; the visual detector misses
        # on states it hasn't been tuned against), so either one finding the
        # login screen is enough to act.
        keyword_match = any(k.lower() in seen_text.lower() for k in login_keywords)
        input_box = find_input_box(image, lines)
        if input_box:
            log.info("[connect_and_login #%d] 偵測到輸入框視覺特徵，位置 %s", iteration, input_box)
        if keyword_match:
            log.info("[connect_and_login #%d] OCR 命中登入關鍵字", iteration)

        if keyword_match or input_box:
            log.info("[connect_and_login #%d] 偵測到登入畫面，輸入 Windows 密碼", iteration)
            # win.click_center() lands dead-center, which on a real Windows
            # lock screen is often the user-avatar tile, not the password box
            # sitting below it -- click the actual matched text's position
            # instead so the click reliably focuses the input field. If OCR
            # didn't match any keyword, fall back to the detected input box's
            # position instead.
            found = find_line_center(lines, login_keywords) if keyword_match else None
            x, y = found if found else input_box
            win.jiggle_click(left + x, top + y)
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
        
    log.error("[connect_and_login] 逾時")
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--computer-name", required=True, help="Chrome Remote Desktop 遠端電腦顯示名稱")
    parser.add_argument("--windows-password", help="遠端電腦 Windows 登入密碼；未提供則互動輸入")
    parser.add_argument("--program-path", help="登入後透過 Win+R 執行的完整路徑或指令（--visual-training 模式下不需要）")
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
    parser.add_argument("--visual-training", action="store_true",
                         help="視覺 training 模式：連線並進入全螢幕後，不斷擷取畫面、"
                              "記錄 OCR 與 find_input_box() 候選框的原始特徵數值到 "
                              "log/visual_training/<時間戳記>/frames.jsonl（連同每張截圖），"
                              "全程不點擊、不輸入密碼、不執行程式；用於收集真實畫面資料，"
                              "作為之後調整視覺判斷參數的依據。搭配 --visual-training-duration "
                              "指定秒數自動結束，不指定則需 Ctrl+C 手動中止")
    parser.add_argument("--visual-training-duration", type=float, default=None,
                         help="--visual-training 模式自動結束的秒數；不指定則需手動 Ctrl+C")
    args = parser.parse_args()

    if not args.visual_training and not args.program_path:
        parser.error("--program-path 為必填（--visual-training 模式除外）")

    ctypes.windll.user32.SetProcessDPIAware()

    log = setup_logger()
    screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    log.info("目前螢幕解析度：%dx%d", screen_w, screen_h)

    if args.tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = args.tessdata_dir

    windows_password = None if args.visual_training else (args.windows_password or getpass.getpass("Windows 密碼: "))
    login_keywords = [k.strip() for k in args.login_keywords.split(",") if k.strip()]
    desktop_keywords = [k.strip() for k in args.desktop_keywords.split(",") if k.strip()]

    def pause_if(step):
        if args.pause_before == step:
            input(f"[pause-before={step}] 對照畫面確認後按 Enter 繼續...")

    kill_existing_chrome(log)
    clear_crash_flag(log)

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
    # IMPORTANT: do NOT click_center() here just to focus the window before F5 --
    # confirmed by live testing that if the device list has already rendered by
    # this point, a dead-center click lands directly on whichever device tile is
    # there and connects to it (observed: silently connected to the wrong
    # computer). win.activate() (called above) already gives keyboard focus
    # without touching page content, which is all F5 needs.
    time.sleep(2)
    win.activate()
    pyautogui.press("f5")
    time.sleep(3)

    pause_if("connect")

    log.info("尋找遠端電腦：%s", args.computer_name)
    if not wait_and_click_text(win, args.computer_name, args.connect_timeout, args.poll_interval, args.tesseract_cmd, log):
        sys.exit(1)

    # Give the remote session a moment to actually establish/render before
    # starting to act on it -- confirmed live: the first couple of frames
    # right after selecting the computer are still the connecting/blank
    # transition state (no password box exists yet at all), which is
    # legitimately "no box detected" but not a useful signal either way.
    log.info("已連線，等待 15 秒讓遠端畫面穩定後再開始偵測")
    time.sleep(15)
    
    # Selecting a computer may open Chrome Remote Desktop's installed PWA as a
    # brand-new (often fullscreen) window while the original tab window stays
    # alive but hidden behind it -- force a fresh window search so we don't keep
    # screenshotting the now-stale original window.
    win.hwnd = None

    # Make sure the remote session is fullscreen as early as possible, right
    # after the new CRD viewer window appears -- the OCR-based login/wake loop
    # below screenshots this window's rect, and outside of Chrome's Fullscreen
    # API state (F11), Windows intercepts special keys like Win+R locally
    # instead of forwarding them to the remote session.
    win.ensure_fullscreen()

    pause_if("pin")

    if args.visual_training:
        training_dir = LOG_DIR / "visual_training" / datetime.now().strftime("%Y%m%d_%H%M%S")
        run_visual_training(win, args.tesseract_cmd, log, training_dir, args.poll_interval,
                             args.visual_training_duration)
    else:
        # One combined loop covers everything from here to a usable desktop: the
        # remote screen may need a screensaver-wake nudge (possibly more than
        # once) before anything useful renders, and once it does, the connection
        # is expected to land on the Windows login screen. connect_and_login()
        # re-reads the actual on-screen state every iteration and reacts to
        # whatever it currently sees, rather than assuming a fixed sequence.
        total_timeout = args.session_timeout + args.login_timeout
        log.info("等待連線並判斷畫面狀態（逾時 %ss）", total_timeout)
        outcome = connect_and_login(win, windows_password, login_keywords,
                                     total_timeout, args.tesseract_cmd, log)
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

        if not win.ensure_fullscreen():
            # Sending Win+R (and the program path + Enter that follow it)
            # while NOT confirmed fullscreen risks it landing on whatever
            # local window has focus instead of the remote session -- could
            # open a local Run dialog and execute an arbitrary command on
            # THIS machine instead of the remote one. Abort rather than risk
            # that, now that ensure_fullscreen() actually verifies success.
            log.error("無法進入全螢幕，中止送出 Win+R（避免誤送到本機）")
            sys.exit(1)

        log.info("送出 Win+R 並執行程式：%s", args.program_path)
        win.click_center()
        hotkey_scancode(0x5B, 0x52)  # VK_LWIN, VK_R
        time.sleep(1)
        type_text_scancode(args.program_path)
        press_key_scancode(0x0D)  # VK_RETURN

        time.sleep(args.post_launch_wait)

    pause_if("disconnect")

    log.info("斷線：先離開全螢幕再關閉 Chrome")
    win.activate()
    if win.is_fullscreen():
        press_key_scancode(0x7A)  # VK_F11
        time.sleep(1)
    kill_existing_chrome(log)
    clear_crash_flag(log)

    log.info("完成")


if __name__ == "__main__":
    main()

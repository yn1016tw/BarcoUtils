import subprocess
from datetime import datetime
from pathlib import Path

FFMPEG_DEFAULT = r"C:\Tools\ffmpeg\bin\ffmpeg.exe"
SCRCPY_DEFAULT = r"C:\Tools\scrcpy-win64-v3.3.3\scrcpy.exe"


def screenshot_host_desktop(output_dir: str, round_num: int) -> str | None:
    try:
        from PIL import ImageGrab
        ts = datetime.now().strftime("%H%M%S")
        path = str(Path(output_dir) / "files" / f"round{round_num:02d}_{ts}_desktop.png")
        ImageGrab.grab().save(path)
        print(f"  Host desktop screenshot: {path}")
        return path
    except Exception as e:
        print(f"  [WARN] Host desktop screenshot failed: {e}")
        return None


def screenshot_for_debug(ui, output_dir: str, round_num: int) -> None:
    ts = datetime.now().strftime("%H%M%S")
    path = str(Path(output_dir) / "files" / f"round{round_num:02d}_{ts}_fail.png")
    try:
        ui.screenshot(path)
        print(f"  Debug screenshot: {path}")
    except Exception:
        pass


def start_recording(output_dir: str, ffmpeg_path: str) -> "subprocess.Popen | None":
    if not Path(ffmpeg_path).exists():
        print(f"[WARN] ffmpeg not found at {ffmpeg_path} — screen recording skipped")
        return None
    ts = datetime.now().strftime("%H%M%S")
    out = str(Path(output_dir) / "files" / f"desktop_{ts}.mp4")
    try:
        proc = subprocess.Popen(
            [
                ffmpeg_path,
                "-f", "gdigrab",
                "-framerate", "30",
                "-i", "desktop",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                out,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"  Recording desktop → {out}")
        return proc
    except Exception as e:
        print(f"[WARN] Could not start ffmpeg: {e}")
        return None


def _get_host_resolution() -> "tuple[int, int]":
    import ctypes
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def start_ui_with_scrcpy(serial: str, scrcpy_path: str = SCRCPY_DEFAULT) -> "subprocess.Popen | None":
    if not Path(scrcpy_path).exists():
        print(f"[WARN] scrcpy not found at {scrcpy_path} — UI mirror skipped")
        return None
    sw, sh = _get_host_resolution()
    w, h = sw // 2, sh // 2
    cmd = [
        scrcpy_path, "--serial", serial,
        "--window-x", "10", "--window-y", "50",
        "--window-width", str(w), "--window-height", str(h),
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  scrcpy started for {serial}  window={w}x{h} @10,50")
        return proc
    except Exception as e:
        print(f"[WARN] Could not start scrcpy: {e}")
        return None


def stop_recording(proc: "subprocess.Popen | None") -> None:
    if proc is None:
        return
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=15)
    except Exception:
        proc.kill()

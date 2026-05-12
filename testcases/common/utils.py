import subprocess
from datetime import datetime
from pathlib import Path

FFMPEG_DEFAULT = r"C:\Tools\ffmpeg\bin\ffmpeg.exe"


def screenshot(ui, output_dir: str, round_num: int) -> None:
    ts = datetime.now().strftime("%H%M%S")
    path = str(Path(output_dir) / "files" / f"round{round_num:02d}_{ts}.png")
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


def stop_recording(proc: "subprocess.Popen | None") -> None:
    if proc is None:
        return
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=15)
    except Exception:
        proc.kill()

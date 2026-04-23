"""
Camera/Mic/Speaker Boot Time Test for Duvel
Measures time from reboot to Camera (any UVC), Mic, and Speaker ready.
Supports USB serial or IP connection. Supports stress testing.

Camera check : v4l2-ctl --all -d <dev>  (capability 0x04200001 = VIDEO_CAPTURE+STREAMING)
Audio check  : tinymix -a               (mixer responds = mic+speaker accessible)

Usage:
    python test_logi_rally_boot_time.py --serial ABC123 --iterations 5
    python test_logi_rally_boot_time.py --ip 192.168.1.100 --iterations 3
    python test_logi_rally_boot_time.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs
"""

import argparse
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# v4l2 capability flag: VIDEO_CAPTURE (0x1) + EXT_PIX_FORMAT (0x200) + STREAMING (0x4000000)
_VIDEO_CAPTURE_CAP = "0x04200001"
_POLL_INTERVAL = 2  # seconds between polls


# ---------------------------------------------------------------------------
# DuvelDevice
# ---------------------------------------------------------------------------

class DuvelDevice:
    def __init__(self, serial: str, is_ip: bool):
        self._serial = serial      # e.g. "ABC123" or "192.168.1.100:5555"
        self._is_ip = is_ip

    @property
    def label(self) -> str:
        return self._serial

    def connect(self) -> None:
        if self._is_ip:
            result = self._adb_raw(["connect", self._serial], timeout=10)
            out = result.stdout.strip()
            if "connected" not in out.lower() and "already" not in out.lower():
                raise ConnectionError(f"adb connect failed: {out}")
            print(f"  [ADB] Connected to {self._serial}")
        else:
            result = self._adb_raw(["devices"], timeout=10)
            if self._serial not in result.stdout:
                raise ConnectionError(f"Device {self._serial} not found in adb devices")
            print(f"  [ADB] USB device {self._serial} found")

    def disconnect(self) -> None:
        if self._is_ip:
            self._adb_raw(["disconnect", self._serial], timeout=5)

    def reboot(self) -> None:
        self._adb(["reboot"], timeout=10)
        deadline = time.time() + 30
        while time.time() < deadline:
            result = self._adb_raw(["get-state"], timeout=3)
            if result.returncode != 0 or "device" not in result.stdout:
                return
            time.sleep(1)

    def wait_for_boot(self, timeout: int) -> None:
        """Mirror TEnTo wait_for_base_unit_running():
        1. wait-for-device
        2. sys.boot_completed == 1
        3. init.svc.bootanim == stopped
        4. pm list packages responds
        """
        deadline = time.time() + timeout

        # Step 1: ADB detects device
        remaining = max(1, int(deadline - time.time()))
        result = self._adb_raw(["wait-for-device"], timeout=remaining)
        if result.returncode != 0:
            raise TimeoutError("Device not detected by ADB within timeout")

        # Step 2: sys.boot_completed == 1
        self._poll_until(
            lambda: self._getprop("sys.boot_completed") == "1",
            deadline,
            "sys.boot_completed never reached 1",
        )

        # Step 3: boot animation stopped
        self._poll_until(
            lambda: self._getprop("init.svc.bootanim") == "stopped",
            deadline,
            "Boot animation never stopped",
        )

        # Step 4: package manager responds
        self._poll_until(
            lambda: self._pm_list_responds(),
            deadline,
            "Package manager never responded",
        )

    def wait_for_camera_working(self, timeout: int) -> str:
        """Wait until any UVC camera with VIDEO_CAPTURE capability is found.
        Returns the device path (e.g. /dev/video7).
        Uses v4l2-ctl --all to verify actual capture capability, not just node presence.
        """
        found = [None]

        def check():
            dev = self._find_working_camera()
            if dev:
                found[0] = dev
                return True
            return False

        self._poll_until(check, time.time() + timeout, "No working camera found within timeout")
        return found[0]

    def wait_for_audio_working(self, timeout: int) -> str:
        """Wait until audio mixer (mic+speaker) responds via tinymix.
        Returns the card name found.
        """
        found = [None]

        def check():
            card = self._find_working_audio()
            if card:
                found[0] = card
                return True
            return False

        self._poll_until(check, time.time() + timeout, "No working audio device found within timeout")
        return found[0]

    # ------------------------------------------------------------------
    # Camera helpers
    # ------------------------------------------------------------------

    def _find_working_camera(self) -> str | None:
        """Returns first /dev/videoX that has VIDEO_CAPTURE+STREAMING capability."""
        # List all video nodes
        result = self._adb_raw(["shell", "ls /dev/video*"], timeout=5)
        if result.returncode != 0 or not result.stdout.strip():
            return None

        for line in result.stdout.strip().splitlines():
            dev = line.strip()
            if not dev.startswith("/dev/video"):
                continue
            if self._camera_can_capture(dev):
                return dev
        return None

    def _camera_can_capture(self, dev: str) -> bool:
        """Check if device reports VIDEO_CAPTURE+STREAMING capability via v4l2-ctl."""
        result = self._adb_raw(["shell", f"v4l2-ctl --all -d {dev}"], timeout=8)
        if result.returncode != 0:
            return False
        output = result.stdout
        # Check capabilities line, e.g.: "Capabilities  : 0x04200001"
        for line in output.splitlines():
            if "capabilities" in line.lower() and _VIDEO_CAPTURE_CAP in line.lower():
                return True
        return False

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    def _find_working_audio(self) -> str | None:
        """Returns audio card name if tinymix responds, else None."""
        # Check /proc/asound/cards for connected audio devices
        result = self._adb_raw(["shell", "cat /proc/asound/cards"], timeout=5)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        lines = result.stdout.strip().splitlines()
        if not lines or "no soundcards" in result.stdout.lower():
            return None

        # Find first external card (skip card 0 which is usually internal)
        card_index = None
        card_name = None
        for line in lines:
            parts = line.split()
            if parts and parts[0].isdigit():
                idx = int(parts[0])
                # Prefer non-zero card index (external USB audio)
                if idx > 0:
                    card_index = idx
                    card_name = " ".join(parts[2:]) if len(parts) > 2 else f"card{idx}"
                    break
                elif card_index is None:
                    card_index = idx
                    card_name = " ".join(parts[2:]) if len(parts) > 2 else f"card{idx}"

        if card_index is None:
            return None

        # Verify tinymix can actually talk to the card
        result = self._adb_raw(["shell", f"tinymix -D {card_index} -a"], timeout=8)
        if result.returncode == 0 and result.stdout.strip():
            return card_name
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _poll_until(self, condition, deadline: float, timeout_msg: str) -> None:
        while time.time() < deadline:
            try:
                if condition():
                    return
            except Exception:
                pass
            time.sleep(_POLL_INTERVAL)
        raise TimeoutError(timeout_msg)

    def _getprop(self, prop: str) -> str:
        result = self._adb(["shell", "getprop", prop], timeout=5)
        return result.stdout.strip()

    def _pm_list_responds(self) -> bool:
        result = self._adb_raw(["shell", "pm", "list", "packages", "-f"], timeout=10)
        return result.returncode == 0 and "package:" in result.stdout

    def _adb(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        result = self._adb_raw(args, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def _adb_raw(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        prefix = ["-s", self._serial] if self._serial else []
        cmd = ["adb"] + prefix + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )


# ---------------------------------------------------------------------------
# TestResult
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    round_num: int
    total_rounds: int
    reboot_start: float = 0.0
    boot_ready: float | None = None
    camera_ready: float | None = None   # first working camera found
    audio_ready: float | None = None    # mic+speaker mixer responds
    camera_device: str | None = None    # e.g. /dev/video7
    audio_card: str | None = None       # e.g. "Rally"
    error: str | None = None
    passed: bool = False

    def total_seconds(self) -> float | None:
        if self.audio_ready and self.reboot_start:
            return self.audio_ready - self.reboot_start
        return None

    def boot_seconds(self) -> float | None:
        if self.boot_ready and self.reboot_start:
            return self.boot_ready - self.reboot_start
        return None

    def camera_seconds(self) -> float | None:
        if self.camera_ready and self.boot_ready:
            return self.camera_ready - self.boot_ready
        return None

    def audio_seconds(self) -> float | None:
        if self.audio_ready and self.boot_ready:
            return self.audio_ready - self.boot_ready
        return None


# ---------------------------------------------------------------------------
# ResultWriter
# ---------------------------------------------------------------------------

class ResultWriter:
    def __init__(self, total_rounds: int, device_label: str):
        self._total = total_rounds
        self._device_label = device_label
        self._run_start = datetime.now()

    def print_round(self, r: TestResult) -> None:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n[Round {r.round_num}/{self._total}] {status}")
        if r.error:
            print(f"  ERROR: {r.error}")

        def ts(t):
            return datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-3] if t else "N/A"

        def diff(t, base, label=""):
            if t and base:
                return f"  (+{t - base:.1f}s{' ' + label if label else ''})"
            return ""

        cam_label = f" [{r.camera_device}]" if r.camera_device else ""
        aud_label = f" [{r.audio_card}]" if r.audio_card else ""

        print(f"  Reboot triggered   : {ts(r.reboot_start)}")
        print(f"  Boot ready         : {ts(r.boot_ready)}{diff(r.boot_ready, r.reboot_start)}")
        print(f"  Camera working     : {ts(r.camera_ready)}{diff(r.camera_ready, r.boot_ready, 'from boot')}{cam_label}")
        print(f"  Audio working      : {ts(r.audio_ready)}{diff(r.audio_ready, r.boot_ready, 'from boot')}{aud_label}")
        total = r.total_seconds()
        print(f"  Total (reboot→audio): {total:.1f}s" if total else "  Total              : N/A")

    def print_summary(self, results: list[TestResult]) -> None:
        passed = [r for r in results if r.passed]
        print(f"\n{'=' * 60}")
        print(f"=== Summary ({len(passed)}/{len(results)} PASS) ===")

        def stats(values):
            v = [x for x in values if x is not None]
            if not v:
                return "N/A"
            if len(v) == 1:
                return f"{v[0]:.1f}s"
            return f"{min(v):.1f}s / {statistics.mean(v):.1f}s / {max(v):.1f}s"

        print(f"  Total time    min/avg/max: {stats([r.total_seconds() for r in passed])}")
        print(f"  Boot time     min/avg/max: {stats([r.boot_seconds() for r in passed])}")
        print(f"  Camera ready  min/avg/max: {stats([r.camera_seconds() for r in passed])}")
        print(f"  Audio ready   min/avg/max: {stats([r.audio_seconds() for r in passed])}")
        print(f"{'=' * 60}")

    def _format_lines(self, results: list[TestResult]) -> list[str]:
        lines = []
        lines.append("=" * 80)
        lines.append(
            f"Test Run: {self._run_start.strftime('%Y-%m-%d %H:%M:%S')} "
            f"| Device: {self._device_label} | Iterations: {self._total}"
        )
        lines.append("=" * 80)
        lines.append("")

        for r in results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"[Round {r.round_num}/{self._total}] {status}")
            if r.error:
                lines.append(f"  ERROR: {r.error}")

            def ts(t):
                return datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-3] if t else "N/A"

            def diff(t, base, label=""):
                if t and base:
                    return f"  (+{t - base:.1f}s{' ' + label if label else ''})"
                return ""

            cam_label = f" [{r.camera_device}]" if r.camera_device else ""
            aud_label = f" [{r.audio_card}]" if r.audio_card else ""

            lines.append(f"  Reboot triggered   : {ts(r.reboot_start)}")
            lines.append(f"  Boot ready         : {ts(r.boot_ready)}{diff(r.boot_ready, r.reboot_start)}")
            lines.append(f"  Camera working     : {ts(r.camera_ready)}{diff(r.camera_ready, r.boot_ready, 'from boot')}{cam_label}")
            lines.append(f"  Audio working      : {ts(r.audio_ready)}{diff(r.audio_ready, r.boot_ready, 'from boot')}{aud_label}")
            total = r.total_seconds()
            lines.append(f"  Total (reboot→audio): {total:.1f}s" if total else "  Total              : N/A")
            lines.append("")

        passed = [r for r in results if r.passed]

        def stats(values):
            v = [x for x in values if x is not None]
            if not v:
                return "N/A"
            if len(v) == 1:
                return f"{v[0]:.1f}s"
            return f"{min(v):.1f}s / {statistics.mean(v):.1f}s / {max(v):.1f}s"

        lines.append(f"=== Summary ({len(passed)}/{len(results)} PASS) ===")
        lines.append(f"  Total time    min/avg/max: {stats([r.total_seconds() for r in passed])}")
        lines.append(f"  Boot time     min/avg/max: {stats([r.boot_seconds() for r in passed])}")
        lines.append(f"  Camera ready  min/avg/max: {stats([r.camera_seconds() for r in passed])}")
        lines.append(f"  Audio ready   min/avg/max: {stats([r.audio_seconds() for r in passed])}")
        lines.append("")
        return lines

    def save_log(self, results: list[TestResult], output_dir: str) -> None:
        path = Path(output_dir) / (self._run_start.strftime("%Y%m%d") + ".txt")
        lines = self._format_lines(results)
        mode = "a" if path.exists() else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\n  Log saved: {path}")


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def run_one_round(device: DuvelDevice, round_num: int, total_rounds: int, args) -> TestResult:
    r = TestResult(round_num=round_num, total_rounds=total_rounds)
    print(f"\n{'─' * 60}")
    print(f"Round {round_num}/{total_rounds} — rebooting device...")

    try:
        r.reboot_start = time.time()
        device.reboot()

        print("  Waiting for boot...")
        device.wait_for_boot(args.boot_timeout)
        r.boot_ready = time.time()
        print(f"  Boot ready  (+{r.boot_seconds():.1f}s)")

        print("  Waiting for camera (v4l2-ctl capability check)...")
        r.camera_device = device.wait_for_camera_working(args.device_timeout)
        r.camera_ready = time.time()
        print(f"  Camera working  {r.camera_device}  (+{r.camera_seconds():.1f}s from boot)")

        print("  Waiting for audio/mic/speaker (tinymix check)...")
        r.audio_card = device.wait_for_audio_working(args.device_timeout)
        r.audio_ready = time.time()
        print(f"  Audio working  [{r.audio_card}]  (+{r.audio_seconds():.1f}s from boot)")

        r.passed = True

    except TimeoutError as e:
        r.error = f"TIMEOUT: {e}"
        print(f"  [TIMEOUT] {e}")
    except Exception as e:
        r.error = str(e)
        print(f"  [ERROR] {e}")

    return r


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Measure camera/mic/speaker ready time after Duvel reboot"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--serial", metavar="SERIAL", help="USB ADB serial number")
    group.add_argument("--ip", metavar="IP[:PORT]", help="ADB over TCP/IP (default port 5555)")
    parser.add_argument("--iterations", type=int, default=1, metavar="N", help="Number of test rounds (default: 1)")
    parser.add_argument("--output-dir", default=".", metavar="DIR", help="Log output directory (default: current dir)")
    parser.add_argument("--boot-timeout", type=int, default=300, metavar="SEC", help="Max seconds to wait for boot (default: 300)")
    parser.add_argument("--device-timeout", type=int, default=120, metavar="SEC", help="Max seconds to wait for camera/audio (default: 120)")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.ip:
        serial = args.ip if ":" in args.ip else f"{args.ip}:5555"
        device = DuvelDevice(serial=serial, is_ip=True)
    else:
        device = DuvelDevice(serial=args.serial, is_ip=False)

    writer = ResultWriter(total_rounds=args.iterations, device_label=device.label)
    results = []

    print("Camera/Mic/Speaker Boot Time Test")
    print(f"  Device     : {device.label}")
    print(f"  Iterations : {args.iterations}")
    print(f"  Output dir : {args.output_dir}")

    try:
        device.connect()
    except ConnectionError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    try:
        for i in range(1, args.iterations + 1):
            result = run_one_round(device, i, args.iterations, args)
            results.append(result)
            writer.print_round(result)
    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
    finally:
        if results:
            writer.print_summary(results)
            Path(args.output_dir).mkdir(parents=True, exist_ok=True)
            writer.save_log(results, args.output_dir)
        device.disconnect()


if __name__ == "__main__":
    main()

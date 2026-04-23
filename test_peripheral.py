"""
Peripheral Boot Time Test for Duvel
Measures time from reboot to Camera, Mic, and Speaker ready.
Supports USB serial or IP connection. Supports stress testing.

Camera check : v4l2-ctl --all -d <dev>  (capability 0x04200001 = VIDEO_CAPTURE+STREAMING)
Audio check  : tinymix -a               (mixer responds = mic+speaker accessible)

Usage:
    python test_peripheral.py --serial 1882000501 --iterations 5
    python test_peripheral.py --ip 192.168.1.100 --iterations 3
    python test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs
"""

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from common.duvel_device import DuvelDevice


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
    camera_name: str | None = None      # e.g. "Rally Camera"
    audio_card: str | None = None       # e.g. "RallyCamera"
    audio_name: str | None = None       # e.g. "Rally Camera"
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

        cam_label = f" [{r.camera_device}  {r.camera_name}]" if r.camera_device else ""
        aud_label = f" [{r.audio_card}  {r.audio_name}]" if r.audio_card else ""

        print(f"  Reboot triggered    : {ts(r.reboot_start)}")
        print(f"  Boot ready          : {ts(r.boot_ready)}{diff(r.boot_ready, r.reboot_start)}")
        print(f"  Camera working      : {ts(r.camera_ready)}{diff(r.camera_ready, r.boot_ready, 'from boot')}{cam_label}")
        print(f"  Audio working       : {ts(r.audio_ready)}{diff(r.audio_ready, r.boot_ready, 'from boot')}{aud_label}")
        total = r.total_seconds()
        print(f"  Total (reboot→audio): {total:.1f}s" if total else "  Total               : N/A")

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

            cam_label = f" [{r.camera_device}  {r.camera_name}]" if r.camera_device else ""
            aud_label = f" [{r.audio_card}  {r.audio_name}]" if r.audio_card else ""

            lines.append(f"  Reboot triggered    : {ts(r.reboot_start)}")
            lines.append(f"  Boot ready          : {ts(r.boot_ready)}{diff(r.boot_ready, r.reboot_start)}")
            lines.append(f"  Camera working      : {ts(r.camera_ready)}{diff(r.camera_ready, r.boot_ready, 'from boot')}{cam_label}")
            lines.append(f"  Audio working       : {ts(r.audio_ready)}{diff(r.audio_ready, r.boot_ready, 'from boot')}{aud_label}")
            total = r.total_seconds()
            lines.append(f"  Total (reboot→audio): {total:.1f}s" if total else "  Total               : N/A")
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

        print("  Waiting for camera (uvcvideo sysfs check)...")
        r.camera_device, r.camera_name = device.wait_for_camera_working(args.device_timeout)
        r.camera_ready = time.time()
        print(f"  Camera working  {r.camera_device}  {r.camera_name}  (+{r.camera_seconds():.1f}s from boot)")

        print("  Waiting for audio/mic/speaker (/proc/asound/cards check)...")
        r.audio_card, r.audio_name = device.wait_for_audio_working(args.device_timeout)
        r.audio_ready = time.time()
        print(f"  Audio working  [{r.audio_card}]  {r.audio_name}  (+{r.audio_seconds():.1f}s from boot)")

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
        description="Measure peripheral (camera/mic/speaker) ready time after Duvel reboot"
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

    print("Peripheral Boot Time Test")
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

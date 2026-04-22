"""
Logi Rally Camera Boot Time Test
Measures time from Duvel reboot to Camera/Mic/Speaker ready.
Supports USB serial or IP connection. Supports stress testing.

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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Logi Rally Camera USB vendor:product ID
_LOGI_RALLY_USB_ID = "046d:0881"
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
        # Wait until device goes offline
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

    def wait_for_logi_rally(self, timeout: int) -> None:
        self._poll_until(
            lambda: self._lsusb_has(_LOGI_RALLY_USB_ID),
            time.time() + timeout,
            f"Logi Rally USB ({_LOGI_RALLY_USB_ID}) not detected within timeout",
        )

    def wait_for_video_node(self, timeout: int) -> None:
        self._poll_until(
            lambda: self._node_exists("/dev/video*"),
            time.time() + timeout,
            "Video node /dev/video* not found within timeout",
        )

    def wait_for_audio_node(self, timeout: int) -> None:
        self._poll_until(
            lambda: self._node_exists("/dev/snd/pcmC*"),
            time.time() + timeout,
            "Audio node /dev/snd/pcmC* not found within timeout",
        )

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

    def _lsusb_has(self, usb_id: str) -> bool:
        result = self._adb_raw(["shell", "lsusb"], timeout=5)
        return usb_id in result.stdout

    def _node_exists(self, glob_path: str) -> bool:
        result = self._adb_raw(["shell", "ls", glob_path], timeout=5)
        return result.returncode == 0 and result.stdout.strip() != ""

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
    usb_detected: float | None = None
    video_ready: float | None = None
    audio_ready: float | None = None
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

    def usb_seconds(self) -> float | None:
        if self.usb_detected and self.boot_ready:
            return self.usb_detected - self.boot_ready
        return None

    def video_seconds(self) -> float | None:
        if self.video_ready and self.usb_detected:
            return self.video_ready - self.usb_detected
        return None

    def audio_seconds(self) -> float | None:
        if self.audio_ready and self.usb_detected:
            return self.audio_ready - self.usb_detected
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

        print(f"  Reboot triggered   : {ts(r.reboot_start)}")
        print(f"  Boot ready         : {ts(r.boot_ready)}{diff(r.boot_ready, r.reboot_start)}")
        print(f"  Logi Rally USB     : {ts(r.usb_detected)}{diff(r.usb_detected, r.boot_ready, 'from boot')}")
        print(f"  Video node ready   : {ts(r.video_ready)}{diff(r.video_ready, r.usb_detected)}")
        print(f"  Audio node ready   : {ts(r.audio_ready)}{diff(r.audio_ready, r.usb_detected)}")
        total = r.total_seconds()
        print(f"  Total              : {total:.1f}s" if total else "  Total              : N/A")

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

        print(f"  Total time   min/avg/max: {stats([r.total_seconds() for r in passed])}")
        print(f"  Boot time    min/avg/max: {stats([r.boot_seconds() for r in passed])}")
        print(f"  USB detect   min/avg/max: {stats([r.usb_seconds() for r in passed])}")
        print(f"  Video ready  min/avg/max: {stats([r.video_seconds() for r in passed])}")
        print(f"  Audio ready  min/avg/max: {stats([r.audio_seconds() for r in passed])}")
        print(f"{'=' * 60}")

    def save_log(self, results: list[TestResult], output_dir: str) -> None:
        path = Path(output_dir) / (self._run_start.strftime("%Y%m%d") + ".txt")
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

            lines.append(f"  Reboot triggered   : {ts(r.reboot_start)}")
            lines.append(f"  Boot ready         : {ts(r.boot_ready)}{diff(r.boot_ready, r.reboot_start)}")
            lines.append(f"  Logi Rally USB     : {ts(r.usb_detected)}{diff(r.usb_detected, r.boot_ready, 'from boot')}")
            lines.append(f"  Video node ready   : {ts(r.video_ready)}{diff(r.video_ready, r.usb_detected)}")
            lines.append(f"  Audio node ready   : {ts(r.audio_ready)}{diff(r.audio_ready, r.usb_detected)}")
            total = r.total_seconds()
            lines.append(f"  Total              : {total:.1f}s" if total else "  Total              : N/A")
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
        lines.append(f"  Total time   min/avg/max: {stats([r.total_seconds() for r in passed])}")
        lines.append(f"  Boot time    min/avg/max: {stats([r.boot_seconds() for r in passed])}")
        lines.append(f"  USB detect   min/avg/max: {stats([r.usb_seconds() for r in passed])}")
        lines.append(f"  Video ready  min/avg/max: {stats([r.video_seconds() for r in passed])}")
        lines.append(f"  Audio ready  min/avg/max: {stats([r.audio_seconds() for r in passed])}")
        lines.append("")

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

        print("  Waiting for Logi Rally USB...")
        device.wait_for_logi_rally(args.device_timeout)
        r.usb_detected = time.time()
        print(f"  USB detected  (+{r.usb_seconds():.1f}s from boot)")

        print("  Waiting for video node...")
        device.wait_for_video_node(args.device_timeout)
        r.video_ready = time.time()
        print(f"  Video ready  (+{r.video_seconds():.1f}s)")

        print("  Waiting for audio node...")
        device.wait_for_audio_node(args.device_timeout)
        r.audio_ready = time.time()
        print(f"  Audio ready  (+{r.audio_seconds():.1f}s)")

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
        description="Measure Logi Rally Camera ready time after Duvel reboot"
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

    print(f"Logi Rally Boot Time Test")
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

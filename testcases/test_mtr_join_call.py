"""
MTR Join-Call Test for Duvel
Reboots the device, waits for boot, then verifies the Teams Rooms join-by-ID
flow end-to-end with per-step timing.

Steps:
  1. Reboot device
  2. Wait for boot complete
  3. Wait for Teams Rooms main page to appear
  4. Tap "Join with an ID"
  5. Verify the join-with-ID dialog is visible
  6. Enter meeting ID (and optional passcode)
  7. Tap "Join Teams meeting"
  8. Verify in-call screen is visible
  9. Save a screenshot
  10. Hang up the call

Meeting info can be provided manually or loaded from teams_meeting_host.py:

  Manual:
    python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-id 123456789
    python testcases/test_mtr_join_call.py --serial 1882000501 --meeting-id 123456789 --passcode abc123
    python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-id 123456789 --iterations 3

  From teams_meeting_host.py (reads meeting_info.json written by the host):
    python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-info-dir C:/logs
    python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-info-dir C:/logs --meeting-info-timeout 180
    python testcases/test_mtr_join_call.py --ip 192.168.1.100 --meeting-info-dir C:/logs --iterations 5

  Default meeting-info path (logs/ next to script):
    python testcases/test_mtr_join_call.py --serial 1882000501 --from-host
    python testcases/test_mtr_join_call.py --ip 192.168.1.100 --from-host
"""

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from common.duvel_device import DuvelDevice
from common.version import VERSION
from common.teams_meeting_host import MeetingInfo

_JOIN_PAGE_TIMEOUT = 30   # seconds to wait for join-with-ID dialog after tapping button
_IN_CALL_TIMEOUT   = 60   # seconds to wait for in-call screen after tapping Join


# ---------------------------------------------------------------------------
# TestResult
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    round_num: int
    total_rounds: int
    reboot_start: float = 0.0
    boot_ready: float | None = None
    main_visible: float | None = None
    join_id_tapped: float | None = None
    join_page_visible: float | None = None
    join_tapped: float | None = None
    in_call_visible: float | None = None
    screenshot_saved: float | None = None
    call_ended: float | None = None
    barco_fw_version: str | None = None
    screenshot_path: str | None = None
    error: str | None = None
    passed: bool = False

    def boot_seconds(self) -> float | None:
        if self.boot_ready and self.reboot_start:
            return self.boot_ready - self.reboot_start
        return None

    def main_seconds(self) -> float | None:
        if self.main_visible and self.boot_ready:
            return self.main_visible - self.boot_ready
        return None

    def in_call_seconds(self) -> float | None:
        if self.in_call_visible and self.boot_ready:
            return self.in_call_visible - self.boot_ready
        return None

    def total_seconds(self) -> float | None:
        if self.screenshot_saved and self.reboot_start:
            return self.screenshot_saved - self.reboot_start
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
        for line in self._format_round_lines(r):
            print(line)

    def print_summary(self, results: list[TestResult]) -> None:
        passed = sum(r.passed for r in results)
        print(f"\n{'=' * 60}")
        print(f"=== Summary ({passed}/{len(results)} PASS) ===")
        for line in self._format_summary_lines(results):
            print(line)
        print(f"{'=' * 60}")

    def save_log(self, results: list[TestResult], output_dir: str) -> None:
        path = Path(output_dir) / f"{self._run_start.strftime('%Y%m%d')}.log"
        lines = self._format_lines(results)
        mode = "a" if path.exists() else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\n  Log saved: {path}")

    @staticmethod
    def _ts(t: float | None) -> str:
        return datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-3] if t else "N/A"

    @staticmethod
    def _diff(t: float | None, base: float | None, label: str = "") -> str:
        if t and base:
            return f"  (+{t - base:.1f}s{' ' + label if label else ''})"
        return ""

    def _format_round_lines(self, r: TestResult) -> list[str]:
        status = "PASS" if r.passed else "FAIL"
        lines = [f"\n[Round {r.round_num}/{self._total}] {status}"]
        if r.error:
            lines.append(f"  ERROR: {r.error}")

        def tag(t: float | None) -> str:
            return "  PASS" if t is not None else "  FAIL"

        lines.append(f"  Reboot triggered      : {self._ts(r.reboot_start)}")
        lines.append(f"  Boot ready            : {self._ts(r.boot_ready)}{self._diff(r.boot_ready, r.reboot_start)}{tag(r.boot_ready)}")
        lines.append(f"  Main page visible     : {self._ts(r.main_visible)}{self._diff(r.main_visible, r.boot_ready, 'from boot')}{tag(r.main_visible)}")
        lines.append(f"  Join ID tapped        : {self._ts(r.join_id_tapped)}{self._diff(r.join_id_tapped, r.boot_ready, 'from boot')}{tag(r.join_id_tapped)}")
        lines.append(f"  Join page visible     : {self._ts(r.join_page_visible)}{self._diff(r.join_page_visible, r.boot_ready, 'from boot')}{tag(r.join_page_visible)}")
        lines.append(f"  Join tapped           : {self._ts(r.join_tapped)}{self._diff(r.join_tapped, r.boot_ready, 'from boot')}{tag(r.join_tapped)}")
        lines.append(f"  In-call visible       : {self._ts(r.in_call_visible)}{self._diff(r.in_call_visible, r.boot_ready, 'from boot')}{tag(r.in_call_visible)}")
        lines.append(f"  Screenshot saved      : {self._ts(r.screenshot_saved)}{self._diff(r.screenshot_saved, r.boot_ready, 'from boot')}{tag(r.screenshot_saved)}")
        if r.screenshot_path:
            lines.append(f"  Screenshot path       : {r.screenshot_path}")
        lines.append(f"  Call ended            : {self._ts(r.call_ended)}{self._diff(r.call_ended, r.boot_ready, 'from boot')}{tag(r.call_ended)}")
        total = r.total_seconds()
        lines.append(f"  Total (reboot->shot)  : {total:.1f}s" if total else "  Total                 : N/A")
        return lines

    def _format_summary_lines(self, results: list[TestResult]) -> list[str]:
        def stats(values):
            v = [x for x in values if x is not None]
            if not v:
                return "N/A"
            if len(v) == 1:
                return f"{v[0]:.1f}s"
            return f"{min(v):.1f}s / {statistics.mean(v):.1f}s / {max(v):.1f}s"

        def line(label, times):
            return f"  {label}: {stats(times)}"

        return [
            line("Total time    min/avg/max", [r.total_seconds() for r in results]),
            line("Boot time     min/avg/max", [r.boot_seconds() for r in results]),
            line("Main visible  min/avg/max", [r.main_seconds() for r in results]),
            line("In-call       min/avg/max", [r.in_call_seconds() for r in results]),
        ]

    def _format_lines(self, results: list[TestResult]) -> list[str]:
        lines = [
            "=" * 80,
            f"Test Run: {self._run_start.strftime('%Y-%m-%d %H:%M:%S')} "
            f"| Device: {self._device_label} | Iterations: {self._total} | v{VERSION}"
            + (f" | FW: {results[0].barco_fw_version}" if results and results[0].barco_fw_version else ""),
            "=" * 80,
            "",
        ]
        for r in results:
            lines.extend(self._format_round_lines(r))
            lines.append("")

        passed = sum(r.passed for r in results)
        lines.append(f"=== Summary ({passed}/{len(results)} PASS) ===")
        lines.extend(self._format_summary_lines(results))
        lines.append("")
        return lines


# ---------------------------------------------------------------------------
# MtrJoinCallTestRunner
# ---------------------------------------------------------------------------

class MtrJoinCallTestRunner:
    def __init__(self, device: DuvelDevice, args):
        self._device = device
        self._args = args

    def run_round(self, round_num: int, total_rounds: int, do_reboot: bool = True) -> TestResult:
        r = TestResult(round_num=round_num, total_rounds=total_rounds)
        print(f"\n{'-' * 60}")
        if do_reboot:
            print(f"Round {round_num}/{total_rounds} - rebooting device...")
        else:
            print(f"Round {round_num}/{total_rounds} - skipping reboot")

        try:
            r.reboot_start = time.time()

            if do_reboot:
                # Step 1: Reboot
                self._device.reboot()

                # Step 2: Wait for boot
                print("  Waiting for boot...")
                self._device.wait_for_boot(self._args.boot_timeout)
                r.boot_ready = time.time()
                print(f"  Boot ready  (+{r.boot_seconds():.1f}s)")
            else:
                r.boot_ready = r.reboot_start

            r.barco_fw_version = self._device.barco_fw_version()
            ui = self._device.ui

            # Step 3: Wait for main page
            print("  Waiting for Teams Rooms main page...")
            if not ui.main.is_visible(timeout=self._args.device_timeout):
                raise TimeoutError(f"Main page not visible within {self._args.device_timeout}s")
            r.main_visible = time.time()
            print(f"  Main page visible  (+{r.main_visible - r.boot_ready:.1f}s from boot)")

            # Step 4: Tap "Join with an ID"
            print("  Tapping 'Join with an ID'...")
            if not ui.main.click_join_with_an_id():
                raise RuntimeError("Could not tap 'Join with an ID' button")
            r.join_id_tapped = time.time()
            print(f"  Join with an ID tapped  (+{r.join_id_tapped - r.boot_ready:.1f}s from boot)")

            # Step 5: Wait for join-with-ID dialog
            print("  Waiting for join-with-ID dialog...")
            if not ui.join_with_id.is_visible(timeout=_JOIN_PAGE_TIMEOUT):
                raise TimeoutError(f"Join-with-ID dialog not visible within {_JOIN_PAGE_TIMEOUT}s")
            r.join_page_visible = time.time()
            print(f"  Join dialog visible  (+{r.join_page_visible - r.boot_ready:.1f}s from boot)")

            # Step 6: Enter meeting ID (and optional passcode)
            print(f"  Entering meeting ID: {self._args.meeting_id}")
            if not ui.join_with_id.enter_meeting_id(self._args.meeting_id):
                raise RuntimeError("Could not enter meeting ID")
            if self._args.passcode:
                print(f"  Entering passcode...")
                if not ui.join_with_id.enter_passcode(self._args.passcode):
                    raise RuntimeError("Could not enter passcode")

            # Step 7: Tap Join
            print("  Tapping 'Join Teams meeting'...")
            if not ui.join_with_id.click_join():
                raise RuntimeError("Could not tap 'Join Teams meeting' button")
            r.join_tapped = time.time()
            print(f"  Join tapped  (+{r.join_tapped - r.boot_ready:.1f}s from boot)")

            # Step 8: Wait for in-call screen
            print("  Waiting for in-call screen...")
            if not ui.in_call.is_visible(timeout=_IN_CALL_TIMEOUT):
                raise TimeoutError(f"In-call screen not visible within {_IN_CALL_TIMEOUT}s")
            r.in_call_visible = time.time()
            title = ui.in_call.get_meeting_title()
            print(f"  In-call visible  (+{r.in_call_visible - r.boot_ready:.1f}s from boot)"
                  + (f"  title: {title}" if title else ""))

            # Step 9: Screenshot
            time.sleep(20)
            ts = datetime.now().strftime("%H%M%S")
            shot_path = str(Path(self._args.output_dir) / "files" / f"round{round_num:02d}_{ts}.png")
            print("  Saving screenshot...")
            ui.screenshot(shot_path)
            r.screenshot_saved = time.time()
            r.screenshot_path = shot_path
            print(f"  Screenshot saved  (+{r.screenshot_saved - r.boot_ready:.1f}s from boot)  {shot_path}")

            # Step 10: Hang up
            print("  Hanging up call...")
            ui.end_call()
            r.call_ended = time.time()
            print(f"  Call ended  (+{r.call_ended - r.boot_ready:.1f}s from boot)")
            time.sleep(5)

            r.passed = True

        except TimeoutError as e:
            r.error = f"TIMEOUT: {e}"
            print(f"  [TIMEOUT] {e}")
            _cleanup_call(self._device.ui)
            _save_debug_screenshot(self._device.ui, self._args.output_dir, round_num)
        except Exception as e:
            r.error = str(e)
            print(f"  [ERROR] {e}")
            _cleanup_call(self._device.ui)
            _save_debug_screenshot(self._device.ui, self._args.output_dir, round_num)

        return r


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cleanup_call(ui) -> None:
    try:
        ui.end_call()
        time.sleep(5)
    except Exception:
        pass


def _save_debug_screenshot(ui, output_dir: str, round_num: int) -> None:
    ts = datetime.now().strftime("%H%M%S")
    path = str(Path(output_dir) / "files" / f"round{round_num:02d}_{ts}_fail.png")
    try:
        ui.screenshot(path)
        print(f"  Debug screenshot: {path}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="MTR join-call test: reboot, boot, Teams Rooms main → Join with an ID → in-call screenshot"
    )
    dev_group = parser.add_mutually_exclusive_group(required=True)
    dev_group.add_argument("--serial", metavar="SERIAL", help="USB ADB serial number")
    dev_group.add_argument("--ip", metavar="IP[:PORT]", help="ADB over TCP/IP (default port 5555)")

    meet_group = parser.add_mutually_exclusive_group(required=True)
    meet_group.add_argument("--meeting-id", metavar="ID", help="Teams meeting ID to join")
    meet_group.add_argument(
        "--meeting-info-dir", metavar="DIR",
        help="Directory containing meeting_info.json written by teams_meeting_host.py",
    )
    meet_group.add_argument(
        "--from-host", action="store_true",
        help="Load meeting info from default path (logs/ next to this script)",
    )

    parser.add_argument("--passcode", default=None, metavar="CODE", help="Meeting passcode (used with --meeting-id; ignored when loading from host)")
    parser.add_argument("--meeting-info-timeout", type=int, default=120, metavar="SEC", help="Seconds to wait for meeting_info.json from host (default: 120)")
    parser.add_argument("--iterations", type=int, default=1, metavar="N", help="Number of test rounds (default: 1)")
    parser.add_argument("--output-dir", default=None, metavar="DIR", help="Log output directory (default: logs/ next to this script)")
    parser.add_argument("--boot-timeout", type=int, default=300, metavar="SEC", help="Max seconds to wait for boot (default: 300)")
    parser.add_argument("--device-timeout", type=int, default=120, metavar="SEC", help="Max seconds to wait for main page (default: 120)")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed round")
    return parser.parse_args()


def main():
    args = parse_args()

    date_str = datetime.now().strftime("%Y%m%d")
    if args.output_dir is None:
        args.output_dir = str(Path(__file__).parent / "logs" / Path(__file__).stem / date_str)

    # Resolve meeting ID / passcode from host JSON if requested
    if args.from_host or args.meeting_info_dir:
        info_dir = None if args.from_host else args.meeting_info_dir
        print(f"Waiting for meeting info from teams_meeting_host.py"
              f"{f' ({info_dir})' if info_dir else ''} ...")
        try:
            info = MeetingInfo.wait_for_info(info_dir, timeout=args.meeting_info_timeout)
        except TimeoutError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
        print(f"Meeting info loaded:\n{info}")
        args.meeting_id = info.meeting_id
        args.passcode = info.passcode or None

    if args.ip:
        serial = args.ip if ":" in args.ip else f"{args.ip}:5555"
        device = DuvelDevice(serial=serial, is_ip=True)
    else:
        device = DuvelDevice(serial=args.serial, is_ip=False)

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.output_dir) / "files").mkdir(parents=True, exist_ok=True)

    try:
        device.connect()
    except ConnectionError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    writer = ResultWriter(total_rounds=args.iterations, device_label=device.label)
    runner = MtrJoinCallTestRunner(device=device, args=args)

    print(f"MTR Join-Call Test  v{VERSION}")
    print(f"  Device     : {device.label}")
    print(f"  FW         : {device.barco_fw_version()}")
    print(f"  Meeting ID : {args.meeting_id}")
    if args.passcode:
        print(f"  Passcode   : {args.passcode}")
    print(f"  Iterations : {args.iterations}")
    print(f"  Output dir : {args.output_dir}")

    results = []
    do_reboot = True
    try:
        for i in range(1, args.iterations + 1):
            result = runner.run_round(i, args.iterations, do_reboot=do_reboot)
            results.append(result)
            writer.print_round(result)
            if args.fail_fast and not result.passed:
                print("\n[Stopped: --fail-fast]")
                break
            do_reboot = not result.passed
    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
    finally:
        if results:
            writer.print_summary(results)
            writer.save_log(results, args.output_dir)
        device.disconnect()


if __name__ == "__main__":
    main()

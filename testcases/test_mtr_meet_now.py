"""
MTR Meet Now Test for Duvel
Navigates to the Teams Rooms main page, taps Meet Now, and verifies the
meet-now flow end-to-end with per-step timing.

Steps:
  1. Navigate to Teams Rooms main page
  2. Tap "Meet now"
  3. Verify "Invite people" dialog is visible
  4. Dismiss the dialog
  5. Save a screenshot
  6. Hang up the meeting
  On exception: reboot and wait for boot before the next round.

Usage:
    python testcases/test_mtr_meet_now.py --ip 192.168.1.100
    python testcases/test_mtr_meet_now.py --serial 1882000501
    python testcases/test_mtr_meet_now.py --ip 192.168.1.100 --output-dir C:/logs --iterations 3

Author: James Yang <james.yang@barco.com>
"""

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from common.duvel_device import DuvelDevice
from common.logger import Logger
from common.version import VERSION
from common.utils import screenshot_for_debug

_INVITE_DIALOG_TIMEOUT = 60   # seconds to wait for invite dialog after tapping Meet now


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
    meet_now_tapped: float | None = None
    invite_visible: float | None = None
    dialog_dismissed: float | None = None
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

    def invite_seconds(self) -> float | None:
        if self.invite_visible and self.boot_ready:
            return self.invite_visible - self.boot_ready
        return None

    def total_seconds(self) -> float | None:
        if self.screenshot_saved and self.reboot_start:
            return self.screenshot_saved - self.reboot_start
        return None


# ---------------------------------------------------------------------------
# ResultWriter
# ---------------------------------------------------------------------------

class ResultWriter:
    def __init__(self, total_rounds: int, device_label: str, logger: Logger):
        self._total = total_rounds
        self._device_label = device_label
        self._logger = logger
        self._run_start = datetime.now()

    def print_round(self, r: TestResult) -> None:
        for line in self._format_round_lines(r):
            self._logger.info(line)

    def print_summary(self, results: list[TestResult]) -> None:
        passed = sum(r.passed for r in results)
        self._logger.info("=" * 60)
        self._logger.info(f"Summary ({passed}/{len(results)} PASS)")
        for line in self._format_summary_lines(results):
            self._logger.info(line)
        self._logger.info("=" * 60)

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
        lines = [f"[Round {r.round_num}/{self._total}] {status}"]
        if r.error:
            lines.append(f"  ERROR: {r.error}")

        def tag(t: float | None) -> str:
            return "  PASS" if t is not None else "  FAIL"

        lines.append(f"  Reboot triggered      : {self._ts(r.reboot_start)}")
        lines.append(f"  Boot ready            : {self._ts(r.boot_ready)}{self._diff(r.boot_ready, r.reboot_start)}{tag(r.boot_ready)}")
        lines.append(f"  Main page visible     : {self._ts(r.main_visible)}{self._diff(r.main_visible, r.boot_ready, 'from boot')}{tag(r.main_visible)}")
        lines.append(f"  Meet now tapped       : {self._ts(r.meet_now_tapped)}{self._diff(r.meet_now_tapped, r.boot_ready, 'from boot')}{tag(r.meet_now_tapped)}")
        lines.append(f"  Invite dialog visible : {self._ts(r.invite_visible)}{self._diff(r.invite_visible, r.boot_ready, 'from boot')}{tag(r.invite_visible)}")
        lines.append(f"  Dialog dismissed      : {self._ts(r.dialog_dismissed)}{self._diff(r.dialog_dismissed, r.boot_ready, 'from boot')}{tag(r.dialog_dismissed)}")
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
            line("Invite dialog min/avg/max", [r.invite_seconds() for r in results]),
        ]


# ---------------------------------------------------------------------------
# MtrMeetNowTestRunner
# ---------------------------------------------------------------------------

class MtrMeetNowTestRunner:
    def __init__(self, device: DuvelDevice, args, logger: Logger):
        self._device = device
        self._args = args
        self._logger = logger

    def run_round(self, round_num: int, total_rounds: int) -> TestResult:
        r = TestResult(round_num=round_num, total_rounds=total_rounds)
        self._logger.info("-" * 60)
        self._logger.info(f"Round {round_num}/{total_rounds}")

        try:
            r.reboot_start = time.time()
            r.boot_ready = r.reboot_start
            r.barco_fw_version = self._device.barco_fw_version()
            ui = self._device.ui

            # Step 1: Navigate to main page
            self._logger.info("Navigating to Teams Rooms main page...")
            if not ui.go_to_main_page(timeout=self._args.device_timeout):
                raise TimeoutError(f"Main page not reachable within {self._args.device_timeout}s")
            r.main_visible = time.time()
            self._logger.info(f"Main page visible  (+{r.main_visible - r.boot_ready:.1f}s)")

            # Step 2: Tap Meet now
            self._logger.info("Tapping 'Meet now'...")
            if not ui.main.click_meet_now():
                raise RuntimeError("Could not tap 'Meet now' button")
            r.meet_now_tapped = time.time()
            self._logger.info(f"Meet now tapped  (+{r.meet_now_tapped - r.boot_ready:.1f}s)")

            # Step 3: Wait for invite dialog
            self._logger.info("Waiting for 'Invite people' dialog...")
            if not ui.invite_people.is_visible(timeout=_INVITE_DIALOG_TIMEOUT):
                raise TimeoutError(f"Invite dialog not visible within {_INVITE_DIALOG_TIMEOUT}s")
            r.invite_visible = time.time()
            self._logger.info(f"Invite dialog visible  (+{r.invite_visible - r.boot_ready:.1f}s)")

            # Step 4: Dismiss dialog
            self._logger.info("Dismissing invite dialog...")
            if not ui.invite_people.dismiss():
                raise RuntimeError("Could not dismiss invite dialog")
            r.dialog_dismissed = time.time()
            self._logger.info(f"Dialog dismissed  (+{r.dialog_dismissed - r.boot_ready:.1f}s)")
            if ui.invite_people.is_visible():
                raise RuntimeError("Invite dialog still visible after dismiss")

            # Step 5: Screenshot
            time.sleep(5)
            ts = datetime.now().strftime("%H%M%S")
            shot_path = str(Path(self._args.output_dir) / "files" / f"round{round_num:02d}_{ts}.png")
            self._logger.info("Taking screenshot...")
            ui.screenshot(shot_path)
            r.screenshot_saved = time.time()
            r.screenshot_path = shot_path
            self._logger.info(f"Screenshot saved  (+{r.screenshot_saved - r.boot_ready:.1f}s)  {shot_path}")

            # Step 6: Hang up
            self._logger.info("Hanging up meeting...")
            ui.end_call()
            r.call_ended = time.time()
            self._logger.info(f"Call ended  (+{r.call_ended - r.boot_ready:.1f}s)")
            time.sleep(5)

            r.passed = True

        except TimeoutError as e:
            r.error = f"TIMEOUT: {e}"
            self._logger.error("TIMEOUT: %s", e)
            _cleanup_call(self._device.ui)
            screenshot_for_debug(self._device.ui, self._args.output_dir, round_num)
            _reboot_device(self._device, self._args.boot_timeout, self._logger)
        except Exception as e:
            r.error = str(e)
            self._logger.error("ERROR: %s", e)
            _cleanup_call(self._device.ui)
            screenshot_for_debug(self._device.ui, self._args.output_dir, round_num)
            _reboot_device(self._device, self._args.boot_timeout, self._logger)

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


def _reboot_device(device: DuvelDevice, boot_timeout: int, logger: Logger) -> None:
    try:
        logger.info("Rebooting device after failure...")
        device.reboot()
        device.wait_for_boot(boot_timeout)
        logger.info("Boot ready.")
    except Exception as e:
        logger.warning("Reboot failed: %s", e)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="MTR Meet Now test: navigate to Teams Rooms main → Meet now → screenshot"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--serial", metavar="SERIAL", help="USB ADB serial number")
    group.add_argument("--ip", metavar="IP[:PORT]", help="ADB over TCP/IP (default port 5555)")
    parser.add_argument("--iterations", type=int, default=1, metavar="N", help="Number of test rounds (default: 1)")
    parser.add_argument("--output-dir", default=None, metavar="DIR", help="Log output directory (default: logs/ next to this script)")
    parser.add_argument("--boot-timeout", type=int, default=300, metavar="SEC", help="Max seconds to wait for boot (default: 300)")
    parser.add_argument("--device-timeout", type=int, default=120, metavar="SEC", help="Max seconds to wait for main page (default: 120)")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed round")
    return parser.parse_args()


def main():
    args = parse_args()

    _now = datetime.now()
    if args.output_dir is None:
        args.output_dir = str(Path(__file__).parent / "logs" / Path(__file__).stem / _now.strftime("%Y%m%d") / _now.strftime("%H%M%S"))

    if args.ip:
        serial = args.ip if ":" in args.ip else f"{args.ip}:5555"
        device = DuvelDevice(serial=serial, is_ip=True)
    else:
        device = DuvelDevice(serial=args.serial, is_ip=False)

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.output_dir) / "files").mkdir(parents=True, exist_ok=True)

    logger = Logger(args.output_dir)

    try:
        device.connect()
    except ConnectionError as e:
        logger.error(str(e))
        sys.exit(1)

    writer = ResultWriter(total_rounds=args.iterations, device_label=device.label, logger=logger)
    runner = MtrMeetNowTestRunner(device=device, args=args, logger=logger)

    logger.info(f"MTR Meet Now Test  v{VERSION}")
    logger.info(f"  Device     : {device.label}")
    logger.info(f"  FW         : {device.barco_fw_version()}")
    logger.info(f"  Iterations : {args.iterations}")
    logger.info(f"  Output dir : {args.output_dir}")

    results = []
    try:
        for i in range(1, args.iterations + 1):
            result = runner.run_round(i, args.iterations)
            results.append(result)
            writer.print_round(result)
            if args.fail_fast and not result.passed:
                logger.info("[Stopped: --fail-fast]")
                break
    except KeyboardInterrupt:
        logger.info("[Interrupted by user]")
    finally:
        if results:
            writer.print_summary(results)
        device.disconnect()


if __name__ == "__main__":
    main()

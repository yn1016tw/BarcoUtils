"""
MTR Join-with-ID Test for Duvel

Joins a Teams meeting by ID on the Duvel MTR, takes a screenshot while
in-call, then hangs up. Desktop recording via ffmpeg runs in parallel.
Supports stress testing with configurable iterations.

Flow per round:
  1. Navigate to Teams Rooms main page
  2. Tap "Join with an ID" and enter meeting ID / passcode
  3. Wait for in-call screen
  4. Wait 15s for stream to stabilize, take device screenshot + desktop screenshot
  5. Hang up (force-stop Teams if hang_up fails)

Typical usage:
  # Terminal 1 — create meeting and auto-accept calls:
  python testcases/common/teams_meeting_host.py

  # Terminal 2 — run the test:
  python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host
  python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --from-host --iterations 5

  # With explicit meeting ID (no teams_meeting_host.py):
  python testcases/test_mtr_join_with_id.py --ip 192.168.1.100 --meeting-id 123456789
  python testcases/test_mtr_join_with_id.py --serial 1882000501 --meeting-id 123456789 --passcode abc123

Author: James Yang <james.yang@barco.com>
"""

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from common.duvel_device import DuvelDevice
from common.logger import Logger
from common.version import VERSION
from common.teams_meeting_host import MeetingInfo
from common.utils import FFMPEG_DEFAULT, screenshot_for_debug, screenshot_host_desktop, start_recording, stop_recording, start_ui_with_scrcpy

_JOIN_PAGE_TIMEOUT = 30  # seconds to wait for join-with-ID dialog
_IN_CALL_TIMEOUT   = 60  # seconds to wait for in-call screen after tapping Join


# ---------------------------------------------------------------------------
# TestResult
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    round_num: int
    total_rounds: int
    join_start: float = 0.0
    in_call_visible: float | None = None
    camera_screenshot: float | None = None
    call_ended: float | None = None
    screenshot_path: str | None = None
    error: str | None = None
    passed: bool = False

    def in_call_seconds(self) -> float | None:
        if self.in_call_visible and self.join_start:
            return self.in_call_visible - self.join_start
        return None

    def total_seconds(self) -> float | None:
        if self.call_ended and self.join_start:
            return self.call_ended - self.join_start
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
        lines.append(f"  Join started          : {self._ts(r.join_start)}")
        lines.append(f"  In-call visible       : {self._ts(r.in_call_visible)}{self._diff(r.in_call_visible, r.join_start)}")
        lines.append(f"  Camera screenshot     : {self._ts(r.camera_screenshot)}{self._diff(r.camera_screenshot, r.join_start)}")
        if r.screenshot_path:
            lines.append(f"  Screenshot path       : {r.screenshot_path}")
        lines.append(f"  Call ended            : {self._ts(r.call_ended)}{self._diff(r.call_ended, r.join_start)}")
        total = r.total_seconds()
        lines.append(f"  Total                 : {total:.1f}s" if total else "  Total                 : N/A")
        return lines


# ---------------------------------------------------------------------------
# MtrAvCallTestRunner
# ---------------------------------------------------------------------------

class MtrJoinWithIdTestRunner:
    def __init__(self, device: DuvelDevice, args, logger: Logger):
        self._device = device
        self._args = args
        self._logger = logger

    def run_round(self, round_num: int, total_rounds: int) -> TestResult:
        r = TestResult(round_num=round_num, total_rounds=total_rounds)
        self._logger.info("-" * 60)
        self._logger.info(f"Round {round_num}/{total_rounds}")

        try:
            ui = self._device.ui
            r.join_start = time.time()

            # Step 1: Navigate to Teams Rooms main page
            self._logger.info("Navigating to Teams Rooms main page...")
            if not ui.go_to_main_page(timeout=self._args.device_timeout):
                raise TimeoutError(f"Main page not reachable within {self._args.device_timeout}s")
            self._logger.info("Main page visible.")

            # Step 2: Tap "Join with an ID"
            self._logger.info("Tapping 'Join with an ID'...")
            if not ui.main.click_join_with_an_id():
                raise RuntimeError("Could not tap 'Join with an ID' button")

            # Step 3: Wait for join-with-ID dialog
            self._logger.info("Waiting for join-with-ID dialog...")
            if not ui.join_with_id.is_visible(timeout=_JOIN_PAGE_TIMEOUT):
                raise TimeoutError(f"Join-with-ID dialog not visible within {_JOIN_PAGE_TIMEOUT}s")

            # Step 4: Enter meeting credentials
            self._logger.info(f"Entering meeting ID: {self._args.meeting_id}")
            if not ui.join_with_id.enter_meeting_id(self._args.meeting_id):
                raise RuntimeError("Could not enter meeting ID")
            if self._args.passcode:
                self._logger.info("Entering passcode...")
                if not ui.join_with_id.enter_passcode(self._args.passcode):
                    raise RuntimeError("Could not enter passcode")

            # Step 5: Tap Join
            self._logger.info("Tapping 'Join Teams meeting'...")
            if not ui.join_with_id.click_join():
                raise RuntimeError("Could not tap 'Join Teams meeting' button")

            # Step 6: Wait for in-call screen
            self._logger.info("Waiting for in-call screen...")
            if not ui.in_call.is_visible(timeout=_IN_CALL_TIMEOUT):
                raise TimeoutError(f"In-call screen not visible within {_IN_CALL_TIMEOUT}s")
            r.in_call_visible = time.time()
            title = ui.in_call.get_meeting_title()
            self._logger.info(
                f"In-call visible  (+{r.in_call_seconds():.1f}s)"
                + (f"  title: {title}" if title else "")
            )

            # Step 7: Camera phase — wait 15s for stream to stabilize, then screenshot
            self._logger.info("Camera phase: waiting 15s for stream to stabilize...")
            time.sleep(15)
            ts = datetime.now().strftime("%H%M%S")
            shot_path = str(
                Path(self._args.output_dir) / "files" / f"round{round_num:02d}_{ts}_device.png"
            )
            self._logger.info("Taking screenshot...")
            ui.screenshot(shot_path)
            screenshot_host_desktop(self._args.output_dir, round_num)
            r.camera_screenshot = time.time()
            r.screenshot_path = shot_path
            self._logger.info(f"Screenshot saved: {shot_path}")

            # Step 8: Hang up on Duvel MTR
            self._logger.info("Hanging up on Duvel MTR...")
            if not ui.in_call.hang_up():
                self._logger.warning("hang_up() failed — force-stopping Teams on device")
                try:
                    ui.force_stop("com.microsoft.skype.teams.ipphone")
                except Exception:
                    pass
            r.call_ended = time.time()
            self._logger.info(f"Call ended  (total: {r.total_seconds():.1f}s)")
            r.passed = True

        except TimeoutError as e:
            r.error = f"TIMEOUT: {e}"
            self._logger.error("TIMEOUT: %s", e)
            _cleanup(self._device.ui)
            screenshot_for_debug(self._device.ui, self._args.output_dir, round_num)
        except Exception as e:
            r.error = str(e)
            self._logger.error("ERROR: %s", e)
            _cleanup(self._device.ui)
            screenshot_for_debug(self._device.ui, self._args.output_dir, round_num)

        return r


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cleanup(ui) -> None:
    try:
        ui.end_call()
        time.sleep(5)
    except Exception:
        pass




# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "MTR join-with-ID test: join a Teams meeting by ID on Duvel MTR → screenshot → hang up. "
            "Run testcases/common/teams_meeting_host.py in a separate terminal to create the "
            "meeting and auto-accept calls from the host PC."
        )
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

    parser.add_argument("--passcode", default=None, metavar="CODE",
                        help="Meeting passcode (used with --meeting-id)")
    parser.add_argument("--meeting-info-timeout", type=int, default=120, metavar="SEC",
                        help="Seconds to wait for meeting_info.json from host (default: 120)")
    parser.add_argument("--iterations", type=int, default=1, metavar="N",
                        help="Number of test rounds (default: 1)")
    parser.add_argument("--output-dir", default=None, metavar="DIR",
                        help="Log output directory (default: logs/ next to this script)")
    parser.add_argument("--device-timeout", type=int, default=120, metavar="SEC",
                        help="Max seconds to wait for MTR main page (default: 120)")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop after the first failed round")
    parser.add_argument("--no-record", action="store_true",
                        help="Disable ffmpeg desktop recording")
    parser.add_argument("--ffmpeg", default=FFMPEG_DEFAULT, metavar="PATH",
                        help=f"Path to ffmpeg.exe (default: {FFMPEG_DEFAULT})")
    return parser.parse_args()


def main():
    args = parse_args()

    _now = datetime.now()
    if args.output_dir is None:
        args.output_dir = str(Path(__file__).parent / "logs" / Path(__file__).stem / _now.strftime("%Y%m%d") / _now.strftime("%H%M%S"))

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.output_dir) / "files").mkdir(parents=True, exist_ok=True)

    logger = Logger(args.output_dir)

    # Resolve meeting ID / passcode from host JSON if requested
    if args.from_host or args.meeting_info_dir:
        info_dir = None if args.from_host else args.meeting_info_dir
        logger.info(
            f"Waiting for meeting info from teams_meeting_host.py"
            f"{f' ({info_dir})' if info_dir else ''} ..."
        )
        try:
            info = MeetingInfo.wait_for_info(info_dir, timeout=args.meeting_info_timeout)
        except TimeoutError as e:
            logger.error(str(e))
            sys.exit(1)
        logger.info(f"Meeting info loaded:\n{info}")
        args.meeting_id = info.meeting_id
        args.passcode = info.passcode or None

    # Connect to Duvel device
    if args.ip:
        serial = args.ip if ":" in args.ip else f"{args.ip}:5555"
        device = DuvelDevice(serial=serial, is_ip=True)
    else:
        device = DuvelDevice(serial=args.serial, is_ip=False)

    try:
        device.connect()
    except ConnectionError as e:
        logger.error(str(e))
        sys.exit(1)

    start_ui_with_scrcpy(device._serial)
    recorder = None if args.no_record else start_recording(args.output_dir, args.ffmpeg)

    writer = ResultWriter(total_rounds=args.iterations, device_label=device.label, logger=logger)
    runner = MtrJoinWithIdTestRunner(device=device, args=args, logger=logger)

    logger.info(f"MTR Join-with-ID Test  v{VERSION}")
    logger.info(f"  Device        : {device.label}")
    logger.info(f"  FW            : {device.barco_fw_version()}")
    logger.info(f"  Meeting ID    : {args.meeting_id}")
    if args.passcode:
        logger.info(f"  Passcode      : {args.passcode}")
    logger.info(f"  Iterations    : {args.iterations}")
    logger.info(f"  Output dir    : {args.output_dir}")

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
        stop_recording(recorder)
        if results:
            writer.print_summary(results)
        device.disconnect()


if __name__ == "__main__":
    main()

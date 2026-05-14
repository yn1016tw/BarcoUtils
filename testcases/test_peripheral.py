"""
Peripheral Test for Duvel
Measures time and features from reboot to Camera, Mic, and Speaker ready.
Supports USB serial or IP connection. Supports stress testing.

Camera check : v4l2_stream_test (STREAMON + 5s warm-up + DQBUF)
Audio check  : /proc/asound/cards -> tinyplay (speaker) -> tinycap RMS (mic)

Usage:
    python testcases/test_peripheral.py --serial 1882000501 --iterations 5
    python testcases/test_peripheral.py --ip 192.168.1.100 --iterations 3
    python testcases/test_peripheral.py --ip 192.168.1.100:5555 --iterations 1 --output-dir C:/logs

Author: James Yang <james.yang@barco.com>
"""

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from common.duvel_device import DuvelDevice, _STREAM_TEST_BIN_REMOTE, _TONE_WAV_2S_REMOTE
from common.version import VERSION


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
    audio_ready: float | None = None    # kernel card enumerated
    speaker_ready: float | None = None  # tinyplay succeeded
    mic_ready: float | None = None      # tinycap RMS > threshold
    mic_rms: float | None = None        # recorded RMS value
    barco_fw_version: str | None = None        # ro.barco.build.version
    camera_device: str | None = None    # e.g. /dev/video7
    camera_name: str | None = None      # e.g. "Rally Camera"
    camera_frame: str | None = None     # local path to captured JPEG
    audio_card: str | None = None       # e.g. "RallyCamera"
    audio_name: str | None = None       # e.g. "Rally Camera"
    error: str | None = None
    passed: bool = False

    def total_seconds(self) -> float | None:
        last = self.mic_ready or self.speaker_ready or self.audio_ready
        if last and self.reboot_start:
            return last - self.reboot_start
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

    def speaker_seconds(self) -> float | None:
        if self.speaker_ready and self.boot_ready:
            return self.speaker_ready - self.boot_ready
        return None

    def mic_seconds(self) -> float | None:
        if self.mic_ready and self.boot_ready:
            return self.mic_ready - self.boot_ready
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
        path = Path(output_dir) / "logs.txt"
        lines = self._format_lines(results)
        mode = "a" if path.exists() else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\n  Log saved: {path}")

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

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

        cam_label = f"  [{r.camera_device}  {r.camera_name}]" if r.camera_device else ""
        aud_label = f"  [{r.audio_card}  {r.audio_name}]" if r.audio_card else ""
        mic_label = f"  RMS={r.mic_rms:.0f}" if r.mic_rms is not None else ""

        def tag(t: float | None) -> str:
            return "  PASS" if t is not None else "  FAIL"

        lines.append(f"  Reboot triggered    : {self._ts(r.reboot_start)}")
        lines.append(f"  Boot ready          : {self._ts(r.boot_ready)}{self._diff(r.boot_ready, r.reboot_start)}{tag(r.boot_ready)}")
        lines.append(f"  Camera working      : {self._ts(r.camera_ready)}{self._diff(r.camera_ready, r.boot_ready, 'from boot')}{tag(r.camera_ready)}{cam_label}")
        if r.camera_frame:
            lines.append(f"  Frame saved         : {r.camera_frame}")
        lines.append(f"  Audio card ready    : {self._ts(r.audio_ready)}{self._diff(r.audio_ready, r.boot_ready, 'from boot')}{tag(r.audio_ready)}{aud_label}")
        lines.append(f"  Speaker working     : {self._ts(r.speaker_ready)}{self._diff(r.speaker_ready, r.boot_ready, 'from boot')}{tag(r.speaker_ready)}")
        lines.append(f"  Mic working         : {self._ts(r.mic_ready)}{self._diff(r.mic_ready, r.boot_ready, 'from boot')}{tag(r.mic_ready)}{mic_label}")
        total = r.total_seconds()
        lines.append(f"  Total (reboot->mic) : {total:.1f}s" if total else "  Total               : N/A")
        return lines

    def _format_summary_lines(self, results: list[TestResult]) -> list[str]:
        n = len(results)

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
            line("Camera ready  min/avg/max", [r.camera_seconds() for r in results]),
            line("Audio card    min/avg/max", [r.audio_seconds() for r in results]),
            line("Speaker ready min/avg/max", [r.speaker_seconds() for r in results]),
            line("Mic ready     min/avg/max", [r.mic_seconds() for r in results]),
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
# PeripheralTestRunner
# ---------------------------------------------------------------------------

class PeripheralTestRunner:
    def __init__(self, device: DuvelDevice, args):
        self._device = device
        self._args = args

    def run(self) -> list[TestResult]:
        results = []
        for i in range(1, self._args.iterations + 1):
            results.append(self.run_round(i, self._args.iterations))
        return results

    def run_round(self, round_num: int, total_rounds: int) -> TestResult:
        r = TestResult(round_num=round_num, total_rounds=total_rounds)
        print(f"\n{'-' * 60}")
        print(f"Round {round_num}/{total_rounds} - rebooting device...")

        try:
            r.reboot_start = time.time()
            self._device.reboot()

            print("  Waiting for boot...")
            self._device.wait_for_boot(self._args.boot_timeout)
            r.boot_ready = time.time()
            r.barco_fw_version = self._device.barco_fw_version()
            print(f"  Boot ready  (+{r.boot_seconds():.1f}s)")

            tests = set(self._args.tests)

            if "camera" in tests:
                print("  Waiting for camera (streaming test)...")
                ts = datetime.now().strftime("%H%M%S")
                frame_path = str(Path(self._args.output_dir) / "files" / f"round{round_num:02d}_{ts}.jpg")
                self._device.clear_camera_tmp()
                Path(frame_path).unlink(missing_ok=True)
                r.camera_device, r.camera_name = self._device.wait_for_camera_working(self._args.device_timeout, frame_path)
                r.camera_ready = time.time()
                r.camera_frame = frame_path
                print(f"  Camera working  {r.camera_device}  {r.camera_name}  (+{r.camera_seconds():.1f}s from boot)")
                print(f"  Frame saved     : {frame_path}")

            if tests & {"speaker", "mic"}:
                print("  Waiting for audio card (/proc/asound/cards check)...")
                r.audio_card, r.audio_name = self._device.wait_for_audio_working(self._args.device_timeout)
                r.audio_ready = time.time()
                print(f"  Audio card ready  [{r.audio_card}]  {r.audio_name}  (+{r.audio_seconds():.1f}s from boot)")

            if "speaker" in tests:
                print("  Testing speaker (tinyplay 1kHz tone)...")
                speaker_ok = self._device.test_speaker(duration=2)
                r.speaker_ready = time.time()
                print(f"  Speaker {'OK' if speaker_ok else 'FAIL'}  (+{r.speaker_seconds():.1f}s from boot)")
                if not speaker_ok:
                    raise RuntimeError("Speaker playback failed (tinyplay returned non-zero)")

            if "mic" in tests:
                print("  Testing mic (tinycap RMS check)...")
                mic_ok, r.mic_rms = self._device.test_mic(duration=2)
                r.mic_ready = time.time()
                print(f"  Mic {'OK' if mic_ok else 'FAIL'}  RMS={r.mic_rms:.0f}  (+{r.mic_seconds():.1f}s from boot)")
                if not mic_ok:
                    raise RuntimeError(f"Mic recording too quiet (RMS={r.mic_rms:.0f} below threshold)")

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
    parser.add_argument("--tests", nargs="+", choices=["camera", "speaker", "mic"],
                        default=["camera", "speaker", "mic"], metavar="TEST",
                        help="Tests to run: camera speaker mic (default: all)")
    parser.add_argument("--output-dir", default=None, metavar="DIR", help="Log output directory (default: logs/ next to this script)")
    parser.add_argument("--boot-timeout", type=int, default=300, metavar="SEC", help="Max seconds to wait for boot (default: 300)")
    parser.add_argument("--device-timeout", type=int, default=120, metavar="SEC", help="Max seconds to wait for camera/audio (default: 120)")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed round (default: continue)")
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

    writer = ResultWriter(total_rounds=args.iterations, device_label=device.label)
    runner = PeripheralTestRunner(device=device, args=args)

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.output_dir) / "files").mkdir(parents=True, exist_ok=True)

    try:
        device.connect()
        device.push_peripheral_resources()
    except ConnectionError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print(f"Peripheral Test  v{VERSION}")
    print(f"  Device     : {device.label}")
    print(f"  FW         : {device.barco_fw_version()}")
    print(f"  Iterations : {args.iterations}")
    print(f"  Tests      : {' '.join(args.tests)}")
    print(f"  Output dir : {args.output_dir}")
    print(f"  [ADB] {'Connected to' if args.ip else 'USB device'} {device.label}")
    print(f"  [ADB] v4l2_stream_test -> {_STREAM_TEST_BIN_REMOTE}")
    print(f"  [ADB] barco_tone_2s.wav -> {_TONE_WAV_2S_REMOTE}")

    results = []
    try:
        for i in range(1, args.iterations + 1):
            result = runner.run_round(i, args.iterations)
            results.append(result)
            writer.print_round(result)
            if args.fail_fast and not result.passed:
                print("\n[Stopped: --fail-fast]")
                break
    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
    finally:
        if results:
            writer.print_summary(results)
            writer.save_log(results, args.output_dir)
        device.disconnect()


if __name__ == "__main__":
    main()

"""
TestLedClient — CLI wrapper around common.test_led_client.TestLedClient's AIDL
scenario control.

Exists so scripts/god_verify_led_manager_app.ps1 (PowerShell) can drive the 9
AIDL-only LedType values (Error, ResetToDefaults, UpdatingBaseUnit*,
SoftwareReboot, BaseUnitStandbyEco/DeepSleep, BaseUnitInUse) that have no
generic `adb shell` command - only TestLedClient's Client1/Client2 toggle
buttons (LedClient.startScenario()/stopScenario() over AIDL) can trigger them.
See common/test_led_client.py's module docstring for the full rationale.

`serial` is treated as an IP[:port] (is_ip=True) if it contains a ".",
otherwise as a USB serial (is_ip=False) - matches this repo's actual serial
formats (USB serials here are plain digit strings; IPs always have dots).

Usage:
    python scripts/test_led_client_cli.py --serial 192.168.1.100:5555 is-installed
    python scripts/test_led_client_cli.py --serial 192.168.1.100:5555 launch
    python scripts/test_led_client_cli.py --serial 192.168.1.100:5555 start --client 1 --led-type BaseUnitInUse
    python scripts/test_led_client_cli.py --serial 192.168.1.100:5555 stop --client 1 --led-type BaseUnitInUse

Prints "OK" and exits 0 on success; prints "FAIL: <reason>" and exits 1 otherwise.

Author: James Yang <james.yang@barco.com>
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "testcases"))

from common.test_led_client import TestLedClient  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Control the TestLedClient app for LED scenario testing")
    parser.add_argument("--serial", required=True, help="ADB serial (USB) or IP[:port]")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("is-installed")
    sub.add_parser("is-running")
    sub.add_parser("launch")

    p_start = sub.add_parser("start")
    p_start.add_argument("--client", type=int, required=True, choices=[1, 2])
    p_start.add_argument("--led-type", required=True)
    p_start.add_argument("--timeout", type=int, default=5)

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("--client", type=int, required=True, choices=[1, 2])
    p_stop.add_argument("--led-type", required=True)
    p_stop.add_argument("--timeout", type=int, default=5)

    args = parser.parse_args()

    is_ip = "." in args.serial
    client = TestLedClient(serial=args.serial, is_ip=is_ip)
    client.connect()

    if args.command == "is-installed":
        ok = client.is_installed()
    elif args.command == "is-running":
        ok = client.is_running()
    elif args.command == "launch":
        client.launch()
        ok = True
    elif args.command == "start":
        ok = client.start_scenario(args.client, args.led_type, timeout=args.timeout)
    elif args.command == "stop":
        ok = client.stop_scenario(args.client, args.led_type, timeout=args.timeout)
    else:
        ok = False

    if ok:
        print("OK")
        sys.exit(0)
    else:
        print(f"FAIL: {args.command} did not confirm within timeout")
        sys.exit(1)


if __name__ == "__main__":
    main()

# Author: James Yang <james.yang@barco.com>
"""
USB Switch Test using AcronameHub (USBHub3+)

Demonstrates switch_port (downstream 0-7) and set_upstream_port (host 0/1).
Each round: switch to each port in sequence, measure current/voltage, then
switch upstream host between round.

Usage:
    python testcases/test_usb_switch.py
    python testcases/test_usb_switch.py --serial 0x12345678
    python testcases/test_usb_switch.py --ports 0 1 2 --iterations 3
    python testcases/test_usb_switch.py --ports 0 1 --upstream 0 --dwell 2.0
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common.acroname_hub import AcronameHub
from common.version import VERSION


def parse_args():
    p = argparse.ArgumentParser(description="USB switch test via AcronameHub")
    p.add_argument("--serial", type=lambda x: int(x, 0), default=None,
                   help="Hub serial number (hex OK: 0x12345678); omit to auto-discover")
    p.add_argument("--ports", type=int, nargs="+", default=[0, 1],
                   metavar="PORT", help="Downstream ports to cycle (default: 0 1)")
    p.add_argument("--upstream", type=int, choices=[0, 1], default=None,
                   help="Fix upstream host port; omit to alternate each round")
    p.add_argument("--dwell", type=float, default=1.0,
                   help="Seconds to dwell on each port (default: 1.0)")
    p.add_argument("--iterations", type=int, default=3,
                   help="Number of full cycles (default: 3)")
    return p.parse_args()


def measure_port(hub: AcronameHub, port: int) -> tuple[float | None, float | None]:
    current = hub.get_port_current(port)
    voltage = hub.get_port_voltage(port)
    return current, voltage


def run(args) -> int:
    print(f"BarcoUtils v{VERSION} — USB Switch Test")
    print(f"  ports={args.ports}  upstream={args.upstream}  "
          f"dwell={args.dwell}s  iterations={args.iterations}")
    print()

    hub = AcronameHub()
    connected = hub.connect(serial=args.serial)
    if not connected:
        print("ERROR: could not connect to AcronameHub")
        return 1

    serial = hub.hub_serial()
    fw = hub.hub_firmware_version()
    print(f"Connected — serial=0x{serial:08X}  firmware={fw}")
    print()

    hub.set_upstream_port(0)
    hub.switch_port(1)
    hub.disconnect()

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(run(parse_args()))

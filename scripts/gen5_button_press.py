"""
Gen5 ClickShare Button — press simulation CLI.

Thin CLI wrapper around ClickShareButton.press(), for use by
scripts/gen5_button.bat (auto-detects the button's serial and calls this).

Usage:
    python scripts/gen5_button_press.py --serial 1200602466
    python scripts/gen5_button_press.py --serial 1200602466 --long

Author: James Yang <james.yang@barco.com>
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "testcases"))

from common.clickshare_button import ClickShareButton  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a press on a Gen5 ClickShare Button")
    parser.add_argument("--serial", required=True, help="ADB serial of the Gen5 Button")
    parser.add_argument("--long", action="store_true", help="Simulate a long press instead of a short press")
    args = parser.parse_args()

    button = ClickShareButton(serial=args.serial, is_ip=False)
    button.connect()
    button.press(long_press=args.long)
    print(f"{'Long' if args.long else 'Short'} press sent to {args.serial}")


if __name__ == "__main__":
    main()

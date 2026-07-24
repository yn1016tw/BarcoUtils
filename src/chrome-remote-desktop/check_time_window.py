#!/usr/bin/env python3
"""Exit 0 if the current local time falls inside the configured weekday/time
window, non-zero otherwise. Used as a gate by the BIOS-wake auto-login flow
(enable_autologin_and_reboot.bat / run_after_autologin.bat) so those scripts
only act near the intended schedule, regardless of what actually triggered
the boot or login -- a manual restart at 2pm must not enable auto-login."""

import argparse
import datetime
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", default="0,1,2,3,4", help="comma-separated weekday numbers, Monday=0 (default: Mon-Fri)")
    parser.add_argument("--start", default="08:00", help="HH:MM window start, inclusive")
    parser.add_argument("--end", default="08:45", help="HH:MM window end, exclusive")
    args = parser.parse_args()

    now = datetime.datetime.now()
    allowed_days = {int(d) for d in args.days.split(",") if d.strip() != ""}
    start = datetime.datetime.strptime(args.start, "%H:%M").time()
    end = datetime.datetime.strptime(args.end, "%H:%M").time()

    in_window = now.weekday() in allowed_days and start <= now.time() < end
    sys.exit(0 if in_window else 1)


if __name__ == "__main__":
    main()

"""
TeamsMeetingHost — create a Teams meeting and auto-accept all incoming calls.

Runs as a standalone script on the Windows PC side while MTR devices join
the meeting via test_mtr_join_call.py.

Steps when started:
  1. Connect to Teams desktop
  2. Start a Meet Now meeting
  3. Copy join info and extract Meeting ID + Passcode
  4. Save meeting info to <output-dir>/meeting_info.json
  5. Loop: auto-accept every incoming call until Ctrl+C

Other test cases can read meeting info from the JSON file:

    from common.teams_meeting_host import MeetingInfo
    info = MeetingInfo.load()          # reads default path
    info = MeetingInfo.load("C:/logs") # reads from custom dir
    print(info.meeting_id, info.passcode)

Usage:
    python testcases/common/teams_meeting_host.py
    python testcases/common/teams_meeting_host.py --output-dir C:/logs
    python testcases/common/teams_meeting_host.py --accept-video
    python testcases/common/teams_meeting_host.py --no-auto-accept  # create meeting only

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logger import Logger
from common.teams_desktop import TeamsDesktopController

# Default JSON path (testcases/logs/)
_DEFAULT_INFO_FILE = Path(__file__).parent.parent / "logs" / "meeting_info.json"

# How often to poll for incoming calls
_ACCEPT_POLL_INTERVAL = 1.0


# ---------------------------------------------------------------------------
# MeetingInfo — shared data structure
# ---------------------------------------------------------------------------

@dataclass
class MeetingInfo:
    meeting_id: str = ""
    passcode: str = ""
    join_url: str = ""
    created_at: str = ""
    info_file: str = ""

    # ---- serialisation ----

    def save(self, output_dir: str | Path | None = None) -> Path:
        """Write meeting info to JSON and return the path."""
        path = _resolve_info_path(output_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.info_file = str(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        return path

    @classmethod
    def load(cls, output_dir: str | Path | None = None) -> "MeetingInfo":
        """Load meeting info from JSON. Raises FileNotFoundError if absent."""
        path = _resolve_info_path(output_dir)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def wait_for_info(
        cls,
        output_dir: str | Path | None = None,
        timeout: int = 120,
    ) -> "MeetingInfo":
        """Block until the JSON file appears (written by a running host), then load it.

        Useful in test scripts that start before the host has created the meeting.
        Raises TimeoutError if file is not found within timeout seconds.
        """
        path = _resolve_info_path(output_dir)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if path.exists():
                try:
                    return cls.load(output_dir)
                except Exception:
                    pass
            time.sleep(1)
        raise TimeoutError(
            f"Meeting info not found at {path} within {timeout}s — "
            "is teams_meeting_host.py running?"
        )

    def is_valid(self) -> bool:
        return bool(self.meeting_id or self.join_url)

    def __str__(self) -> str:
        lines = [f"  Meeting ID : {self.meeting_id or '(unknown)'}"]
        if self.passcode:
            lines.append(f"  Passcode   : {self.passcode}")
        if self.join_url:
            lines.append(f"  Join URL   : {self.join_url}")
        if self.created_at:
            lines.append(f"  Created at : {self.created_at}")
        return "\n".join(lines)


def _resolve_info_path(output_dir: str | Path | None) -> Path:
    if output_dir is None:
        return _DEFAULT_INFO_FILE
    return Path(output_dir) / "meeting_info.json"


# ---------------------------------------------------------------------------
# TeamsMeetingHost
# ---------------------------------------------------------------------------

class TeamsMeetingHost:
    """Creates a Teams meeting and auto-accepts incoming calls.

    Usage:
        host = TeamsMeetingHost()
        info = host.start()           # connect, create meeting, return MeetingInfo
        host.start_auto_accept()      # background thread
        ...
        host.stop()
    """

    def __init__(self, accept_video: bool = False, output_dir: str | Path | None = None,
                 logger: Logger | None = None):
        self._ctrl = TeamsDesktopController()
        self._accept_video = accept_video
        self._output_dir = output_dir
        self._info = MeetingInfo()
        self._accepting = False
        self._accept_thread: threading.Thread | None = None
        self._logger = logger

    # ---- public API -------------------------------------------------------

    def start(self, connect_timeout: int = 30, meeting_timeout: int = 30) -> MeetingInfo:
        """Connect to Teams and start a Meet Now meeting.

        Returns a MeetingInfo with meeting_id/passcode/join_url populated.
        Saves the info to JSON immediately so other processes can read it.
        """
        self._logger.info("Connecting to Teams...")
        self._ctrl.connect(launch=True, timeout=connect_timeout)
        self._logger.info("Connected.")

        self._logger.info("Starting Meet Now meeting...")
        # create_meeting() returns dict: {meeting_id, passcode, join_url}
        info_dict = self._ctrl.create_meeting(timeout=meeting_timeout)

        self._info = MeetingInfo(
            meeting_id=info_dict.get("meeting_id", ""),
            passcode=info_dict.get("passcode", ""),
            join_url=info_dict.get("join_url", ""),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        saved_path = self._info.save(self._output_dir)
        self._logger.info("Meeting created:\n%s", self._info)
        self._logger.info("Info saved: %s", saved_path)
        return self._info

    def get_meeting_info(self) -> MeetingInfo:
        """Return the current meeting info (populated after start())."""
        return self._info

    def start_auto_accept(self) -> None:
        """Start a background thread that accepts all incoming calls."""
        if self._accepting:
            return
        self._accepting = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="auto-accept"
        )
        self._accept_thread.start()
        self._logger.info("Auto-accept started (background thread running).")

    def stop(self) -> None:
        """Stop the auto-accept loop."""
        self._accepting = False
        if self._accept_thread:
            self._accept_thread.join(timeout=5)
        self._logger.info("Auto-accept stopped.")

    def run_forever(self) -> None:
        """Block, accept calls, until Ctrl+C."""
        self.start_auto_accept()
        self._logger.info("Waiting for incoming calls... (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self._logger.info("Stopped by user.")
        finally:
            self.stop()

    # ---- internals --------------------------------------------------------

    def _accept_loop(self) -> None:
        while self._accepting:
            try:
                if self._ctrl.wait_for_incoming_call(timeout=2):
                    caller = self._get_caller_name()
                    self._logger.info("Incoming call detected%s — accepting...",
                                      f" from {caller}" if caller else "")
                    ok = (
                        self._ctrl.accept_video_call()
                        if self._accept_video
                        else self._ctrl.accept_call()
                    )
                    if ok:
                        self._logger.info("Call accepted.")
                    else:
                        # Race condition: popup may have disappeared between detection
                        # and the click attempt — re-check before declaring failure.
                        time.sleep(1)
                        if not self._ctrl.wait_for_incoming_call(timeout=1):
                            self._logger.info("Call accepted (popup cleared before click confirmed).")
                        else:
                            self._logger.warning("Accept failed — button not found. Running diagnostic dump...")
                            self._ctrl.dump_incoming_call_info()
                    time.sleep(2)  # debounce: wait before checking again
            except Exception as e:
                self._logger.error("auto-accept error: %s", e)
                self._logger.debug(traceback.format_exc())
                time.sleep(_ACCEPT_POLL_INTERVAL)

    def _get_caller_name(self) -> str:
        """Try to read the caller name from the incoming call toast title."""
        try:
            from pywinauto import Desktop
            for w in Desktop(backend="uia").windows():
                title = w.window_text() or ""
                m = re.match(r"^(.+?)\s+(is calling|is video calling)", title, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
        except Exception:
            pass
        return ""



# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Create a Teams meeting and auto-accept incoming calls"
    )
    p.add_argument(
        "--output-dir", default=None, metavar="DIR",
        help=f"Directory to write meeting_info.json (default: {_DEFAULT_INFO_FILE.parent})",
    )
    p.add_argument(
        "--accept-video", action="store_true",
        help="Accept calls with video (default: audio only)",
    )
    p.add_argument(
        "--no-auto-accept", action="store_true",
        help="Create meeting and print info, then exit (do not accept calls)",
    )
    p.add_argument(
        "--connect-timeout", type=int, default=30, metavar="SEC",
        help="Seconds to wait for Teams to start (default: 30)",
    )
    p.add_argument(
        "--meeting-timeout", type=int, default=30, metavar="SEC",
        help="Seconds to wait for meeting to start (default: 30)",
    )
    return p.parse_args()


def main():
    args = parse_args()

    log_dir = args.output_dir or str(_DEFAULT_INFO_FILE.parent)
    log_file = f"{datetime.now().strftime('%Y%m%d')}_meeting_host.log"
    logger = Logger(log_dir, filename=log_file)

    host = TeamsMeetingHost(
        accept_video=args.accept_video,
        output_dir=args.output_dir,
        logger=logger,
    )

    try:
        info = host.start(
            connect_timeout=args.connect_timeout,
            meeting_timeout=args.meeting_timeout,
        )
    except Exception as e:
        logger.error("%s", e)
        sys.exit(1)

    if not info.is_valid():
        logger.warning("Could not extract meeting ID/passcode — check Teams UI manually.")
        logger.warning("The JSON file was saved with whatever info was available.")

    if args.no_auto_accept:
        return

    host.run_forever()


if __name__ == "__main__":
    main()

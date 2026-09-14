"""
TestLedClient — ADB-based controller for the TestLedClient app.

TestLedClient (led-manager-apk repo's `test-led-client` module, package
`com.barco.clickshare.testledclient`) is a UI-only test harness with no
exported components of its own: two independent AIDL LED clients ("Client1"/
"Client2", each a grid of ToggleButtons — one per LedType — that call
LedClient.startScenario()/stopScenario() directly), plus a third "Client3"
row of plain Buttons that each send a short sequence of ACTION_PAIRING_BUTTON
broadcasts (the same event shape buttonmanager-apk sends). This class drives
that UI via uiautomator dumps + `input tap`, the same approach ui_mtr.py uses
for Teams Rooms.

Purpose: LedType values reachable only through the AIDL ILedManager interface
(Error, ResetToDefaults, UpdatingBaseUnit*, SoftwareReboot,
BaseUnitStandbyEco/DeepSleep, BaseUnitInUse) have no generic `adb shell`
command to trigger them — TestLedClient's toggle buttons are the only way to
exercise them without writing a custom AIDL caller. See
scripts/god_verify_led_manager_app.ps1 for the ADB-broadcast-only coverage of the
remaining 7 button-related LedTypes, and cross-check results against
BaseUnit.Led.State (configuration-manager-apk) either way.

Requires `adb` in PATH and TestLedClient already installed
(`test-led-client/build/outputs/apk/debug/test-led-client-debug.apk`, built via
`./gradlew :test-led-client:assembleDebug` from C:\\Project\\Wave4\\led-manager-apk).

Usage:
    from common.test_led_client import TestLedClient
    client = TestLedClient(serial="192.168.1.100:5555", is_ip=True)
    client.connect()
    client.launch()
    client.start_scenario(1, "BaseUnitInUse")
    client.stop_scenario(1, "BaseUnitInUse")
    client.trigger_intent_sequence("pairing_button_success")

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = "com.barco.clickshare.testledclient"
ACTIVITY = ".MainActivity"
_UI_DUMP_REMOTE = "/data/local/tmp/testledclient_ui_dump.xml"
_POLL_INTERVAL = 0.3  # seconds

# All 16 LedType values -> Client1 ToggleButton resource-id (per MainActivity.kt's
# mainButtonLedTypeMap / activity_main.xml). Client2 uses the same id with a "1" suffix.
LED_TYPE_BUTTON_IDS = {
    "Error": "errorButton",
    "ResetToDefaults": "resetToDefaultsButton",
    "UpdatingBaseUnit": "updatingBaseUnitButton",
    "UpdatingBaseUnitSuccess": "updatingBaseUnitSuccessButton",
    "SoftwareReboot": "softwareRebootButton",
    "UpdatingBaseUnitFailed": "updatingBaseUnitFailedButton",
    "UpdatingButton": "updatingButtonButtoon",  # sic - typo in app source (R.id.updatingButtonButtoon)
    "UpdatingButtonSuccess": "updatingButtonSuccessButton",
    "UpdatingButtonFailed": "updatingButtonFailedButton",
    "PairingButton": "pairingButtonButton",
    "PairingButtonSuccess": "pairingButtonSuccessButton",
    "PairingButtonFailed": "pairingButtonFailedButton",
    "BaseUnitStandbyEco": "baseUnitStandbyEcoButton",
    "BaseUnitStandbyDeepSleep": "baseUnitStandbyDeepSleepButton",
    "BaseUnitInUse": "baseUnitInUseButton",
    "Idle": "idleButton",
}

# Client3 (intent) plain Buttons -> resource-id. Each tap sends a short sequence of
# ACTION_PAIRING_BUTTON broadcasts for a fixed test serial ("1234567890"), ~3s apart
# (see MainActivity.kt's thirdButtonLedTypeListMap / handleButtonClick).
#
# KNOWN BUG in TestLedClient itself (confirmed empirically against a real device, not
# just by reading source): 3 of these 5 never reach their named LedType, because
# MainActivity.kt's hardcoded ButtonStatus strings don't match ButtonStatus.kt's real
# enum values, and/or the sequence never sends the final "Finished.Successful" needed
# to resolve a *Success type:
#   - "pairing_button_success": sends "Pair.Started"/"Pair.Successful" (real values are
#     "Pairing.Started"/"Pairing.Successful") and never sends "Finished.Successful" ->
#     LED state never leaves Idle.
#   - "updating_button_success": sends "FirmwareSync.InProgress"/"WaitingToFinish"/
#     "Successful" but likewise never sends "Finished.Successful" -> LED state never
#     leaves Idle.
#   - "pairing_button_failed": sends "Pair.Started" (typo) then
#     "Pair.Error.PairInfoFailure" (real value is "Pairing.Error.PairingInfoFailure")
#     -> both are unknown to ButtonStatus.fromValue(), LED state never leaves Idle.
#   - "updating_button_failed" and "detach" DO work (their strings happen to match
#     ButtonStatus.kt exactly) - confirmed: triggers UpdatingButtonFailed, then Idle.
# Prefer set_scenario()/AIDL for the success/pairing-failed cases instead of these
# three broken buttons; only use "updating_button_failed"/"detach" from this map, or
# fix test-led-client's MainActivity.kt if the broadcast-path coverage matters.
INTENT_BUTTON_IDS = {
    "pairing_button_success": "buttonPairingSuccessButton",
    "updating_button_success": "buttonUpdatingSuccessButton",
    "pairing_button_failed": "buttonPairingFailedButton",
    "updating_button_failed": "buttonUpdatingFailedButton",
    "detach": "buttonDetachButton",
}


class TestLedClient:
    def __init__(self, serial: str, is_ip: bool):
        self._serial = serial  # e.g. "ABC123" or "192.168.1.100:5555"
        self._is_ip = is_ip

    @property
    def label(self) -> str:
        return self._serial

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self._is_ip:
            result = subprocess.run(
                ["adb", "connect", self._serial],
                capture_output=True, text=True, timeout=15,
            )
            out = result.stdout.strip()
            if "connected" not in out.lower() and "already" not in out.lower():
                raise ConnectionError(f"adb connect failed: {out}")
        else:
            result = self._adb_raw(["devices"], timeout=10)
            if self._serial not in result.stdout:
                raise ConnectionError(f"Device {self._serial} not found in adb devices")

    def disconnect(self) -> None:
        if self._is_ip:
            subprocess.run(["adb", "disconnect", self._serial], capture_output=True, timeout=5)

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------

    def is_installed(self) -> bool:
        r = self._adb(["shell", "pm", "list", "packages", PACKAGE])
        return f"package:{PACKAGE}" in r.stdout

    def is_running(self) -> bool:
        r = self._adb_raw(["shell", "pidof", PACKAGE], timeout=10)
        return r.stdout.strip().isdigit()

    def launch(self) -> None:
        self._adb(["shell", "am", "start", "-n", f"{PACKAGE}/{ACTIVITY}"])

    def force_stop(self) -> None:
        self._adb(["shell", "am", "force-stop", PACKAGE])

    # ------------------------------------------------------------------
    # UI hierarchy (mirrors ui_mtr.py's dump/find/tap pattern)
    # ------------------------------------------------------------------

    def dump_ui(self) -> str:
        """Dump the current UI hierarchy and return raw XML, or '' if dump fails."""
        raw = self._adb_bytes(
            ["shell", f"uiautomator dump {_UI_DUMP_REMOTE} >/dev/null 2>&1"
             f" && cat {_UI_DUMP_REMOTE} && rm -f {_UI_DUMP_REMOTE}"],
            timeout=20,
        )
        return raw.decode("utf-8", errors="replace") if raw else ""

    def find_element(self, resource_id: str) -> dict | None:
        """Look up one node by its bare resource-id (without the package prefix).

        Returned dict keys: checked (bool, only meaningful for ToggleButtons),
        text, bounds, center. center is an (x, y) tuple suitable for tap(); None
        if bounds are missing.
        """
        try:
            root = ET.fromstring(self.dump_ui())
        except ET.ParseError:
            return None
        full_id = f"{PACKAGE}:id/{resource_id}"
        for node in root.iter("node"):
            if node.get("resource-id") == full_id:
                return {
                    "checked": node.get("checked") == "true",
                    "text": node.get("text"),
                    "bounds": node.get("bounds", ""),
                    "center": _bounds_center(node.get("bounds", "")),
                }
        return None

    def tap(self, x: int, y: int) -> None:
        self._adb(["shell", "input", "tap", str(x), str(y)])

    def message_display_text(self) -> str | None:
        """Return the app's on-screen result message (the messageDisplay TextView),
        e.g. "button: errorButton, type: Error, checked: true, result: Success"."""
        return (self.find_element("messageDisplay") or {}).get("text")

    def screenshot(self, local_path: str) -> None:
        data = self._adb_bytes(["exec-out", "screencap", "-p"], timeout=15)
        p = Path(local_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    # ------------------------------------------------------------------
    # Client1 / Client2 - AIDL LED scenarios (ToggleButtons)
    # ------------------------------------------------------------------

    def set_scenario(self, client: int, led_type: str, enable: bool, timeout: int = 5) -> bool:
        """Start (enable=True) or stop (enable=False) an LED scenario on client 1 or 2
        by toggling its button, then polling until the toggle reflects the desired
        checked state. led_type is one of LED_TYPE_BUTTON_IDS' keys (all 16 LedType
        names). Returns True once confirmed, False on timeout or missing element.
        A no-op (returns True immediately) if the toggle is already in that state.
        """
        if led_type not in LED_TYPE_BUTTON_IDS:
            raise ValueError(f"Unknown LedType: {led_type}")
        if client not in (1, 2):
            raise ValueError("client must be 1 or 2")

        base_id = LED_TYPE_BUTTON_IDS[led_type]
        resource_id = base_id if client == 1 else f"{base_id}1"

        el = self.find_element(resource_id)
        if el is None or el["center"] is None:
            return False
        if el["checked"] == enable:
            return True

        self.tap(*el["center"])

        deadline = time.time() + timeout
        while time.time() < deadline:
            el = self.find_element(resource_id)
            if el and el["checked"] == enable:
                return True
            time.sleep(_POLL_INTERVAL)
        return False

    def start_scenario(self, client: int, led_type: str, timeout: int = 5) -> bool:
        return self.set_scenario(client, led_type, True, timeout=timeout)

    def stop_scenario(self, client: int, led_type: str, timeout: int = 5) -> bool:
        return self.set_scenario(client, led_type, False, timeout=timeout)

    # ------------------------------------------------------------------
    # Client3 - intent broadcast sequences
    # ------------------------------------------------------------------

    def trigger_intent_sequence(self, name: str) -> bool:
        """Tap one of Client3's buttons (see INTENT_BUTTON_IDS). Each sends its
        fixed sequence of ACTION_PAIRING_BUTTON broadcasts (~3s apart, for test
        serial "1234567890") asynchronously - this call only confirms the tap
        landed, not that the sequence finished; poll BaseUnit.Led.State
        separately to observe the result."""
        if name not in INTENT_BUTTON_IDS:
            raise ValueError(f"Unknown intent sequence: {name}")
        el = self.find_element(INTENT_BUTTON_IDS[name])
        if el is None or el["center"] is None:
            return False
        self.tap(*el["center"])
        return True

    # ------------------------------------------------------------------
    # ADB helpers
    # ------------------------------------------------------------------

    def _adb(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        result = self._adb_raw(args, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(str(a) for a in args)} failed: {result.stderr.strip()}")
        return result

    def _adb_raw(self, args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        prefix = ["-s", self._serial] if self._serial else []
        cmd = ["adb"] + prefix + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def _adb_bytes(self, args: list, timeout: int = 30) -> bytes:
        prefix = ["-s", self._serial] if self._serial else []
        cmd = ["adb"] + prefix + args
        return subprocess.run(cmd, capture_output=True, timeout=timeout).stdout


def _bounds_center(bounds: str) -> tuple[int, int] | None:
    """Parse '[x1,y1][x2,y2]' -> center (x, y), or None on error."""
    try:
        parts = bounds.replace("][", ",").strip("[]").split(",")
        x1, y1, x2, y2 = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    except (ValueError, IndexError):
        return None

"""
SetupDatetimePage — Page object for the MDEP Device Setup Wizard "Set date & time" step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Date and time configuration (shown after network connection)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_datetime

Usage:
    page = device.ui.setup_datetime
    if page.is_visible():
        print(page.get_current_time())    # "2:39 AM, May 7, 2026"
        print(page.get_timezone())        # "GMT-00:00 Azores"
        page.click_next()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import time

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupDatetimePage(BasePage):
    """Page object for the 'Set date & time' wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the date/time setup step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/currentTime")
                or self._ui.find_element(text="Set date & time")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title (e.g. 'Set date & time')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/setupStepTitle")
        return el.get("text") if el else None

    def get_current_time(self) -> str | None:
        """Return the displayed current time string (e.g. '2:39 AM, May 7, 2026')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/currentTime")
        return el.get("text") if el else None

    def get_timezone(self) -> str | None:
        """Return the currently selected timezone (e.g. 'GMT-00:00 Azores')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/timeZoneSelectionLabel")
        return el.get("text") if el else None

    def click_timezone(self) -> bool:
        """Tap the timezone selector to open the timezone picker."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/timeZoneSelectionLabel"},
        ])

    def set_timezone(self, location: str, max_scrolls: int = 30) -> bool:
        """Open the picker, scroll to find location by city name, select it, and tap Save.

        location: city name as shown in the list (e.g. 'Brussels', 'London', 'Amsterdam').
        Returns True if the timezone was found, selected, and saved.
        """
        if not self.click_timezone():
            return False

        # Wait for the picker RecyclerView to appear.
        deadline = time.time() + 5
        while time.time() < deadline:
            if self._ui.find_element(resource_id=f"{_PKG}:id/timezonesRecycler"):
                break
            time.sleep(0.4)
        else:
            return False

        # Recycler centre-X and swipe Y coords (from observed bounds [552,235][1368,843]).
        cx = 960
        swipe_from_y, swipe_to_y = 730, 300

        for _ in range(max_scrolls):
            el = self._ui.find_element(resource_id=f"{_PKG}:id/location", text=location)
            if el and el["center"]:
                self._ui.tap(*el["center"])
                return self._tap([
                    {"resource_id": f"{_PKG}:id/cs_positive_button"},
                    {"text": "Save"},
                ])
            self._ui.swipe(cx, swipe_from_y, cx, swipe_to_y, duration_ms=300)
            time.sleep(0.3)

        return False

    def cancel_timezone_picker(self) -> bool:
        """Tap Cancel in the timezone picker to dismiss without saving."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/cs_negative_button"},
            {"text": "Cancel"},
        ])

    def is_24h_format(self) -> bool | None:
        """Return True if 24-hour format is enabled, False if 12-hour, None if not found."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/toggleTimeFormat")
        if el is None:
            return None
        return el.get("checked") == "true"

    def toggle_time_format(self) -> bool:
        """Tap the 24-hour format toggle switch."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/toggleTimeFormat"},
        ])

    def click_change_time_server(self) -> bool:
        """Tap the 'Change time server' optional button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/optionalButton"},
            {"text": "Change time server"},
        ])

    def click_next(self) -> bool:
        """Tap the 'Next' primary button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Next"},
        ])

    def click_back(self) -> bool:
        """Tap the Back button (top-left chevron)."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/backButton"},
            {"content_desc": "Back"},
        ])

    def get_ip_address(self) -> str | None:
        """Return the IP address shown in the footer bar."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/ipAddressValue")
        return el.get("text") if el else None

    def get_serial_number(self) -> str | None:
        """Return the serial number shown in the footer bar."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/serialNumberValue")
        return el.get("text") if el else None

    def get_version(self) -> str | None:
        """Return the firmware version shown in the footer bar."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/versionValue")
        return el.get("text") if el else None

    def get_build_type(self) -> str | None:
        """Return the build type shown in the footer bar (e.g. 'debug')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/buildTypeValue")
        return el.get("text") if el else None

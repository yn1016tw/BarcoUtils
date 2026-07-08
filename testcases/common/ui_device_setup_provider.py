"""
SetupProviderPage — Page object for the MDEP "Choose your provider" screen.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Firmware:  04.04.00.master-2073 / MDEP TPB7.241001.071

Access via device.ui.setup_provider

Note: on this firmware build the resource-ids and their displayed text are
swapped — `clickshareProviderCard`/`textProviderMTR` show "ClickShare" while
`mtrProviderCard`/`textProviderClickshare` show "Microsoft Teams Rooms". The
methods below are named after the resource-id (and therefore the underlying
provider they select), not the mislabeled text.

Usage:
    page = device.ui.setup_provider
    if page.is_visible():
        page.select_mtr()
        page.click_confirm()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupProviderPage(BasePage):
    """Page object for the 'Choose your provider' wizard screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Choose your provider screen is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/clickshareProviderCard")
                or self._ui.find_element(resource_id=f"{_PKG}:id/mtrProviderCard")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the screen title text (e.g. 'Choose your provider')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/title")
        return el.get("text") if el else None

    def select_clickshare(self) -> bool:
        """Tap the ClickShare provider card (resource-id clickshareProviderCard)."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/clickshareProviderCard"},
            {"content_desc": "ClickShare provider"},
        ])

    def select_mtr(self) -> bool:
        """Tap the Microsoft Teams Room provider card (resource-id mtrProviderCard)."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/mtrProviderCard"},
            {"content_desc": "Microsoft Teams Room provider"},
        ])

    def click_confirm(self) -> bool:
        """Tap the 'Confirm' primary button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Confirm"},
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

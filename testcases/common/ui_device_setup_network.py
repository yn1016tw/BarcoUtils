"""
SetupNetworkPage — Page object for the MDEP Device Setup Wizard "Connect to the network" step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Network connection (shown after language selection)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_network

Usage:
    page = device.ui.setup_network
    if page.is_visible():
        print(page.get_connectivity_message())  # "You're connected."
        page.click_next()
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupNetworkPage(BasePage):
    """Page object for the 'Connect to the network' wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the network connection step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/connectivityMessage")
                or self._ui.find_element(text="Connect to the network")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title (e.g. 'Connect to the network')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/setupStepTitle")
        return el.get("text") if el else None

    def get_connectivity_message(self) -> str | None:
        """Return the connectivity status message (e.g. \"You're connected.\")."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/connectivityMessage")
        return el.get("text") if el else None

    def is_connected(self) -> bool:
        """Return True if the connectivity message indicates a successful connection."""
        msg = self.get_connectivity_message()
        return msg is not None and "connected" in msg.lower()

    def click_next(self) -> bool:
        """Tap the 'Next' primary button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Next"},
        ])

    def click_settings(self) -> bool:
        """Tap the 'Settings' optional button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/optionalButton"},
            {"text": "Settings"},
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

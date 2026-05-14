"""
SetupCompletePage — Page object for the MDEP Device Setup Wizard "Installation complete!" screen.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Final completion screen (shown after all setup steps are done)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_complete

Usage:
    page = device.ui.setup_complete
    if page.is_visible():
        print(page.get_title())   # "Installation complete!"
        page.click_continue()     # advance to Microsoft Teams

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupCompletePage(BasePage):
    """Page object for the 'Installation complete!' wizard completion screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the installation complete screen is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(content_desc="Installation complete!")
                or self._ui.find_element(text="Installation complete!")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the completion title (e.g. 'Installation complete!')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/title")
        return el.get("text") if el else None

    def click_continue(self) -> bool:
        """Tap the 'Continue to Microsoft Teams' button to finish setup."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Continue to Microsoft Teams"},
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

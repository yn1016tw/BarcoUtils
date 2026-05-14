"""
DeviceSetupWizardPage — Page object for the MDEP Device Setup Wizard screen.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Firmware:  04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.device_setup_wizard

Usage:
    page = device.ui.device_setup_wizard
    if page.is_visible():
        page.confirm_connection()
    ip  = page.get_ip_address()    # "10.102.90.83"
    ver = page.get_version()       # "04.03.00.master-1660"

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"
_ACTIVITY = f"{_PKG}/.root.RootActivity"


class DeviceSetupWizardPage(BasePage):
    """Page object for the 'No input device detected' wizard screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Device Setup Wizard is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/primaryButton")
                or self._ui.find_element(text="No input device detected")
            ),
            timeout,
        )

    def confirm_connection(self) -> bool:
        """Tap the 'Confirm connection' primary button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Confirm connection"},
        ])

    def get_title(self) -> str | None:
        """Return the wizard title text (e.g. 'No input device detected')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/title")
        return el.get("text") if el else None

    def get_message(self) -> str | None:
        """Return the wizard body message text."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/message")
        return el.get("text") if el else None

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

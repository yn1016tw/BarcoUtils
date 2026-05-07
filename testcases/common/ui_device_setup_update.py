"""
SetupUpdatePage — Page object for the MDEP Device Setup Wizard firmware update check step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Firmware update check (shown after date & time configuration)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_update

Usage:
    page = device.ui.setup_update
    if page.is_visible():
        print(page.get_title())           # "System is up to date!"
        print(page.get_fw_version())      # "Firmware Version 04.03.00.master-1660"
        print(page.get_message())         # "Your device is running the latest version..."
        page.click_continue()
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupUpdatePage(BasePage):
    """Page object for the firmware update check wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the firmware update check step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/primarySubtitle")
                or self._ui.find_element(text="System is up to date!")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title (e.g. 'System is up to date!')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/title")
        return el.get("text") if el else None

    def get_fw_version(self) -> str | None:
        """Return the firmware version subtitle (e.g. 'Firmware Version 04.03.00.master-1660')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/primarySubtitle")
        return el.get("text") if el else None

    def get_message(self) -> str | None:
        """Return the secondary message body text."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/secondarySubtitle")
        return el.get("text") if el else None

    def click_continue(self) -> bool:
        """Tap the 'Continue' primary button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Continue"},
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

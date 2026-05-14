"""
SetupTermsPage — Page object for the MDEP Device Setup Wizard "Terms & Conditions" step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     EULA acceptance (shown early in setup flow)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_terms

Usage:
    page = device.ui.setup_terms
    if page.is_visible():
        print(page.get_title())       # "Terms & Conditions"
        print(page.get_disclaimer())  # "By clicking accept, you agree to..."
        page.click_accept()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupTermsPage(BasePage):
    """Page object for the 'Terms & Conditions' EULA acceptance wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Terms & Conditions step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/policyDisclaimer")
                or self._ui.find_element(text="Terms & Conditions")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title (e.g. 'Terms & Conditions')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/title")
        return el.get("text") if el else None

    def get_eula_text(self) -> str | None:
        """Return the EULA body text (the full license agreement content)."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/message")
        return el.get("text") if el else None

    def get_disclaimer(self) -> str | None:
        """Return the disclaimer line below the EULA (e.g. 'By clicking accept, you agree to...')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/policyDisclaimer")
        return el.get("text") if el else None

    def click_accept(self) -> bool:
        """Tap the 'I accept' primary button to agree to the EULA."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "I accept"},
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

"""
SetupPrivacyPage — Page object for the MDEP Device Setup Wizard "Microsoft Privacy" step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Privacy / diagnostic data settings (shown after Terms & Conditions)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_privacy

Usage:
    page = device.ui.setup_privacy
    if page.is_visible():
        print(page.get_title())       # "Microsoft Privacy"
        print(page.get_subtitle())    # "Microsoft puts you in control of your privacy..."
        page.toggle_optional_data()   # enable optional diagnostic data
        page.click_accept()
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupPrivacyPage(BasePage):
    """Page object for the 'Microsoft Privacy' diagnostic data wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Microsoft Privacy step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/privacy_fragment")
                or self._ui.find_element(text="Microsoft Privacy")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title (e.g. 'Microsoft Privacy')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/setupStepTitle")
        return el.get("text") if el else None

    def get_subtitle(self) -> str | None:
        """Return the subtitle description (e.g. 'Microsoft puts you in control of your privacy...')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/subtitle")
        return el.get("text") if el else None

    def get_required_data_label(self) -> str | None:
        """Return the 'Required diagnostic data' section label."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/requiredDataSubtitleText")
        return el.get("text") if el else None

    def get_required_data_content(self) -> str | None:
        """Return the required diagnostic data description text."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/requiredDataContent")
        return el.get("text") if el else None

    def get_optional_data_content(self) -> str | None:
        """Return the optional diagnostic data description text."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/optionalDataContent")
        return el.get("text") if el else None

    def get_optional_data_clarification(self) -> str | None:
        """Return the optional diagnostic data clarification text."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/optionalDataContentClarification")
        return el.get("text") if el else None

    def is_optional_data_enabled(self) -> bool | None:
        """Return True if the optional diagnostic data toggle is ON, False if OFF, None if not found."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/toggle")
        if el is None:
            return None
        return el.get("checked") == "true"

    def toggle_optional_data(self) -> bool:
        """Tap the optional diagnostic data toggle switch to change its state."""
        return self._tap([{"resource_id": f"{_PKG}:id/toggle"}])

    def click_learn_more(self) -> bool:
        """Tap the 'Learn more' optional button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/optionalButton"},
            {"text": "Learn more"},
        ])

    def click_accept(self) -> bool:
        """Tap the 'Accept' primary button to proceed past the privacy step."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Accept"},
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

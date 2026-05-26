"""
SetupNetworkPage — Page object for the MDEP Device Setup Wizard network connectivity step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Network connectivity (shown after language selection)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071
          04.03.00.master-1858 (revised UI: online_title/online_message replace connectivityMessage;
          primaryButton text changed from "Next" to "Continue"; secondaryButton replaces optionalButton)

Access via device.ui.setup_network

Usage:
    page = device.ui.setup_network
    if page.is_visible():
        print(page.get_connectivity_message())
        page.click_next()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupNetworkPage(BasePage):
    """Page object for the network connectivity wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the network connectivity step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/connectivityMessage")
                or self._ui.find_element(resource_id=f"{_PKG}:id/connectivity_host_fragment")
                or self._ui.find_element(text="Connect to the network")
                or self._ui.find_element(text="Network Connectivity")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/setupStepTitle")
        return el.get("text") if el else None

    def get_connectivity_message(self) -> str | None:
        """Return the connectivity status message.

        Tries both FW layouts: legacy connectivityMessage (≤1660) and
        online_title + online_message (≥1858).
        """
        el = self._ui.find_element(resource_id=f"{_PKG}:id/connectivityMessage")
        if el:
            return el.get("text")
        title = self._ui.find_element(resource_id=f"{_PKG}:id/online_title")
        msg = self._ui.find_element(resource_id=f"{_PKG}:id/online_message")
        parts = [e.get("text") for e in (title, msg) if e and e.get("text")]
        return " ".join(parts) if parts else None

    def get_online_title(self) -> str | None:
        """Return the online status title (≥1858, e.g. 'Internet Connection Established')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/online_title")
        return el.get("text") if el else None

    def get_online_message(self) -> str | None:
        """Return the detailed online status message (≥1858)."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/online_message")
        return el.get("text") if el else None

    def get_limited_message(self) -> str | None:
        """Return the limited-connectivity label if visible (≥1858)."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/limited_message")
        return el.get("text") if el else None

    def is_connected(self) -> bool:
        """Return True if the page indicates a successful internet connection."""
        # Legacy layout: check connectivityMessage text
        legacy = self._ui.find_element(resource_id=f"{_PKG}:id/connectivityMessage")
        if legacy:
            msg = legacy.get("text") or ""
            return "connected" in msg.lower()
        # New layout (≥1858): online_title visible = connected
        return bool(self._ui.find_element(resource_id=f"{_PKG}:id/online_title"))

    def click_next(self) -> bool:
        """Tap the primary 'Next' / 'Continue' button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Continue"},
            {"text": "Next"},
        ])

    def click_settings(self) -> bool:
        """Tap the 'Network settings' / 'Settings' secondary button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/secondaryButton"},
            {"resource_id": f"{_PKG}:id/optionalButton"},
            {"text": "Network settings"},
            {"text": "Settings"},
        ])

    def click_more_information(self) -> bool:
        """Tap the 'More information' troubleshooting button (≥1858)."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/troubleshootingButton"},
            {"text": "More information"},
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

"""
SetupXmsCloudPage — Page object for the MDEP Device Setup Wizard "Scan QR Code" step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     XMS Cloud account linking via QR code (shown after language selection)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_xms_cloud

Usage:
    page = device.ui.setup_xms_cloud
    if page.is_visible():
        print(page.get_title())     # "Scan QR Code to continue"
        print(page.get_subtitle())  # "Point your mobile device camera at the QR code..."
        page.click_skip()

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupXmsCloudPage(BasePage):
    """Page object for the XMS Cloud QR code account-linking wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the QR code sign-in step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/textTitle")
                or self._ui.find_element(text="Scan QR Code to continue")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title (e.g. 'Scan QR Code to continue')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/textTitle")
        return el.get("text") if el else None

    def get_subtitle(self) -> str | None:
        """Return the subtitle instruction text."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/leftSideSubtitle")
        return el.get("text") if el else None

    def get_extra_info(self) -> str | None:
        """Return the extra info text below the subtitle."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/leftSideExtraInfo")
        return el.get("text") if el else None

    def click_skip(self) -> bool:
        """Tap the 'Skip' button to bypass QR code sign-in."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/skipButton"},
            {"text": "Skip"},
        ])

    def click_knowledge_base(self) -> bool:
        """Tap the knowledge base / troubleshooting link."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/knowledgeBaseInformationView"},
            {"text_contains": "Click here for more information"},
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

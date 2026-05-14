"""
SetupConfirmPage — Page object for the MDEP Device Setup Wizard "Confirm installation" step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Final confirmation (shown after admin password creation)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_confirm

Usage:
    page = device.ui.setup_confirm
    if page.is_visible():
        print(page.get_setup_status())   # "Setup complete with XMS cloud"
        print(page.get_room_name())      # "ClickShare-1882000501"
        page.click_confirm_installation()

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupConfirmPage(BasePage):
    """Page object for the 'Confirm installation' wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the confirm installation step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/layoutSetupComplete")
                or self._ui.find_element(text="Confirm installation")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the page title (e.g. 'Confirm installation')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/fragmentTitle")
        return el.get("text") if el else None

    def get_setup_status(self) -> str | None:
        """Return the setup completion status (e.g. 'Setup complete with XMS cloud')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/title")
        return el.get("text") if el else None

    def get_subtitle(self) -> str | None:
        """Return the subtitle text (e.g. 'Device successfully configured and ready for operation')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/subtitle")
        return el.get("text") if el else None

    def get_room_name(self) -> str | None:
        """Return the room name shown in the device details (e.g. 'ClickShare-1882000501')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/tvRoomValue")
        return el.get("text") if el else None

    def get_model_name(self) -> str | None:
        """Return the model name shown in the device details (e.g. 'Clickshare-Hub-Pro')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/tvModelValue")
        return el.get("text") if el else None

    def get_platform_name(self) -> str | None:
        """Return the platform name shown in the device details (e.g. 'C-300RS')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/tvPlatformValue")
        return el.get("text") if el else None

    def get_serial_number(self) -> str | None:
        """Return the serial number shown in the device details."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/tvSerialValue")
        return el.get("text") if el else None

    def get_admin_password_status(self) -> str | None:
        """Return the admin password status line (e.g. 'Admin password is set.')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/adminPassTitle")
        return el.get("text") if el else None

    def click_change_password(self) -> bool:
        """Tap the 'Change admin password' button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/buttonChangePassword"},
            {"text": "Change admin password"},
        ])

    def click_confirm_installation(self) -> bool:
        """Tap the 'Confirm installation' primary button to complete setup."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Confirm installation"},
        ])

    def get_ip_address(self) -> str | None:
        """Return the IP address shown in the footer bar."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/ipAddressValue")
        return el.get("text") if el else None

    def get_serial_number_footer(self) -> str | None:
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

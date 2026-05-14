"""
DeviceSettingsPage — Page object for the Android Device Settings panel.

Opened from Teams Rooms Settings → Device settings. This is the native
com.android.settings app embedded as an overlay. Contains a scrollable
list of setting categories.

Access via device.ui.device_settings

Usage:
    device.ui.device_settings.is_visible()
    device.ui.device_settings.click_exit()
    device.ui.device_settings.click_accessibility()
    device.ui.device_settings.click_system()
    device.ui.device_settings.click_about()
    device.ui.device_settings.click_admin_settings()

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.android.settings"


class DeviceSettingsPage(BasePage):
    """Page object for the Android Device Settings panel."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Device Settings panel is displayed. Polls until timeout if > 0."""
        return self._poll(
            lambda: bool(self._ui.find_element(resource_id=f"{_PKG}:id/settings_homepage_container")),
            timeout,
        )

    def click_exit(self) -> bool:
        """Tap Exit settings (back button in the toolbar). Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/back_button_two_pane"},
            {"content_desc": "Exit settings"},
        ])

    def click_accessibility(self) -> bool:
        """Tap the Accessibility entry. Returns True if found and tapped."""
        return self._tap([{"text": "Accessibility"}])

    def click_system(self) -> bool:
        """Tap the System entry. Returns True if found and tapped."""
        return self._tap([{"text": "System"}])

    def click_about(self) -> bool:
        """Tap the About entry. Returns True if found and tapped."""
        return self._tap([{"text": "About"}])

    def click_admin_settings(self) -> bool:
        """Tap the Admin settings entry. Returns True if found and tapped."""
        return self._tap([{"text": "Admin settings"}])

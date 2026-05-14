"""
SettingsPage — Page object for the Teams Rooms Settings dialog.

Shown after tapping Settings from the More menu. Contains org name display
plus navigation entries (About, Device settings).

Access via device.ui.settings

Usage:
    device.ui.settings.is_visible()
    device.ui.settings.click_back()
    device.ui.settings.get_org_name()      # e.g. "barcomxdev"
    device.ui.settings.click_about()
    device.ui.settings.click_device_settings()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from common.ui_base import BasePage
from common.ui_mtr import _MTR_PACKAGE as _PKG


class SettingsPage(BasePage):
    """Page object for the Teams Rooms Settings dialog."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Settings dialog is displayed. Polls until timeout if > 0."""
        return self._poll(
            lambda: bool(self._ui.find_element(resource_id=f"{_PKG}:id/settings")),
            timeout,
        )

    def click_back(self) -> bool:
        """Tap the Back button in the toolbar. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/overflow_menu_button"},
            {"content_desc": "Back"},
        ])

    def get_org_name(self) -> str | None:
        """Return the organisation name shown at the top, or None if not found."""
        try:
            root = ET.fromstring(self._ui.dump_ui())
        except ET.ParseError:
            return None
        container = None
        for node in root.iter("node"):
            if node.get("resource-id") == f"{_PKG}:id/organization_name":
                container = node
                break
        if container is None:
            return None
        for child in container.iter("node"):
            text = child.get("text", "").strip()
            if text:
                return text
        return None

    def click_about(self) -> bool:
        """Tap the About entry. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/settings_about_layout"},
            {"content_desc": "About"},
            {"resource_id": f"{_PKG}:id/settings_item_about"},
        ])

    def click_device_settings(self) -> bool:
        """Tap the Device settings entry. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/settings_partner_settings_layout"},
            {"content_desc": "Device settings"},
            {"resource_id": f"{_PKG}:id/settings_item_partner_settings"},
        ])

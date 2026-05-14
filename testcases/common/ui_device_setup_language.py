"""
SetupLanguagePage — Page object for the MDEP Device Setup Wizard "Select language" step.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Language selection (after confirming device connection)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_language

Usage:
    page = device.ui.setup_language
    if page.is_visible():
        print(page.get_selected_language())  # "English"
        page.select_language("English")
        page.click_continue()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupLanguagePage(BasePage):
    """Page object for the 'Select language' wizard step."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the language selection step is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/languagesRecycler")
                or self._ui.find_element(text="Select language")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the step title (e.g. 'Select language')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/setupStepTitle")
        return el.get("text") if el else None

    def get_selected_language(self) -> str | None:
        """Return the currently selected language name, or None if not found."""
        try:
            root = ET.fromstring(self._ui.dump_ui())
        except ET.ParseError:
            return None
        for row in root.iter("node"):
            if row.get("resource-id") != f"{_PKG}:id/row":
                continue
            radio = next(
                (c for c in row if c.get("resource-id") == f"{_PKG}:id/selected"),
                None,
            )
            if radio is None or radio.get("checked") != "true":
                continue
            lang = next(
                (c for c in row if c.get("resource-id") == f"{_PKG}:id/language"),
                None,
            )
            return lang.get("text") if lang is not None else None
        return None

    def select_language(self, language: str) -> bool:
        """Tap the row for the given language name. Returns True if found and tapped.

        Note: only languages currently visible in the list can be tapped.
        If the language is off-screen, scroll first.
        """
        return self._tap([{"text": language}])

    def click_continue(self) -> bool:
        """Tap the 'Continue' primary button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Continue"},
        ])

    def click_back(self) -> bool:
        """Tap the Back button (top-left chevron)."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/backButton"},
            {"content_desc": "Back"},
        ])

    def click_accessibility_settings(self) -> bool:
        """Tap the 'Accessibility settings' outlined button."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/outlinedButton"},
            {"text": "Accessibility settings"},
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

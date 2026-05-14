"""
TeamsSignInPage — Page object for the Teams "Welcome / Device Code Flow" sign-in screen.

Activity: com.microsoft.skype.teams.ipphone/.NordenActivity (or similar)
Step:     First-run sign-in (device code flow — enter code at microsoft.com/devicelogin)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.teams_sign_in

Usage:
    page = device.ui.teams_sign_in
    if page.is_visible():
        code = page.get_login_code()      # e.g. "ABC123"
        print(f"Go to microsoft.com/devicelogin and enter: {code}")
        page.click_refresh_code()         # generate a new code
        page.click_sign_in_on_device()    # switch to on-device sign-in flow

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.skype.teams.ipphone"


class TeamsSignInPage(BasePage):
    """Page object for the Teams device-code-flow (DCF) sign-in screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Teams DCF sign-in screen is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/dcf_code_layout")
                or self._ui.find_element(resource_id=f"{_PKG}:id/dfc_login_code")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the welcome title (e.g. 'Welcome to Microsoft Teams!')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/welcome_to_teams_title")
        return el.get("text") if el else None

    def get_tenant_name(self) -> str | None:
        """Return the provisioned tenant name shown above the title (may be empty before sign-in)."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/provisioned_tenant_name")
        return el.get("text") if el else None

    def get_step1_text(self) -> str | None:
        """Return the Step 1 instruction (e.g. 'Step 1: On your computer or mobile, go to ...')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/step_1_text_info")
        return el.get("text") if el else None

    def get_step2_text(self) -> str | None:
        """Return the Step 2 instruction (e.g. 'Step 2: Enter the code below to sign in.')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/step_2_text_info")
        return el.get("text") if el else None

    def get_login_code(self) -> str | None:
        """Return the current device login code (e.g. 'ABC123') to enter at microsoft.com/devicelogin."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/dfc_login_code")
        return el.get("text") if el else None

    def click_refresh_code(self) -> bool:
        """Tap the 'Refresh code' button to generate a new device login code."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/refresh_code_button"},
            {"text": "Refresh code"},
            {"content_desc": "Refresh code"},
        ])

    def click_sign_in_on_device(self) -> bool:
        """Tap the 'Sign in on this device' button to switch to on-device sign-in flow."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/sign_in_on_the_device"},
            {"text": "Sign in on this device"},
        ])

    def click_settings(self) -> bool:
        """Tap the Settings gear icon in the top-right corner."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/fre_partner_settings"},
            {"content_desc": "Settings"},
        ])

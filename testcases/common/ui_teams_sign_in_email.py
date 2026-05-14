"""
TeamsSignInEmailPage — Page object for the Teams on-device email/account sign-in screen.

Activity: com.microsoft.skype.teams.ipphone/.NordenActivity (or similar)
Step:     On-device sign-in — email / phone / username entry
          (reached by tapping "Sign in on this device" from the DCF screen)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.teams_sign_in_email

Usage:
    page = device.ui.teams_sign_in_email
    if page.is_visible():
        page.enter_email("user@contoso.com")
        page.click_sign_in()

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.skype.teams.ipphone"


class TeamsSignInEmailPage(BasePage):
    """Page object for the Teams on-device email/username entry sign-in screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the on-device email sign-in screen is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/fre_auth")
                or self._ui.find_element(resource_id=f"{_PKG}:id/edit_email")
            ),
            timeout,
        )

    def get_label(self) -> str | None:
        """Return the welcome label text above the email field."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/email_label")
        return el.get("text") if el else None

    def enter_email(self, email: str) -> bool:
        """Tap the email/username field and type the given address."""
        if not self._tap([{"resource_id": f"{_PKG}:id/edit_email"}]):
            return False
        self._ui.input_text(email)
        return True

    def click_sign_in(self) -> bool:
        """Tap the 'Sign in' button to proceed with the entered email."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/sign_in_button"},
            {"text": "Sign in"},
            {"content_desc": "Sign in"},
        ])

    def click_back(self) -> bool:
        """Tap the back arrow to return to the previous sign-in screen."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/sign_in_back_button"},
            {"content_desc": "Back"},
        ])

    def click_settings(self) -> bool:
        """Tap the Settings gear icon in the top-right corner."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/fre_partner_settings"},
            {"content_desc": "Settings"},
        ])

    def click_privacy_cookies(self) -> bool:
        """Tap the 'Privacy & Cookies' link at the bottom of the screen."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/privacy_cookies_link"},
            {"text": "Privacy & Cookies"},
        ])

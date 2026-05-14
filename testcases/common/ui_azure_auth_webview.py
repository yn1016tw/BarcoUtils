"""
AzureAuthWebViewPage — Page object for the Azure Authenticator WebView sign-in screen.

Package:  com.azure.authenticator
Step:     Microsoft account authentication — multi-step MSAL web flow:
            1. Password entry    (is_password_page)
            2. Device registration  (is_device_registration_page)
          Shown after email is entered in the Teams on-device sign-in flow.
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.azure_auth_webview

NOTE: The page is a WebView whose content is the Microsoft MSAL HTML sign-in form.
      Once loaded, the WebView exposes HTML element IDs as Android accessibility
      resource-ids (e.g. resource-id="i0118" for the password field).
      These can be found and tapped via find_element / tap_element normally.

Usage:
    page = device.ui.azure_auth_webview
    if page.is_visible():
        print(page.get_display_name())   # "user@contoso.com"
        page.enter_password("MyPass!")
        page.click_sign_in()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.azure.authenticator"


class AzureAuthWebViewPage(BasePage):
    """Page object for the Azure Authenticator MSAL password-entry WebView screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Azure Authenticator auth WebView is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/dual_screen_layout")
            ),
            timeout,
        )

    def is_password_page(self) -> bool:
        """Return True if the password-entry form is loaded inside the WebView."""
        return bool(
            self._ui.find_element(resource_id="i0118")
            or self._ui.find_element(text="Enter password")
        )

    def get_display_name(self) -> str | None:
        """Return the account name shown on the sign-in form (e.g. 'user@contoso.com')."""
        el = self._ui.find_element(resource_id="displayName")
        return el.get("text") if el else None

    def enter_password(self, password: str) -> bool:
        """Tap the password field (HTML id 'i0118') and type the given password."""
        if not self._tap([
            {"resource_id": "i0118"},
            {"text": "Enter password"},
        ]):
            return False
        self._ui.input_text(password)
        return True

    def click_sign_in(self) -> bool:
        """Tap the 'Sign in' button (HTML id 'idSIButton9')."""
        return self._tap([
            {"resource_id": "idSIButton9"},
            {"text": "Sign in"},
        ])

    def click_back(self) -> bool:
        """Tap the 'Back' link to return to the email entry step."""
        return self._tap([
            {"resource_id": "idBtn_Back"},
            {"text": "Back"},
        ])

    def click_forgot_password(self) -> bool:
        """Tap the 'Forgot my password' link."""
        return self._tap([
            {"resource_id": "idA_PWD_ForgotPassword"},
            {"content_desc": "Forgot my password"},
            {"text": "Forgot my password"},
        ])

    def click_sign_in_with_another_account(self) -> bool:
        """Tap the 'Sign in with another account' link."""
        return self._tap([
            {"resource_id": "i1668"},
            {"content_desc": "Sign in with another account"},
            {"text": "Sign in with another account"},
        ])

    def click_terms_of_use(self) -> bool:
        """Tap the 'Terms of use' footer link."""
        return self._tap([
            {"resource_id": "ftrTerms"},
            {"content_desc": "Terms of use"},
        ])

    def click_privacy_cookies(self) -> bool:
        """Tap the 'Privacy & cookies' footer link."""
        return self._tap([
            {"resource_id": "ftrPrivacy"},
            {"content_desc": "Privacy & cookies"},
        ])

    # ── Device registration step ──────────────────────────────────────────────

    def is_device_registration_page(self) -> bool:
        """Return True if the 'Help us keep your device secure' registration prompt is shown."""
        return bool(
            self._ui.find_element(resource_id="WorkplaceJoinDescription")
            or self._ui.find_element(text="Help us keep your device secure")
        )

    def get_heading(self) -> str | None:
        """Return the page heading (e.g. 'Help us keep your device secure')."""
        el = self._ui.find_element(resource_id="heading")
        return el.get("text") if el else None

    def get_description(self) -> str | None:
        """Return the body description (e.g. 'Register your device to continue.')."""
        el = self._ui.find_element(resource_id="WorkplaceJoinDescription")
        return el.get("text") if el else None

    def click_register(self) -> bool:
        """Tap the 'Register' primary button on the device registration prompt."""
        return self._tap([
            {"resource_id": "idSIButton9", "text": "Register"},
            {"text": "Register"},
        ])

    def click_more_details(self) -> bool:
        """Tap the 'Click here for more details' link on the registration page."""
        return self._tap([
            {"resource_id": "MoreDetails"},
            {"resource_id": "moreOptions"},
            {"text": "Click here for more details"},
        ])

"""
SetupAdminPasswordPage — Page object for the MDEP Device Setup Wizard "Create Admin Password" dialog.

Activity: com.microsoft.devicesetupwizard/.root.RootActivity
Step:     Admin password creation (dialog shown during XMS Cloud / account-linking step)
Firmware: 04.03.00.master-1660 / MDEP TPB7.241001.071

Access via device.ui.setup_admin_password

Usage:
    page = device.ui.setup_admin_password
    if page.is_visible():
        page.enter_new_password("MyPass123!")
        page.enter_confirm_password("MyPass123!")
        page.click_create_and_continue()
"""

from __future__ import annotations

from common.ui_base import BasePage

_PKG = "com.microsoft.devicesetupwizard"


class SetupAdminPasswordPage(BasePage):
    """Page object for the 'Create Admin Password' dialog in the setup wizard."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the admin password creation dialog is in the foreground."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/adminPasswordTitle")
                or self._ui.find_element(text="Create Admin Password")
            ),
            timeout,
        )

    def get_title(self) -> str | None:
        """Return the dialog title (e.g. 'Create Admin Password')."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/adminPasswordTitle")
        return el.get("text") if el else None

    def enter_new_password(self, password: str) -> bool:
        """Tap the 'Enter password' field and type the given password."""
        if not self._tap([{"resource_id": f"{_PKG}:id/newPasswordInput"}]):
            return False
        self._ui.input_text(password)
        return True

    def toggle_new_password_visibility(self) -> bool:
        """Tap the eye icon to show/hide the new password field."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/newPasswordVisibilityToggle"},
            {"content_desc": "Toggle Password Visibility"},
        ])

    def enter_confirm_password(self, password: str) -> bool:
        """Tap the 'Confirm password' field and type the given password."""
        if not self._tap([{"resource_id": f"{_PKG}:id/confirmNewPasswordInput"}]):
            return False
        self._ui.input_text(password)
        return True

    def toggle_confirm_password_visibility(self) -> bool:
        """Tap the eye icon to show/hide the confirm password field."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/confirmNewPasswordVisibilityToggle"},
        ])

    def get_password_error(self) -> str | None:
        """Return the password error or strength hint text."""
        el = self._ui.find_element(resource_id=f"{_PKG}:id/passwordError")
        return el.get("text") if el else None

    def get_password_strength(self) -> str | None:
        """Return password strength: 'weak', 'medium', 'strong', or None if unknown.

        Determined by which strength bar is selected (checked=true).
        Returns the highest strength level whose bar is visible/active.
        """
        bar_weak   = self._ui.find_element(resource_id=f"{_PKG}:id/barWeak")
        bar_medium = self._ui.find_element(resource_id=f"{_PKG}:id/barMedium")
        bar_strong = self._ui.find_element(resource_id=f"{_PKG}:id/barStrong")
        if bar_strong and bar_strong.get("checked") == "true":
            return "strong"
        if bar_medium and bar_medium.get("checked") == "true":
            return "medium"
        if bar_weak and bar_weak.get("checked") == "true":
            return "weak"
        return None

    def click_create_and_continue(self) -> bool:
        """Tap the 'Create and continue' primary button (enabled only when passwords match)."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/primaryButton"},
            {"text": "Create and continue"},
        ])

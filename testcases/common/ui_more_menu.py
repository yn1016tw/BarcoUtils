"""
MoreMenuPage — Page object for the Teams Rooms "More" overlay.

Shown after tapping "More" on the home screen. Contains a two-row grid of
actions plus a Back button to return to the home screen.

Access via device.ui.more_menu

Usage:
    device.ui.more_menu.is_visible()
    device.ui.more_menu.click_back()
    device.ui.more_menu.click_meet_now()
    device.ui.more_menu.click_call()
    device.ui.more_menu.click_share()
    device.ui.more_menu.click_whiteboard()
    device.ui.more_menu.click_join_with_an_id()
    device.ui.more_menu.click_settings()
"""

from __future__ import annotations

from common.ui_base import BasePage
from common.ui_mtr import _MTR_PACKAGE as _PKG


class MoreMenuPage(BasePage):
    """Page object for the Teams Rooms More menu overlay."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the More menu overlay is displayed. Polls until timeout if > 0."""
        return self._poll(
            lambda: bool(self._ui.find_element(resource_id=f"{_PKG}:id/more_menu_container")),
            timeout,
        )

    def click_back(self) -> bool:
        """Tap the Back button to close the menu. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/back_layout"},
            {"resource_id": f"{_PKG}:id/tv_back"},
            {"text": "Back"},
        ])

    def click_meet_now(self) -> bool:
        """Tap Meet now. Returns True if found and tapped."""
        return self._tap([{"text": "Meet now"}])

    def click_call(self) -> bool:
        """Tap Call. Returns True if found and tapped."""
        return self._tap([{"text": "Call"}])

    def click_share(self) -> bool:
        """Tap Share. Returns True if found and tapped."""
        return self._tap([{"text": "Share"}])

    def click_whiteboard(self) -> bool:
        """Tap Whiteboard. Returns True if found and tapped."""
        return self._tap([{"text": "Whiteboard"}])

    def click_join_with_an_id(self) -> bool:
        """Tap Join with an ID. Returns True if found and tapped."""
        return self._tap([{"text": "Join with an ID"}])

    def click_settings(self) -> bool:
        """Tap Settings. Returns True if found and tapped."""
        return self._tap([{"text": "Settings"}])

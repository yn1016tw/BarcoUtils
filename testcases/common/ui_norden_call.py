"""
NordenCallPage — Page object for the Teams Rooms dial screen (NordenCallActivity).

Reached by tapping the Call button on the home screen (MainPage.click_call()).
Provides a search/dial field and a Call button that activates once a valid
contact or number is entered.

Obtain via device.ui.norden_call (lazy property on MtrUi).

Usage:
    device.ui.norden_call.is_visible()
    device.ui.norden_call.type_name_or_number("Alice")
    device.ui.norden_call.click_call()
    device.ui.norden_call.click_back()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage
from common.ui_mtr import _MTR_PACKAGE as _PKG

_SEARCH_BOX_ID = f"{_PKG}:id/search_contact_box"
_CALL_BUTTON_ID = f"{_PKG}:id/call_button"
_BACK_BUTTON_ID = f"{_PKG}:id/back_layout"


class NordenCallPage(BasePage):
    """Page object for the Teams Rooms dial / contact-search screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the dial screen is displayed. Polls until timeout if > 0."""
        def check():
            return self._ui.find_element(resource_id=_SEARCH_BOX_ID) is not None
        return self._poll(check, timeout)

    def type_name_or_number(self, text: str) -> bool:
        """Tap the search field and type text. Returns True if the field was found."""
        if not self._ui.tap_element(resource_id=_SEARCH_BOX_ID):
            return False
        self._ui.input_text(text)
        return True

    def click_call(self) -> bool:
        """Tap the Call button (only active once a valid contact/number is entered)."""
        return self._tap([
            {"resource_id": _CALL_BUTTON_ID, "text": "Call"},
            {"resource_id": _CALL_BUTTON_ID},
        ])

    def click_back(self) -> bool:
        """Tap the Back button to return to the home screen."""
        return self._tap([
            {"resource_id": _BACK_BUTTON_ID, "content_desc": "Back"},
            {"content_desc": "Back"},
        ])

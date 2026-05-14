"""
JoinWithIdPage — Page object for the Teams Rooms "Join with an ID" screen.

Reached by tapping the Join with an ID button on the home screen
(MainPage.click_join_with_an_id()).

Obtain via device.ui.join_with_id (lazy property on MtrUi).

Usage:
    device.ui.join_with_id.is_visible()
    device.ui.join_with_id.enter_meeting_id("123 456 789")
    device.ui.join_with_id.enter_passcode("abc123")
    device.ui.join_with_id.click_join()
    device.ui.join_with_id.click_back()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage
from common.ui_mtr import _MTR_PACKAGE as _PKG

_CONTAINER_ID    = f"{_PKG}:id/meeting_join_by_code_container"
_MEETING_ID_ID   = f"{_PKG}:id/code_edit_text"
_PASSCODE_ID     = f"{_PKG}:id/passcode_edit_text"
_JOIN_BUTTON_ID  = f"{_PKG}:id/join_meeting_button"
_BACK_BUTTON_ID  = f"{_PKG}:id/back_layout"


class JoinWithIdPage(BasePage):
    """Page object for the 'Join a Teams meeting with an ID' screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the join-with-ID screen is displayed. Polls until timeout if > 0."""
        def check():
            return self._ui.find_element(resource_id=_CONTAINER_ID) is not None
        return self._poll(check, timeout)

    def enter_meeting_id(self, meeting_id: str) -> bool:
        """Tap the meeting ID field and type the ID. Returns True if the field was found."""
        if not self._ui.tap_element(resource_id=_MEETING_ID_ID):
            return False
        self._ui.input_text(meeting_id)
        return True

    def enter_passcode(self, passcode: str) -> bool:
        """Tap the passcode field and type the passcode. Returns True if the field was found."""
        if not self._ui.tap_element(resource_id=_PASSCODE_ID):
            return False
        self._ui.input_text(passcode)
        return True

    def click_join(self) -> bool:
        """Tap the 'Join Teams meeting' button. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": _JOIN_BUTTON_ID, "text": "Join Teams meeting"},
            {"resource_id": _JOIN_BUTTON_ID},
        ])

    def click_back(self) -> bool:
        """Tap the Back button to return to the home screen."""
        return self._tap([
            {"resource_id": _BACK_BUTTON_ID, "content_desc": "Back"},
            {"content_desc": "Back"},
        ])

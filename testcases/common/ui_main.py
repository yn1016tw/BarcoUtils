"""
MainPage — Page object for the Teams Rooms home screen.

Provides visibility checks and one-tap helpers for each main-nav button.
Obtain via device.ui.main (lazy property on MtrUi).

Usage:
    device.ui.main.is_visible()
    device.ui.main.click_meet_now()
    device.ui.main.click_call()
    device.ui.main.click_share()
    device.ui.main.click_join_with_an_id()
    device.ui.main.click_more()

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage
from common.ui_mtr import _MTR_PACKAGE as _PKG

_BUTTONS: dict[str, list[dict]] = {
    "meet_now":        [{"resource_id": f"{_PKG}:id/meetnow_btn"},            {"content_desc": "Meet now"}],
    "call":            [{"resource_id": f"{_PKG}:id/dialpad_btn"},             {"content_desc": "Call"}],
    "share":           [{"resource_id": f"{_PKG}:id/projecting_btn"},          {"content_desc": "Share"}],
    "join_with_an_id": [{"resource_id": f"{_PKG}:id/meeting_join_Code_btn"},   {"content_desc": "Join with an ID"}],
    "more":            [{"resource_id": f"{_PKG}:id/more_btn"},                {"content_desc": "More"}],
}

_HOME_LANDMARKS = [
    {"resource_id": f"{_PKG}:id/meetnow_btn"},
    {"content_desc": "Meet now"},
]


class MainPage(BasePage):
    """Page object for the MTR / Teams Rooms home screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the Teams Rooms home screen is displayed. Polls until timeout if > 0."""
        def check():
            for kwargs in _HOME_LANDMARKS:
                if self._ui.find_element(**kwargs):
                    return True
            return False
        return self._poll(check, timeout)

    def click_meet_now(self) -> bool:
        return self._tap(_BUTTONS["meet_now"])

    def click_call(self) -> bool:
        return self._tap(_BUTTONS["call"])

    def click_share(self) -> bool:
        return self._tap(_BUTTONS["share"])

    def click_join_with_an_id(self) -> bool:
        return self._tap(_BUTTONS["join_with_an_id"])

    def click_more(self) -> bool:
        return self._tap(_BUTTONS["more"])

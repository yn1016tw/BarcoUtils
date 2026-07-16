"""
ClickShareMainPage — Page object for the ClickShare mode home screen.

Applies to Duvel (ClickShare/MTR) and God (ClickShare-only) units running the
`com.barco.clickshare.uicomposer` app. The screen is passive (no clickable
buttons — sharing is started by pressing the physical ClickShare Button), so
this page object only exposes visibility checks and text/content-desc getters.

Obtain via device.ui.clickshare_main (lazy property on MtrUi).

Usage:
    device.ui.clickshare_main.is_visible()
    device.ui.clickshare_main.get_device_name()
    device.ui.clickshare_main.get_share_instruction()

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

from common.ui_base import BasePage

_HOME_LANDMARKS = [
    {"content_desc": "ClickShare Logo"},
    {"text_contains": "Press the Button to share"},
]


class ClickShareMainPage(BasePage):
    """Page object for the ClickShare mode home screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the ClickShare home screen is displayed. Polls until timeout if > 0."""
        def check():
            for kwargs in _HOME_LANDMARKS:
                if self._ui.find_element(**kwargs):
                    return True
            return False
        return self._poll(check, timeout)

    def get_device_name(self) -> str | None:
        """Return the device name shown top-left (e.g. 'ClickShare-9752000162')."""
        el = self._ui.find_element(text_contains="ClickShare-")
        return el["text"] if el else None

    def get_date(self) -> str | None:
        """Return the displayed date string (e.g. 'THURSDAY, JULY 16')."""
        el = self._ui.find_element(text_contains=",")
        return el["text"] if el else None

    def get_time(self) -> str | None:
        """Return the displayed time string (e.g. '11:06 AM')."""
        for suffix in ("AM", "PM"):
            el = self._ui.find_element(text_contains=suffix)
            if el:
                return el["text"]
        return None

    def get_share_instruction(self) -> str | None:
        """Return the on-screen instruction text (e.g. 'Press the Button to share')."""
        el = self._ui.find_element(text_contains="Press the Button to share")
        return el["text"] if el else None

"""
InvitePeoplePage — Page object for the "Invite people to join you" dialog
that appears after tapping Meet now in Teams Rooms.

Access via device.ui.invite_people

Usage:
    device.ui.invite_people.is_visible()
    device.ui.invite_people.dismiss()
    device.ui.invite_people.click_add_participants()
    device.ui.invite_people.get_meeting_id()   # "349 124 040 953 242"
    device.ui.invite_people.get_passcode()     # "wY2yd2L3"
    device.ui.invite_people.get_dial_in_info() # "+32 2 897 92 05(Toll)\nConference ID: 969 327 92#"

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from common.ui_base import BasePage
from common.ui_mtr import _MTR_PACKAGE as _PKG


class InvitePeoplePage(BasePage):
    """Page object for the Teams Rooms 'Invite people to join you' dialog."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the invite dialog is displayed. Polls until timeout if > 0."""
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/invite_button")
                or self._ui.find_element(text="Invite people to join you")
            ),
            timeout,
        )

    def dismiss(self) -> bool:
        """Tap the Dismiss (X) button. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/icn_dismiss"},
            {"content_desc": "Dismiss"},
        ])

    def click_add_participants(self) -> bool:
        """Tap the 'Add participants' button. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/invite_button"},
            {"text": "Add participants"},
        ])

    def get_meeting_id(self) -> str | None:
        """Return the meeting ID string, or None if not found."""
        return self._parse_info().get("meeting_id")

    def get_passcode(self) -> str | None:
        """Return the passcode string, or None if not found."""
        return self._parse_info().get("passcode")

    def get_dial_in_info(self) -> str | None:
        """Return the dial-in phone + conference ID string, or None if not found."""
        return self._parse_info().get("dial_in")

    def _parse_info(self) -> dict:
        try:
            root = ET.fromstring(self._ui.dump_ui())
        except ET.ParseError:
            return {}

        nodes = list(root.iter("node"))
        info = {}
        for i, node in enumerate(nodes):
            text = node.get("text", "")
            if "Meeting ID" in text and i + 1 < len(nodes):
                info["meeting_id"] = nodes[i + 1].get("text", "").strip()
            elif "Passcode" in text and i + 1 < len(nodes):
                info["passcode"] = nodes[i + 1].get("text", "").strip()
            elif ("Toll" in text or "Conference ID" in text) and text.strip():
                info["dial_in"] = text.strip()
        return info

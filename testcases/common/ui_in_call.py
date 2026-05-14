"""
InCallPage — Page object for the Teams Rooms active call screen.

Access via device.ui.in_call

Usage:
    device.ui.in_call.is_visible()
    device.ui.in_call.get_meeting_title()   # "Meeting with mtr_p_ 25"
    device.ui.in_call.hang_up()
    device.ui.in_call.mute()
    device.ui.in_call.toggle_camera()
    device.ui.in_call.change_video()
    device.ui.in_call.show_participants()
    device.ui.in_call.reactions()
    device.ui.in_call.share()
    device.ui.in_call.more_options()
    device.ui.in_call.change_view()
    device.ui.in_call.volume_up()
    device.ui.in_call.volume_down()

Author: James Yang <yn1016@gmail.com>
"""

from __future__ import annotations

from common.ui_base import BasePage
from common.ui_mtr import _MTR_PACKAGE as _PKG


class InCallPage(BasePage):
    """Page object for the Teams Rooms active call screen."""

    def is_visible(self, timeout: int = 0) -> bool:
        """Return True if the in-call screen is displayed. Polls until timeout if > 0.

        Requires both incall_fragment_root (confirms the call fragment is loaded)
        and call_end_button / Hang up (confirms controls are ready). Checking only
        the hang-up button is insufficient — it also appears during the joining/
        connecting transition before the call is fully entered.
        """
        return self._poll(
            lambda: bool(
                self._ui.find_element(resource_id=f"{_PKG}:id/incall_fragment_root")
                and (
                    self._ui.find_element(resource_id=f"{_PKG}:id/call_end_button")
                    or self._ui.find_element(content_desc="Hang up")
                )
            ),
            timeout,
        )

    def get_meeting_title(self) -> str | None:
        """Return the meeting title from the action bar, or None if not found."""
        el = (
            self._ui.find_element(resource_id=f"{_PKG}:id/action_bar_title_text_norden")
            or self._ui.find_element(resource_id=f"{_PKG}:id/action_bar_title_text")
        )
        return el["text"] if el else None

    def hang_up(self) -> bool:
        """Tap the Hang up button. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_end_button"},
            {"content_desc": "Hang up"},
            {"content_desc": "End call"},
            {"content_desc": "Leave"},
        ])

    def mute(self) -> bool:
        """Toggle mute. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_control_mute"},
            {"content_desc": "Mute"},
            {"content_desc": "Unmute"},
        ])

    def toggle_camera(self) -> bool:
        """Toggle camera on/off. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_control_video"},
            {"content_desc": "Turn off camera"},
            {"content_desc": "Turn on camera"},
        ])

    def change_video(self) -> bool:
        """Tap Change Video (camera source switcher). Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_change_video"},
            {"content_desc": "Change Video"},
        ])

    def show_participants(self) -> bool:
        """Open the participants panel. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_control_roster"},
            {"content_desc": "Show participants"},
        ])

    def reactions(self) -> bool:
        """Open the reactions panel. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_control_reactions_button"},
            {"content_desc": "Reactions"},
        ])

    def share(self) -> bool:
        """Open the share content panel. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_control_share_button"},
            {"content_desc": "Share"},
        ])

    def more_options(self) -> bool:
        """Open the More options menu. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_more_options"},
            {"content_desc": "More options"},
        ])

    def change_view(self) -> bool:
        """Tap the Change your view button. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/call_control_content_share_mode"},
            {"content_desc": "Change your view"},
        ])

    def volume_up(self) -> bool:
        """Tap Volume up. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/volume_plus"},
            {"content_desc": "Volume up"},
        ])

    def volume_down(self) -> bool:
        """Tap Volume down. Returns True if found and tapped."""
        return self._tap([
            {"resource_id": f"{_PKG}:id/volume_minus"},
            {"content_desc": "Volume down"},
        ])

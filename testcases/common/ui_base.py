"""
BasePage — shared base class for all BarcoUtils page objects.

Author: James Yang <james.yang@barco.com>
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.ui_mtr import MtrUi


class BasePage:
    """Shared base for all MTR page objects."""

    def __init__(self, ui: "MtrUi") -> None:
        self._ui = ui

    def _tap(self, candidates: list[dict]) -> bool:
        """Try each candidate kwarg dict against tap_element until one succeeds."""
        for kwargs in candidates:
            if self._ui.tap_element(**kwargs):
                return True
        return False

    def _poll(self, check_fn, timeout: int) -> bool:
        """Poll check_fn every second. If timeout <= 0, run once. Returns True if check passed."""
        if timeout <= 0:
            return check_fn()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if check_fn():
                return True
            time.sleep(1)
        return False

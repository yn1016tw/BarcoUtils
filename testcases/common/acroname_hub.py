# Author: James Yang <james.yang@barco.com>

import brainstem
from brainstem.link import Spec

_PORT_MAX = 7


class AcronameHub:
    """Thin wrapper around brainstem USBHub3p SDK."""

    def __init__(self):
        self._hub = brainstem.stem.USBHub3p()
        self._connected = False

    def connect(self, serial: int | None = None) -> bool:
        try:
            if serial is not None:
                err = self._hub.connectFromSerial(serial)
            else:
                err = self._hub.discoverAndConnect(Spec.USB)
            self._connected = (err == 0)
            return self._connected
        except Exception:
            return False

    def disconnect(self) -> None:
        try:
            self._hub.disconnect()
        except Exception:
            pass
        self._connected = False

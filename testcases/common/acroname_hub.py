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

    # ------------------------------------------------------------------
    # Port validation helper
    # ------------------------------------------------------------------

    def _valid_port(self, port: int) -> bool:
        return 0 <= port <= _PORT_MAX

    # ------------------------------------------------------------------
    # Port power
    # ------------------------------------------------------------------

    def set_port_power(self, port: int, enable: bool) -> bool:
        if not self._valid_port(port):
            return False
        try:
            return self._hub.usb.setPowerEnable(port, enable) == 0
        except Exception:
            return False

    def get_port_power(self, port: int) -> bool | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getPowerEnable(port)
            return result.value if result.error == 0 else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Port data
    # ------------------------------------------------------------------

    def set_port_data(self, port: int, enable: bool) -> bool:
        if not self._valid_port(port):
            return False
        try:
            return self._hub.usb.setDataEnable(port, enable) == 0
        except Exception:
            return False

    def get_port_data(self, port: int) -> bool | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getDataEnable(port)
            return result.value if result.error == 0 else None
        except Exception:
            return None

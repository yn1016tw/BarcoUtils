# Author: James Yang <james.yang@barco.com>

_PORT_MAX = 7
_UPSTREAM_MAX = 1  # USBHub3+ supports 2 upstream host ports (0 and 1)


class AcronameHub:
    """Thin wrapper around brainstem USBHub3p SDK."""

    def __init__(self):
        self._hub = None
        self._connected = False

    def connect(self, serial: int | None = None) -> bool:
        try:
            import brainstem
            from brainstem.link import Spec
            if self._hub is None:
                self._hub = brainstem.stem.USBHub3p()
            if serial is not None:
                err = self._hub.connectFromSerial(serial, Spec.USB)
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

    # ------------------------------------------------------------------
    # Port speed
    # ------------------------------------------------------------------

    _SPEED_MAP = {"auto": 0, "ss": 1, "hs": 2, "fs": 3, "ls": 4}

    def set_port_speed(self, port: int, speed: str) -> bool:
        if not self._valid_port(port):
            return False
        mode = self._SPEED_MAP.get(speed)  # 0 is valid (auto), so check is None not falsy
        if mode is None:
            return False
        try:
            return self._hub.usb.setPortMode(port, mode) == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Current / voltage measurement
    # ------------------------------------------------------------------

    def get_port_current(self, port: int) -> float | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getCurrentMicroAmps(port)
            return result.value / 1000.0 if result.error == 0 else None
        except Exception:
            return None

    def get_port_voltage(self, port: int) -> float | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getVoltageMillivolts(port)
            return float(result.value) if result.error == 0 else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Boost charge (BC1.2)
    # ------------------------------------------------------------------

    def set_port_boost_charge(self, port: int, enable: bool) -> bool:
        if not self._valid_port(port):
            return False
        try:
            return self._hub.usb.setBoostEnable(port, enable) == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Upstream host port switching
    # ------------------------------------------------------------------

    def switch_usb_port(self, port: int, exclusive: bool = True) -> bool:
        if not 0 <= port <= _UPSTREAM_MAX:
            return False
        try:
            err = self._hub.usb.setUpstreamPort(port)
            if err != 0:
                return False
            other = 1 - port
            # exclusive: disable the other upstream so only one host sees the hub
            # non-exclusive: re-enable it so both hosts can access simultaneously
            self._hub.usb.setUpstreamPortEnable(other, not exclusive)
            return True
        except Exception:
            return False

    def get_upstream_port(self) -> int | None:
        try:
            result = self._hub.usb.getUpstreamPort()
            return result.value if result.error == 0 else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Hub info
    # ------------------------------------------------------------------

    def hub_serial(self) -> int | None:
        try:
            result = self._hub.system.getSerialNumber()
            return result.value if result.error == 0 else None
        except Exception:
            return None

    def hub_firmware_version(self) -> str | None:
        try:
            result = self._hub.system.getVersion()
            return str(result.value) if result.error == 0 else None
        except Exception:
            return None

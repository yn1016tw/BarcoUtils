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
    # Port power  (setPowerEnable/Disable take channel only, no bool arg)
    # ------------------------------------------------------------------

    def set_port_power(self, port: int, enable: bool) -> bool:
        if not self._valid_port(port):
            return False
        try:
            if enable:
                return self._hub.usb.setPowerEnable(port) == 0
            else:
                return self._hub.usb.setPowerDisable(port) == 0
        except Exception:
            return False

    def get_port_power(self, port: int) -> bool | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getPortState(port)
            if result.error != 0:
                return None
            return bool(result.value & self._hub.usb.PORT_MODE_VBUS_ENABLE)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Port data  (setDataEnable/Disable take channel only, no bool arg)
    # ------------------------------------------------------------------

    def set_port_data(self, port: int, enable: bool) -> bool:
        if not self._valid_port(port):
            return False
        try:
            if enable:
                return self._hub.usb.setDataEnable(port) == 0
            else:
                return self._hub.usb.setDataDisable(port) == 0
        except Exception:
            return False

    def get_port_data(self, port: int) -> bool | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getPortState(port)
            if result.error != 0:
                return None
            return bool(result.value & self._hub.usb.PORT_MODE_USB2_A_ENABLE)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Port speed  (setHiSpeedData*/setSuperSpeedData* per channel)
    # ------------------------------------------------------------------

    def set_port_speed(self, port: int, speed: str) -> bool:
        if not self._valid_port(port):
            return False
        try:
            usb = self._hub.usb
            if speed == "auto":
                # enable both HS and SS; hub negotiates
                r1 = usb.setHiSpeedDataEnable(port)
                r2 = usb.setSuperSpeedDataEnable(port)
                return r1 == 0 and r2 == 0
            elif speed == "ss":
                r1 = usb.setSuperSpeedDataEnable(port)
                r2 = usb.setHiSpeedDataDisable(port)
                return r1 == 0 and r2 == 0
            elif speed == "hs":
                r1 = usb.setHiSpeedDataEnable(port)
                r2 = usb.setSuperSpeedDataDisable(port)
                return r1 == 0 and r2 == 0
            elif speed in ("fs", "ls"):
                # disable both; device falls back to FS/LS
                r1 = usb.setHiSpeedDataDisable(port)
                r2 = usb.setSuperSpeedDataDisable(port)
                return r1 == 0 and r2 == 0
            else:
                return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Current / voltage measurement
    # getPortCurrent returns µA; getPortVoltage returns µV
    # ------------------------------------------------------------------

    def get_port_current(self, port: int) -> float | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getPortCurrent(port)
            return result.value / 1000.0 if result.error == 0 else None  # µA -> mA
        except Exception:
            return None

    def get_port_voltage(self, port: int) -> float | None:
        if not self._valid_port(port):
            return None
        try:
            result = self._hub.usb.getPortVoltage(port)
            return result.value / 1000.0 if result.error == 0 else None  # µV -> mV
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Boost charge (BC1.2) — hub-wide, not per-port
    # ------------------------------------------------------------------

    def set_boost_charge(self, enable: bool) -> bool:
        try:
            usb = self._hub.usb
            setting = usb.BOOST_8_PERCENT if enable else usb.BOOST_0_PERCENT
            return usb.setDownstreamBoostMode(setting) == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Port switching (downstream ports 0-7)
    # exclusive=True  -> power on target port, power off all others
    # exclusive=False -> power on target port only, leave others unchanged
    # ------------------------------------------------------------------

    def switch_port(self, port: int, exclusive: bool = True) -> bool:
        if not self._valid_port(port):
            return False
        try:
            usb = self._hub.usb
            if exclusive:
                for p in range(_PORT_MAX + 1):
                    if p != port:
                        usb.setPortDisable(p)
            return usb.setPortEnable(port) == 0
        except Exception:
            return False

    def set_upstream_port(self, port: int) -> bool:
        if not 0 <= port <= _UPSTREAM_MAX:
            return False
        try:
            usb = self._hub.usb
            mode = usb.UPSTREAM_MODE_PORT_0 if port == 0 else usb.UPSTREAM_MODE_PORT_1
            return usb.setUpstreamMode(mode) == 0
        except Exception:
            return False

    def get_upstream_port(self) -> int | None:
        try:
            result = self._hub.usb.getUpstreamState()
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

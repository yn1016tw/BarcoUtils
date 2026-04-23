"""
AcronameHubSwitcher — standalone controller for the Acroname Programmable USB 3.0 Hub (8 ports).

Requires the `brainstem` Python package (Windows only; install the wheel provided by Acroname).

Usage:
    switcher = AcronameHubSwitcher(
        serial="4E0918F",
        hosts={"PC": 0, "W4DUVEL": 1},
        ports={"USB0": 0, "USB1": 1, "USB2": 2, "USB3": 3,
               "USB4": 4, "USB5": 5, "USB6": 6, "USB7": 7},
    )
    switcher.switch_to_port("USB3", host="W4DUVEL", init_delay=30)
    switcher.switch_to_port("USB5", host="W4DUVEL", init_delay=180)  # slow peripheral
    switcher.disable_all_ports()
"""

import time
from contextlib import contextmanager, suppress

import brainstem
import brainstem.result


class AcronameConnectionError(RuntimeError):
    pass


class AcronameHubSwitcher:
    """
    Control the Acroname Programmable Industrial USB 3.0 Hub (USBHub3p, 8 downstream ports).

    Hub has 2 selectable upstream ports (hosts) and 8 individually switchable downstream ports.
    All brainstem connections are opened per-operation and closed immediately after — the same
    pattern used by TEnTo's AcronameUsbHub3p.
    """

    def __init__(self, serial: str, hosts: dict[str, int], ports: dict[str, int]):
        """
        :param serial: Hub serial number in hex (printed on the label), e.g. "4E0918F"
        :param hosts:  Map of host name → upstream port index, e.g. {"PC": 0, "W4DUVEL": 1}
        :param ports:  Map of port label → downstream port index (0-7),
                       e.g. {"USB0": 0, "USB1": 1, ..., "USB7": 7}
        """
        self._serial = int(serial, 16)
        self._hosts = hosts
        self._ports = ports
        self._active_port: str | None = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @contextmanager
    def _connection(self):
        hub = brainstem.stem.USBHub3p()
        result = hub.connect(self._serial)
        try:
            if result is not brainstem.result.Result.NO_ERROR:
                raise AcronameConnectionError(
                    f"Cannot connect to Acroname hub (serial=0x{self._serial:X})"
                )
            yield hub
        finally:
            with suppress(Exception):
                hub.disconnect()

    def _port_index(self, port: str) -> int:
        if port not in self._ports:
            raise KeyError(f"Unknown port label '{port}'. Known: {list(self._ports)}")
        return self._ports[port]

    def _host_index(self, host: str) -> int:
        if host not in self._hosts:
            raise KeyError(f"Unknown host name '{host}'. Known: {list(self._hosts)}")
        return self._hosts[host]

    # ------------------------------------------------------------------
    # Downstream port control
    # ------------------------------------------------------------------

    def enable_port(self, port: str) -> None:
        """Enable power and data on a downstream port."""
        with self._connection() as hub:
            hub.usb.setPortEnable(self._port_index(port))

    def disable_port(self, port: str) -> None:
        """Disable power and data on a downstream port."""
        with self._connection() as hub:
            hub.usb.setPortDisable(self._port_index(port))

    def disable_all_ports(self) -> None:
        """Disable all configured downstream ports."""
        with self._connection() as hub:
            for idx in self._ports.values():
                hub.usb.setPortDisable(idx)
        self._active_port = None

    def is_port_enabled(self, port: str) -> bool:
        """Return True if the downstream port is fully enabled (Vbus + USB2 + USB3 data)."""
        with self._connection() as hub:
            status = hub.usb.getPortState(self._port_index(port)).value
        return (status & 0b1011) == 0b1011

    # ------------------------------------------------------------------
    # Upstream host selection
    # ------------------------------------------------------------------

    def switch_host(self, host: str) -> None:
        """Select which upstream host port the hub connects to."""
        with self._connection() as hub:
            hub.usb.setUpstreamMode(self._host_index(host))

    # ------------------------------------------------------------------
    # High-level switch  (mirrors _switch_to_usb_port in the reference test)
    # ------------------------------------------------------------------

    def switch_to_port(self, port: str, host: str | None = None, init_delay: int = 30) -> None:
        """
        Deactivate the current port, activate a new one, optionally switch upstream host,
        then wait for the peripheral to enumerate.

        Sequence (matches _switch_to_usb_port / _set_acroname_upstream_port):
          1. Disable the previously active downstream port (if any).
          2. Enable the requested downstream port.
          3. Switch upstream host (if host is given).
          4. Sleep init_delay seconds for the peripheral to boot.

        :param port:       Downstream port label to activate, e.g. "USB3"
        :param host:       Upstream host name to select, e.g. "W4DUVEL". None = keep current.
        :param init_delay: Seconds to wait after enabling the port (default 30).
                           Pass 180 for slow peripherals such as Sennheiser TC Bar.
        """
        print(f"  [USB] Switching to {port}" + (f" (host={host})" if host else ""))
        with self._connection() as hub:
            if self._active_port is not None:
                hub.usb.setPortDisable(self._port_index(self._active_port))
            hub.usb.setPortEnable(self._port_index(port))
            if host is not None:
                hub.usb.setUpstreamMode(self._host_index(host))
        self._active_port = port
        if init_delay > 0:
            print(f"  [USB] Waiting {init_delay}s for peripheral to enumerate...")
            time.sleep(init_delay)

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def firmware_version(self) -> str:
        """Return hub firmware version as 'major.minor.patch'."""
        with self._connection() as hub:
            raw = hub.system.getVersion().value
        major = (raw >> 28) & 0xF
        minor = (raw >> 24) & 0xF
        patch = raw & 0xFFFFFF
        return f"{major}.{minor}.{patch}"

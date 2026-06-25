# Author: James Yang <james.yang@barco.com>
"""
Sample: AcronameHub USB switch via USBHub3+

Usage:
    python testcases/test_usb_switch.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common.acroname_hub import AcronameHub, UpstreamMode

hub = AcronameHub()
assert hub.connect(), "connect failed"
print(f"connected: serial=0x{hub.hub_serial():08X}  firmware={hub.hub_firmware_version()}")

# upstream mode
hub.set_upstream_mode(UpstreamMode.PORT_0)
print(f"upstream mode: {hub.get_upstream_mode().name}")

# switch downstream ports
for port in [0, 1, 2]:
    hub.switch_port(port)
    v = hub.get_port_voltage(port)
    i = hub.get_port_current(port)
    print(f"port {port}: {v:.0f} mV  {i:.1f} mA")
    time.sleep(0.5)

hub.disconnect()

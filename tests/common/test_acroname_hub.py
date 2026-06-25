import sys
import types
from unittest.mock import MagicMock, call
import pytest

# ---------------------------------------------------------------------------
# Stub out brainstem before importing AcronameHub
# ---------------------------------------------------------------------------
_bs = types.ModuleType("brainstem")
_bs.stem = types.ModuleType("brainstem.stem")
_bs.link = types.ModuleType("brainstem.link")
_bs.link.Spec = MagicMock()
_bs.link.Spec.USB = 0
sys.modules["brainstem"] = _bs
sys.modules["brainstem.stem"] = _bs.stem
sys.modules["brainstem.link"] = _bs.link

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "testcases"))

from common.acroname_hub import AcronameHub


def _make_ok_result(value):
    r = MagicMock()
    r.error = 0
    r.value = value
    return r


def _make_err_result():
    r = MagicMock()
    r.error = 1
    r.value = None
    return r


def _make_hub(connect_err=0):
    mock_stem = MagicMock()
    mock_stem.discoverAndConnect.return_value = connect_err
    # upstream mode constants
    mock_stem.usb.UPSTREAM_MODE_PORT_0 = 0
    mock_stem.usb.UPSTREAM_MODE_PORT_1 = 1
    mock_stem.usb.UPSTREAM_MODE_AUTO = 2
    # boost constants
    mock_stem.usb.BOOST_0_PERCENT = 0
    mock_stem.usb.BOOST_8_PERCENT = 2
    # port state bitmask constants
    mock_stem.usb.PORT_MODE_VBUS_ENABLE = 6
    mock_stem.usb.PORT_MODE_USB2_A_ENABLE = 4
    _bs.stem.USBHub3p = MagicMock(return_value=mock_stem)
    hub = AcronameHub()
    hub.connect()
    return hub, mock_stem


# ------------------------------------------------------------------
# connect / disconnect
# ------------------------------------------------------------------

def test_connect_success():
    mock_stem = MagicMock()
    mock_stem.discoverAndConnect.return_value = 0
    _bs.stem.USBHub3p = MagicMock(return_value=mock_stem)
    hub = AcronameHub()
    assert hub.connect() is True
    mock_stem.discoverAndConnect.assert_called_once_with(_bs.link.Spec.USB)


def test_connect_with_serial():
    mock_stem = MagicMock()
    mock_stem.connectFromSerial.return_value = 0
    _bs.stem.USBHub3p = MagicMock(return_value=mock_stem)
    hub = AcronameHub()
    assert hub.connect(serial=0xABCD1234) is True
    mock_stem.connectFromSerial.assert_called_once_with(0xABCD1234, _bs.link.Spec.USB)


def test_connect_failure():
    mock_stem = MagicMock()
    mock_stem.discoverAndConnect.return_value = 1
    _bs.stem.USBHub3p = MagicMock(return_value=mock_stem)
    hub = AcronameHub()
    assert hub.connect() is False


def test_disconnect_calls_sdk():
    hub, stem = _make_hub()
    hub.disconnect()
    stem.disconnect.assert_called_once()


def test_disconnect_before_connect_does_not_raise():
    hub = AcronameHub()
    hub.disconnect()


# ------------------------------------------------------------------
# Port power
# ------------------------------------------------------------------

def test_set_port_power_enable():
    hub, stem = _make_hub()
    stem.usb.setPowerEnable.return_value = 0
    assert hub.set_port_power(0, True) is True
    stem.usb.setPowerEnable.assert_called_once_with(0)


def test_set_port_power_disable():
    hub, stem = _make_hub()
    stem.usb.setPowerDisable.return_value = 0
    assert hub.set_port_power(3, False) is True
    stem.usb.setPowerDisable.assert_called_once_with(3)


def test_set_port_power_sdk_error():
    hub, stem = _make_hub()
    stem.usb.setPowerEnable.return_value = 1
    assert hub.set_port_power(0, True) is False


def test_set_port_power_invalid_port():
    hub, stem = _make_hub()
    assert hub.set_port_power(8, True) is False
    stem.usb.setPowerEnable.assert_not_called()


def test_get_port_power_true():
    hub, stem = _make_hub()
    stem.usb.getPortState.return_value = _make_ok_result(6)
    assert hub.get_port_power(0) is True


def test_get_port_power_false():
    hub, stem = _make_hub()
    stem.usb.getPortState.return_value = _make_ok_result(0)
    assert hub.get_port_power(0) is False


def test_get_port_power_error():
    hub, stem = _make_hub()
    stem.usb.getPortState.return_value = _make_err_result()
    assert hub.get_port_power(0) is None


def test_get_port_power_invalid_port():
    hub, stem = _make_hub()
    assert hub.get_port_power(8) is None
    stem.usb.getPortState.assert_not_called()


# ------------------------------------------------------------------
# Port data
# ------------------------------------------------------------------

def test_set_port_data_enable():
    hub, stem = _make_hub()
    stem.usb.setDataEnable.return_value = 0
    assert hub.set_port_data(2, True) is True
    stem.usb.setDataEnable.assert_called_once_with(2)


def test_set_port_data_disable():
    hub, stem = _make_hub()
    stem.usb.setDataDisable.return_value = 0
    assert hub.set_port_data(2, False) is True
    stem.usb.setDataDisable.assert_called_once_with(2)


def test_set_port_data_sdk_error():
    hub, stem = _make_hub()
    stem.usb.setDataEnable.return_value = 1
    assert hub.set_port_data(2, True) is False


def test_set_port_data_invalid_port():
    hub, stem = _make_hub()
    assert hub.set_port_data(-1, True) is False
    stem.usb.setDataEnable.assert_not_called()


def test_get_port_data_true():
    hub, stem = _make_hub()
    stem.usb.getPortState.return_value = _make_ok_result(4)
    assert hub.get_port_data(1) is True


def test_get_port_data_false():
    hub, stem = _make_hub()
    stem.usb.getPortState.return_value = _make_ok_result(0)
    assert hub.get_port_data(1) is False


def test_get_port_data_error():
    hub, stem = _make_hub()
    stem.usb.getPortState.return_value = _make_err_result()
    assert hub.get_port_data(1) is None


def test_get_port_data_invalid_port():
    hub, stem = _make_hub()
    assert hub.get_port_data(-1) is None
    stem.usb.getPortState.assert_not_called()


# ------------------------------------------------------------------
# Port speed
# ------------------------------------------------------------------

def test_set_port_speed_auto():
    hub, stem = _make_hub()
    stem.usb.setHiSpeedDataEnable.return_value = 0
    stem.usb.setSuperSpeedDataEnable.return_value = 0
    assert hub.set_port_speed(0, "auto") is True
    stem.usb.setHiSpeedDataEnable.assert_called_once_with(0)
    stem.usb.setSuperSpeedDataEnable.assert_called_once_with(0)


def test_set_port_speed_ss():
    hub, stem = _make_hub()
    stem.usb.setSuperSpeedDataEnable.return_value = 0
    stem.usb.setHiSpeedDataDisable.return_value = 0
    assert hub.set_port_speed(0, "ss") is True
    stem.usb.setSuperSpeedDataEnable.assert_called_once_with(0)
    stem.usb.setHiSpeedDataDisable.assert_called_once_with(0)


def test_set_port_speed_hs():
    hub, stem = _make_hub()
    stem.usb.setHiSpeedDataEnable.return_value = 0
    stem.usb.setSuperSpeedDataDisable.return_value = 0
    assert hub.set_port_speed(0, "hs") is True


def test_set_port_speed_fs():
    hub, stem = _make_hub()
    stem.usb.setHiSpeedDataDisable.return_value = 0
    stem.usb.setSuperSpeedDataDisable.return_value = 0
    assert hub.set_port_speed(0, "fs") is True


def test_set_port_speed_ls():
    hub, stem = _make_hub()
    stem.usb.setHiSpeedDataDisable.return_value = 0
    stem.usb.setSuperSpeedDataDisable.return_value = 0
    assert hub.set_port_speed(0, "ls") is True


def test_set_port_speed_unknown_string():
    hub, stem = _make_hub()
    assert hub.set_port_speed(0, "turbo") is False
    stem.usb.setHiSpeedDataEnable.assert_not_called()


def test_set_port_speed_invalid_port():
    hub, stem = _make_hub()
    assert hub.set_port_speed(8, "ss") is False
    stem.usb.setSuperSpeedDataEnable.assert_not_called()


def test_set_port_speed_sdk_error():
    hub, stem = _make_hub()
    stem.usb.setSuperSpeedDataEnable.return_value = 1
    stem.usb.setHiSpeedDataDisable.return_value = 0
    assert hub.set_port_speed(0, "ss") is False


# ------------------------------------------------------------------
# Current / voltage
# ------------------------------------------------------------------

def test_get_port_current_ok():
    hub, stem = _make_hub()
    stem.usb.getPortCurrent.return_value = _make_ok_result(450000)
    assert hub.get_port_current(0) == pytest.approx(450.0)


def test_get_port_current_error():
    hub, stem = _make_hub()
    stem.usb.getPortCurrent.return_value = _make_err_result()
    assert hub.get_port_current(0) is None


def test_get_port_current_invalid_port():
    hub, stem = _make_hub()
    assert hub.get_port_current(8) is None
    stem.usb.getPortCurrent.assert_not_called()


def test_get_port_voltage_ok():
    hub, stem = _make_hub()
    stem.usb.getPortVoltage.return_value = _make_ok_result(5000000)
    assert hub.get_port_voltage(0) == pytest.approx(5000.0)


def test_get_port_voltage_error():
    hub, stem = _make_hub()
    stem.usb.getPortVoltage.return_value = _make_err_result()
    assert hub.get_port_voltage(0) is None


def test_get_port_voltage_invalid_port():
    hub, stem = _make_hub()
    assert hub.get_port_voltage(8) is None
    stem.usb.getPortVoltage.assert_not_called()


# ------------------------------------------------------------------
# Boost charge (hub-wide)
# ------------------------------------------------------------------

def test_set_boost_charge_enable():
    hub, stem = _make_hub()
    stem.usb.setDownstreamBoostMode.return_value = 0
    assert hub.set_boost_charge(True) is True
    stem.usb.setDownstreamBoostMode.assert_called_once_with(stem.usb.BOOST_8_PERCENT)


def test_set_boost_charge_disable():
    hub, stem = _make_hub()
    stem.usb.setDownstreamBoostMode.return_value = 0
    assert hub.set_boost_charge(False) is True
    stem.usb.setDownstreamBoostMode.assert_called_once_with(stem.usb.BOOST_0_PERCENT)


def test_set_boost_charge_sdk_error():
    hub, stem = _make_hub()
    stem.usb.setDownstreamBoostMode.return_value = 1
    assert hub.set_boost_charge(True) is False


# ------------------------------------------------------------------
# Upstream host port switching
# ------------------------------------------------------------------

def test_switch_usb_port_exclusive_port0():
    hub, stem = _make_hub()
    stem.usb.setUpstreamMode.return_value = 0
    assert hub.switch_usb_port(0, exclusive=True) is True
    stem.usb.setUpstreamMode.assert_called_once_with(stem.usb.UPSTREAM_MODE_PORT_0)


def test_switch_usb_port_exclusive_port1():
    hub, stem = _make_hub()
    stem.usb.setUpstreamMode.return_value = 0
    assert hub.switch_usb_port(1, exclusive=True) is True
    stem.usb.setUpstreamMode.assert_called_once_with(stem.usb.UPSTREAM_MODE_PORT_1)


def test_switch_usb_port_non_exclusive():
    hub, stem = _make_hub()
    stem.usb.setUpstreamMode.return_value = 0
    assert hub.switch_usb_port(0, exclusive=False) is True
    stem.usb.setUpstreamMode.assert_called_once_with(stem.usb.UPSTREAM_MODE_AUTO)


def test_switch_usb_port_default_exclusive():
    hub, stem = _make_hub()
    stem.usb.setUpstreamMode.return_value = 0
    assert hub.switch_usb_port(0) is True
    stem.usb.setUpstreamMode.assert_called_once_with(stem.usb.UPSTREAM_MODE_PORT_0)


def test_switch_usb_port_invalid_port():
    hub, stem = _make_hub()
    assert hub.switch_usb_port(2) is False
    stem.usb.setUpstreamMode.assert_not_called()


def test_switch_usb_port_sdk_error():
    hub, stem = _make_hub()
    stem.usb.setUpstreamMode.return_value = 1
    assert hub.switch_usb_port(0) is False


def test_get_upstream_port_ok():
    hub, stem = _make_hub()
    stem.usb.getUpstreamState.return_value = _make_ok_result(1)
    assert hub.get_upstream_port() == 1


def test_get_upstream_port_error():
    hub, stem = _make_hub()
    stem.usb.getUpstreamState.return_value = _make_err_result()
    assert hub.get_upstream_port() is None


# ------------------------------------------------------------------
# Hub info
# ------------------------------------------------------------------

def test_hub_serial_ok():
    hub, stem = _make_hub()
    stem.system.getSerialNumber.return_value = _make_ok_result(0x12345678)
    assert hub.hub_serial() == 0x12345678


def test_hub_serial_error():
    hub, stem = _make_hub()
    stem.system.getSerialNumber.return_value = _make_err_result()
    assert hub.hub_serial() is None


def test_hub_firmware_version_ok():
    hub, stem = _make_hub()
    stem.system.getVersion.return_value = _make_ok_result("3.0.0")
    assert hub.hub_firmware_version() == "3.0.0"


def test_hub_firmware_version_error():
    hub, stem = _make_hub()
    stem.system.getVersion.return_value = _make_err_result()
    assert hub.hub_firmware_version() is None

import sys
import types
from unittest.mock import MagicMock, patch, call
import pytest

# ---------------------------------------------------------------------------
# Stub out the brainstem package before importing AcronameHub so tests work
# without the real SDK installed.
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


def _make_hub(connect_err=0):
    """Create a test hub with mocked brainstem stem object."""
    mock_stem = MagicMock()
    mock_stem.discoverAndConnect.return_value = connect_err
    _bs.stem.USBHub3p = MagicMock(return_value=mock_stem)
    hub = AcronameHub()
    return hub, mock_stem


def test_connect_success():
    hub, stem = _make_hub(connect_err=0)
    result = hub.connect()
    assert result is True
    stem.discoverAndConnect.assert_called_once_with(_bs.link.Spec.USB)


def test_connect_with_serial():
    hub, stem = _make_hub()
    stem.connectFromSerial.return_value = 0
    result = hub.connect(serial=0xABCD1234)
    assert result is True
    stem.connectFromSerial.assert_called_once_with(0xABCD1234)


def test_connect_failure():
    hub, stem = _make_hub(connect_err=1)
    result = hub.connect()
    assert result is False


def test_disconnect_calls_sdk():
    hub, stem = _make_hub()
    hub.connect()
    hub.disconnect()
    stem.disconnect.assert_called_once()


def test_disconnect_before_connect_does_not_raise():
    hub, stem = _make_hub()
    hub.disconnect()  # no exception


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


def test_set_port_power_enable():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setPowerEnable.return_value = 0
    assert hub.set_port_power(0, True) is True
    stem.usb.setPowerEnable.assert_called_once_with(0, True)


def test_set_port_power_disable():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setPowerEnable.return_value = 0
    assert hub.set_port_power(3, False) is True
    stem.usb.setPowerEnable.assert_called_once_with(3, False)


def test_set_port_power_sdk_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setPowerEnable.return_value = 1
    assert hub.set_port_power(0, True) is False


def test_set_port_power_invalid_port():
    hub, stem = _make_hub()
    hub.connect()
    assert hub.set_port_power(8, True) is False
    stem.usb.setPowerEnable.assert_not_called()


def test_get_port_power_true():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getPowerEnable.return_value = _make_ok_result(True)
    assert hub.get_port_power(0) is True


def test_get_port_power_false():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getPowerEnable.return_value = _make_ok_result(False)
    assert hub.get_port_power(0) is False


def test_get_port_power_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getPowerEnable.return_value = _make_err_result()
    assert hub.get_port_power(0) is None


def test_get_port_power_invalid_port():
    hub, stem = _make_hub()
    hub.connect()
    assert hub.get_port_power(8) is None
    stem.usb.getPowerEnable.assert_not_called()


def test_set_port_data_enable():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setDataEnable.return_value = 0
    assert hub.set_port_data(2, True) is True
    stem.usb.setDataEnable.assert_called_once_with(2, True)


def test_set_port_data_disable():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setDataEnable.return_value = 0
    assert hub.set_port_data(2, False) is True
    stem.usb.setDataEnable.assert_called_once_with(2, False)


def test_set_port_data_sdk_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setDataEnable.return_value = 1
    assert hub.set_port_data(2, True) is False


def test_set_port_data_invalid_port():
    hub, stem = _make_hub()
    hub.connect()
    assert hub.set_port_data(-1, True) is False
    stem.usb.setDataEnable.assert_not_called()


def test_get_port_data_true():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getDataEnable.return_value = _make_ok_result(True)
    assert hub.get_port_data(1) is True


def test_get_port_data_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getDataEnable.return_value = _make_err_result()
    assert hub.get_port_data(1) is None


def test_set_port_speed_ss():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setPortMode.return_value = 0
    assert hub.set_port_speed(0, "ss") is True
    stem.usb.setPortMode.assert_called_once_with(0, 1)


def test_set_port_speed_auto():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setPortMode.return_value = 0
    assert hub.set_port_speed(0, "auto") is True
    stem.usb.setPortMode.assert_called_once_with(0, 0)


def test_set_port_speed_unknown_string():
    hub, stem = _make_hub()
    hub.connect()
    assert hub.set_port_speed(0, "turbo") is False
    stem.usb.setPortMode.assert_not_called()


def test_set_port_speed_invalid_port():
    hub, stem = _make_hub()
    hub.connect()
    assert hub.set_port_speed(8, "ss") is False
    stem.usb.setPortMode.assert_not_called()


def test_set_port_speed_sdk_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setPortMode.return_value = 1
    assert hub.set_port_speed(0, "hs") is False


def test_get_port_current_ok():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getCurrentMicroAmps.return_value = _make_ok_result(450000)
    assert hub.get_port_current(0) == pytest.approx(450.0)


def test_get_port_current_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getCurrentMicroAmps.return_value = _make_err_result()
    assert hub.get_port_current(0) is None


def test_get_port_current_invalid_port():
    hub, stem = _make_hub()
    hub.connect()
    assert hub.get_port_current(8) is None
    stem.usb.getCurrentMicroAmps.assert_not_called()


def test_get_port_voltage_ok():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getVoltageMillivolts.return_value = _make_ok_result(5000)
    assert hub.get_port_voltage(0) == pytest.approx(5000.0)


def test_get_port_voltage_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.getVoltageMillivolts.return_value = _make_err_result()
    assert hub.get_port_voltage(0) is None


def test_set_port_boost_charge_enable():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setBoostEnable.return_value = 0
    assert hub.set_port_boost_charge(0, True) is True
    stem.usb.setBoostEnable.assert_called_once_with(0, True)


def test_set_port_boost_charge_sdk_error():
    hub, stem = _make_hub()
    hub.connect()
    stem.usb.setBoostEnable.return_value = 1
    assert hub.set_port_boost_charge(0, True) is False


def test_set_port_boost_charge_invalid_port():
    hub, stem = _make_hub()
    hub.connect()
    assert hub.set_port_boost_charge(8, True) is False
    stem.usb.setBoostEnable.assert_not_called()

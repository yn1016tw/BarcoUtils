import sys
import types
from unittest.mock import MagicMock, patch, call

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

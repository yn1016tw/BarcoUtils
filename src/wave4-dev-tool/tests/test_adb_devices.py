from unittest.mock import MagicMock, patch

from backend.adb_devices import Device, connect_ip, list_devices, parse_devices_output

SAMPLE_OUTPUT = (
    "List of devices attached\n"
    "1882000501             device usb:1-1 product:duvel model:Hub_Pro device:duvel transport_id:1\n"
    "192.168.1.100:5555     device product:duvel model:Hub_Pro device:duvel transport_id:2\n"
    "emulator-5554          offline transport_id:3\n"
    "\n"
)


def test_parse_devices_output_skips_offline_and_header():
    devices = parse_devices_output(SAMPLE_OUTPUT)
    assert devices == [
        Device(serial="1882000501", model="Hub_Pro", transport_id="1"),
        Device(serial="192.168.1.100:5555", model="Hub_Pro", transport_id="2"),
    ]


def test_parse_devices_output_empty():
    assert parse_devices_output("List of devices attached\n") == []


def test_parse_devices_output_missing_model_defaults_to_unknown():
    output = "List of devices attached\n1234  device transport_id:5\n"
    devices = parse_devices_output(output)
    assert devices == [Device(serial="1234", model="unknown", transport_id="5")]


@patch("backend.adb_devices.subprocess.run")
def test_list_devices_calls_adb_devices_l(mock_run):
    mock_run.return_value = MagicMock(stdout=SAMPLE_OUTPUT, stderr="")
    devices = list_devices(adb_path="adb")
    mock_run.assert_called_once_with(
        ["adb", "devices", "-l"], capture_output=True, text=True, timeout=5.0,
    )
    assert len(devices) == 2


@patch("backend.adb_devices.subprocess.run")
def test_connect_ip_success(mock_run):
    mock_run.return_value = MagicMock(stdout="connected to 192.168.1.100:5555\n", stderr="")
    success, message = connect_ip("192.168.1.100:5555")
    assert success is True
    assert "connected to" in message


@patch("backend.adb_devices.subprocess.run")
def test_connect_ip_failure(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="unable to connect to 1.2.3.4:5555\n")
    success, message = connect_ip("1.2.3.4:5555")
    assert success is False
    assert "unable to connect" in message

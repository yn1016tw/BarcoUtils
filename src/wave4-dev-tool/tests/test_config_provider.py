from unittest.mock import MagicMock, patch

from backend.config_provider import AUTHORITY, list_clickshare, parse_content_query_output

SAMPLE_QUERY_OUTPUT = (
    "Row: 0 key=clickshare.button.timeout, value=30\n"
    "Row: 1 key=clickshare.hdmi.autoswitch, value=true\n"
)


def test_parse_content_query_output_multiple_rows():
    assert parse_content_query_output(SAMPLE_QUERY_OUTPUT) == [
        ("clickshare.button.timeout", "30"),
        ("clickshare.hdmi.autoswitch", "true"),
    ]


def test_parse_content_query_output_empty():
    assert parse_content_query_output("") == []
    assert parse_content_query_output("no rows found\n") == []


def test_parse_content_query_output_value_contains_comma():
    output = "Row: 0 key=clickshare.network.dns, value=8.8.8.8, 8.8.4.4\n"
    assert parse_content_query_output(output) == [
        ("clickshare.network.dns", "8.8.8.8, 8.8.4.4"),
    ]


@patch("backend.config_provider.subprocess.run")
def test_list_clickshare_builds_expected_command(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=SAMPLE_QUERY_OUTPUT, stderr="")
    entries = list_clickshare(serial="1882000501")
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[:4] == ["adb", "-s", "1882000501", "shell"]
    assert "content" in called_cmd
    assert f"content://{AUTHORITY}/clickshare/" in " ".join(called_cmd)
    assert len(entries) == 2
    assert entries[0].domain == "clickshare"
    assert entries[0].key == "clickshare.button.timeout"
    assert entries[0].value == "30"
    assert entries[0].editable is True


@patch("backend.config_provider.subprocess.run")
def test_list_clickshare_no_serial_omits_dash_s(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    list_clickshare(serial=None)
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "adb"
    assert "-s" not in called_cmd


@patch("backend.config_provider.subprocess.run")
def test_list_clickshare_returns_empty_on_adb_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: no devices/emulators found")
    entries = list_clickshare(serial="missing-serial")
    assert entries == []

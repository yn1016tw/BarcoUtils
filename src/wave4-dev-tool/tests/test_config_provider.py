from unittest.mock import MagicMock, patch

from backend.config_provider import (
    AUTHORITY,
    delete_clickshare,
    export_clickshare_config,
    insert_clickshare,
    list_clickshare,
    parse_content_query_output,
    update_clickshare,
)

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


@patch("backend.config_provider.subprocess.run")
def test_update_clickshare_existing_key(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="1 row updated\n", stderr="")
    ok, msg = update_clickshare("1882000501", "clickshare.button.timeout", "45")
    called_cmd = mock_run.call_args[0][0]
    assert "update" in called_cmd
    assert "--bind" in called_cmd
    assert "value:s:45" in called_cmd
    assert ok is True


@patch("backend.config_provider.subprocess.run")
def test_update_clickshare_falls_back_to_insert_when_key_missing(mock_run):
    # First call: update reports 0 rows updated (key doesn't exist yet).
    # Second call: insert succeeds.
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="0 rows updated\n", stderr=""),
        MagicMock(returncode=0, stdout="", stderr=""),
    ]
    ok, msg = update_clickshare("1882000501", "clickshare.new.key", "value")
    assert mock_run.call_count == 2
    second_cmd = mock_run.call_args_list[1][0][0]
    assert "insert" in second_cmd
    assert ok is True


@patch("backend.config_provider.subprocess.run")
def test_insert_clickshare_builds_expected_command(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    ok, msg = insert_clickshare("1882000501", "clickshare.new.key", "42")
    called_cmd = mock_run.call_args[0][0]
    assert "insert" in called_cmd
    assert "value:s:42" in called_cmd
    assert ok is True


@patch("backend.config_provider.subprocess.run")
def test_delete_clickshare_builds_expected_command(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="1 row deleted\n", stderr="")
    ok, msg = delete_clickshare("1882000501", "clickshare.button.timeout")
    called_cmd = mock_run.call_args[0][0]
    assert "delete" in called_cmd
    assert ok is True


@patch("backend.config_provider.subprocess.run")
def test_export_clickshare_config_extracts_json(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='Result: Bundle[{success=true, json={"a":1,"b":2}}]\n',
        stderr="",
    )
    ok, payload = export_clickshare_config("1882000501")
    assert ok is True
    assert payload == '{"a":1,"b":2}'


@patch("backend.config_provider.subprocess.run")
def test_export_clickshare_config_returns_raw_output_on_parse_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="unexpected format\n", stderr="")
    ok, payload = export_clickshare_config("1882000501")
    assert ok is False
    assert payload == "unexpected format\n"

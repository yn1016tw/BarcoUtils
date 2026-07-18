from unittest.mock import MagicMock, patch

from backend.config_provider import (
    AUTHORITY,
    _shell_quote,
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
def test_list_clickshare_no_prefix_uses_export_config(mock_run):
    # The real device's ContentProvider rejects a "clickshare/" URI with no
    # key segment (confirmed empirically), so listing everything must go
    # through export_config's Bundle/JSON payload instead of a direct query.
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=(
            'Result: Bundle[{success=true, json={"schemaVersion":1,"config":'
            '{"BaseUnit.Audio.Enabled":"true","BaseUnit.Standby.StandbyTime":"10"}}}]\n'
        ),
        stderr="",
    )
    ok, entries = list_clickshare(serial="1882000501")
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[:4] == ["adb", "-s", "1882000501", "shell"]
    assert "call" in called_cmd
    assert "export_config" in called_cmd
    assert ok is True
    assert len(entries) == 2
    by_key = {e.key: e for e in entries}
    assert by_key["BaseUnit.Audio.Enabled"].value == "true"
    assert by_key["BaseUnit.Audio.Enabled"].domain == "clickshare"
    assert by_key["BaseUnit.Audio.Enabled"].editable is True
    assert by_key["BaseUnit.Standby.StandbyTime"].value == "10"


@patch("backend.config_provider.subprocess.run")
def test_list_clickshare_no_serial_omits_dash_s(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0, stdout='Result: Bundle[{success=true, json={"config":{}}}]\n', stderr="",
    )
    list_clickshare(serial=None)
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "adb"
    assert "-s" not in called_cmd


@patch("backend.config_provider.subprocess.run")
def test_list_clickshare_returns_empty_on_adb_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: no devices/emulators found")
    ok, entries = list_clickshare(serial="missing-serial")
    assert ok is False
    assert entries == []


@patch("backend.config_provider.subprocess.run")
def test_list_clickshare_returns_empty_when_export_json_is_malformed(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="unexpected format with no json field\n", stderr="")
    ok, entries = list_clickshare(serial="1882000501")
    assert ok is False
    assert entries == []


@patch("backend.config_provider.subprocess.run")
def test_list_clickshare_prefix_is_shell_quoted(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    list_clickshare(serial="1882000501", prefix="clickshare.button timeout")
    called_cmd = mock_run.call_args[0][0]
    called_str = " ".join(called_cmd)
    assert _shell_quote("clickshare.button timeout") in called_str


@patch("backend.config_provider.subprocess.run")
def test_update_clickshare_existing_key(mock_run):
    # First call: list_clickshare query finds the key already exists.
    # Second call: update succeeds.
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="Row: 0 key=clickshare.button.timeout, value=30\n", stderr=""),
        MagicMock(returncode=0, stdout="", stderr=""),
    ]
    ok, msg = update_clickshare("1882000501", "clickshare.button.timeout", "45")
    assert mock_run.call_count == 2
    update_cmd = mock_run.call_args_list[1][0][0]
    assert "update" in update_cmd
    assert "--bind" in update_cmd
    assert _shell_quote("value:s:45") in update_cmd
    assert ok is True


@patch("backend.config_provider.subprocess.run")
def test_update_clickshare_falls_back_to_insert_when_key_missing(mock_run):
    # First call: list_clickshare query finds no matching key.
    # Second call: insert succeeds.
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),
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
    assert _shell_quote("value:s:42") in called_cmd
    assert ok is True


@patch("backend.config_provider.subprocess.run")
def test_insert_clickshare_value_with_space_is_single_quoted_token(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    insert_clickshare("1882000501", "clickshare.room.name", "My Room")
    called_cmd = mock_run.call_args[0][0]
    # The value (with its embedded space) must arrive as a single quoted argv token,
    # not as two separate unquoted tokens.
    assert "'value:s:My Room'" in called_cmd
    assert "My" not in called_cmd
    assert "Room'" not in called_cmd


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


from backend.config_provider import SYSTEM_KEYS, get_system_value, list_system, update_system


def test_system_keys_table_has_expected_entries():
    assert SYSTEM_KEYS["Settings.ScreenOffTimeout"] is True
    assert SYSTEM_KEYS["Settings.SetupWizardHasRun"] is True
    assert SYSTEM_KEYS["Properties.SystemBuildVersion"] is False
    assert SYSTEM_KEYS["Properties.ModelName"] is False
    assert len(SYSTEM_KEYS) == 20


@patch("backend.config_provider.subprocess.run")
def test_get_system_value_parses_single_row(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0, stdout="Row: 0 key=Settings.ScreenOffTimeout, value=600000\n", stderr="",
    )
    value = get_system_value("1882000501", "Settings.ScreenOffTimeout")
    assert value == "600000"


@patch("backend.config_provider.subprocess.run")
def test_get_system_value_returns_none_on_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    value = get_system_value("1882000501", "Settings.ScreenOffTimeout")
    assert value is None


@patch("backend.config_provider.subprocess.run")
def test_list_system_queries_every_key_and_marks_editable(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Row: 0 key=x, value=some-value\n", stderr="")
    ok, entries = list_system("1882000501")
    assert ok is True
    assert mock_run.call_count == len(SYSTEM_KEYS)
    assert len(entries) == len(SYSTEM_KEYS)
    by_key = {e.key: e for e in entries}
    assert by_key["Settings.ScreenOffTimeout"].editable is True
    assert by_key["Properties.ModelName"].editable is False
    assert all(e.domain == "system" for e in entries)


@patch("backend.config_provider.subprocess.run")
def test_list_system_short_circuits_when_first_key_query_fails(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: no devices/emulators found")
    ok, entries = list_system("missing-serial")
    assert ok is False
    assert entries == []
    assert mock_run.call_count == 1


@patch("backend.config_provider.subprocess.run")
def test_update_system_rejects_readonly_property(mock_run):
    ok, msg = update_system("1882000501", "Properties.ModelName", "new-value")
    mock_run.assert_not_called()
    assert ok is False
    assert "read-only" in msg


@patch("backend.config_provider.subprocess.run")
def test_update_system_writes_editable_setting(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    ok, msg = update_system("1882000501", "Settings.ScreenOffTimeout", "300000")
    called_cmd = mock_run.call_args[0][0]
    assert "update" in called_cmd
    assert _shell_quote("value:s:300000") in called_cmd
    assert ok is True


from backend.config_provider import get_mdep_value, update_mdep


@patch("backend.config_provider.subprocess.run")
def test_get_mdep_value_found(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0, stdout="Row: 0 key=mdep.narrator.enabled, value=Enabled\n", stderr="",
    )
    entry = get_mdep_value("1882000501", "mdep.narrator.enabled")
    assert entry is not None
    assert entry.domain == "mdep"
    assert entry.key == "mdep.narrator.enabled"
    assert entry.value == "Enabled"
    assert entry.editable is True


@patch("backend.config_provider.subprocess.run")
def test_get_mdep_value_not_found(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    entry = get_mdep_value("1882000501", "mdep.unknown.key")
    assert entry is None


@patch("backend.config_provider.subprocess.run")
def test_get_mdep_value_adb_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    entry = get_mdep_value("1882000501", "mdep.narrator.enabled")
    assert entry is None


@patch("backend.config_provider.subprocess.run")
def test_update_mdep_builds_expected_command(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    ok, msg = update_mdep("1882000501", "mdep.narrator.enabled", "Disabled")
    called_cmd = mock_run.call_args[0][0]
    assert "update" in called_cmd
    assert _shell_quote("value:s:Disabled") in called_cmd
    assert ok is True

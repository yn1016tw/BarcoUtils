# Wave4 Dev Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Windows GUI tool (`src/wave4-dev-tool/`) that lets a
tester browse and edit `configuration-manager-apk` settings on a Barco Duvel
over ADB, across multiple connected devices.

**Architecture:** Python backend (pure-function ADB wrappers, unit-tested with
mocked `subprocess.run`) + pywebview window rendering an HTML/CSS/JS UI, talking
to the backend via `pywebview.api.*` calls. Packaged with PyInstaller
`--onefile` into a single `.exe`.

**Tech Stack:** Python 3.10+, `pywebview`, `pyinstaller`, `pytest` (backend
tests only — no test harness exists for the GUI layer itself, verified manually).

## Global Constraints

- Design source of truth: `docs/superpowers/specs/2026-07-18-wave4-dev-tool-design.md` — re-read it if a task's intent is unclear.
- ContentProvider authority: `com.barco.clickshare.configurationmanager.provider` (three subtrees: `clickshare/*`, `system/*`, `mdep/*`).
- All ADB calls go through `adb shell content ...`; no root required.
- No confirmation dialogs on Save/Delete; no auto-backup of previous values (explicit prior product decision).
- `Properties.*` keys in the `system` domain are always read-only (the APK itself rejects writes); never render an edit control for them.
- No code obfuscation/protection needed — this is an internal tool.
- Commit message format per `CLAUDE.md`: imperative lowercase summary (e.g. `add clickshare content-provider wrapper`), no body unless something non-obvious needs explanation, no AI co-author lines. Do not bump `testcases/common/version.py` — that versioning scheme is for `testcases/`, not `src/` tools.
- All new source lives under `src/wave4-dev-tool/`, following the existing `src/timesheet/`, `src/hid-test/` convention in this repo.

---

## File Structure

```
src/wave4-dev-tool/
├── app.py                    — pywebview entry point + Api class (JS↔Python bridge)
├── requirements.txt          — pywebview, pyinstaller, pytest
├── build.bat                 — PyInstaller --onefile packaging script
├── backend/
│   ├── __init__.py
│   ├── models.py             — ConfigEntry dataclass
│   ├── adb_devices.py        — `adb devices -l` parsing, device list/connect
│   └── config_provider.py    — content query/insert/update/delete/call wrappers for all 3 domains
├── ui/
│   ├── index.html            — device selector, tabs, search bar, panels
│   ├── style.css
│   └── app.js                — rendering, tree building, edit/save/cancel, export
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_adb_devices.py
    └── test_config_provider.py
```

---

### Task 1: Project scaffolding + ConfigEntry model

**Files:**
- Create: `src/wave4-dev-tool/backend/__init__.py` (empty)
- Create: `src/wave4-dev-tool/backend/models.py`
- Create: `src/wave4-dev-tool/tests/__init__.py` (empty)
- Create: `src/wave4-dev-tool/tests/test_models.py`
- Create: `src/wave4-dev-tool/requirements.txt`

**Interfaces:**
- Produces: `ConfigEntry` dataclass with fields `domain: str`, `key: str`, `value: str`, `editable: bool` — every later backend function returns `list[ConfigEntry]` or `ConfigEntry | None` built from this type.

- [ ] **Step 1: Create the package directories and empty `__init__.py` files**

Run from repo root (`C:\Project\BarcoUtils`):
```bash
mkdir -p src/wave4-dev-tool/backend src/wave4-dev-tool/tests src/wave4-dev-tool/ui
touch src/wave4-dev-tool/backend/__init__.py src/wave4-dev-tool/tests/__init__.py
```

- [ ] **Step 2: Write the failing test**

`src/wave4-dev-tool/tests/test_models.py`:
```python
from backend.models import ConfigEntry


def test_config_entry_holds_fields():
    entry = ConfigEntry(
        domain="clickshare",
        key="clickshare.button.timeout",
        value="30",
        editable=True,
    )
    assert entry.domain == "clickshare"
    assert entry.key == "clickshare.button.timeout"
    assert entry.value == "30"
    assert entry.editable is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest src/wave4-dev-tool/tests/test_models.py -v` (from repo root)
Expected: FAIL with `ModuleNotFoundError: No module named 'backend'`

- [ ] **Step 4: Write minimal implementation**

`src/wave4-dev-tool/backend/models.py`:
```python
from dataclasses import dataclass


@dataclass
class ConfigEntry:
    domain: str
    key: str
    value: str
    editable: bool
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/wave4-dev-tool/tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Write requirements.txt**

`src/wave4-dev-tool/requirements.txt`:
```
pywebview
pyinstaller
pytest
```

- [ ] **Step 7: Commit**

```bash
git add src/wave4-dev-tool/backend/__init__.py src/wave4-dev-tool/backend/models.py src/wave4-dev-tool/tests/__init__.py src/wave4-dev-tool/tests/test_models.py src/wave4-dev-tool/requirements.txt
git commit -m "scaffold wave4-dev-tool with ConfigEntry model"
```

---

### Task 2: ADB device listing and connect

**Files:**
- Create: `src/wave4-dev-tool/backend/adb_devices.py`
- Create: `src/wave4-dev-tool/tests/test_adb_devices.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Device` dataclass (`serial: str`, `model: str`, `transport_id: str`); `parse_devices_output(output: str) -> list[Device]`; `list_devices(adb_path: str = "adb", timeout: float = 5.0) -> list[Device]`; `connect_ip(ip_port: str, adb_path: str = "adb", timeout: float = 5.0) -> tuple[bool, str]`. Task 8 (app.py) calls `list_devices()` and `connect_ip()` directly.

- [ ] **Step 1: Write the failing tests**

`src/wave4-dev-tool/tests/test_adb_devices.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/wave4-dev-tool/tests/test_adb_devices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.adb_devices'`

- [ ] **Step 3: Write minimal implementation**

`src/wave4-dev-tool/backend/adb_devices.py`:
```python
import subprocess
from dataclasses import dataclass


@dataclass
class Device:
    serial: str
    model: str
    transport_id: str


def parse_devices_output(output: str) -> list[Device]:
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, status = parts[0], parts[1]
        if status != "device":
            continue
        model = "unknown"
        transport_id = "unknown"
        for token in parts[2:]:
            if token.startswith("model:"):
                model = token[len("model:"):]
            elif token.startswith("transport_id:"):
                transport_id = token[len("transport_id:"):]
        devices.append(Device(serial=serial, model=model, transport_id=transport_id))
    return devices


def list_devices(adb_path: str = "adb", timeout: float = 5.0) -> list[Device]:
    result = subprocess.run(
        [adb_path, "devices", "-l"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return parse_devices_output(result.stdout)


def connect_ip(ip_port: str, adb_path: str = "adb", timeout: float = 5.0) -> tuple[bool, str]:
    result = subprocess.run(
        [adb_path, "connect", ip_port],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (result.stdout or "") + (result.stderr or "")
    success = "connected to" in output.lower()
    return success, output.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/wave4-dev-tool/tests/test_adb_devices.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wave4-dev-tool/backend/adb_devices.py src/wave4-dev-tool/tests/test_adb_devices.py
git commit -m "add adb device listing and connect-by-ip"
```

---

### Task 3: content-provider query output parser + ClickShare read

**Files:**
- Create: `src/wave4-dev-tool/backend/config_provider.py`
- Create: `src/wave4-dev-tool/tests/test_config_provider.py`

**Interfaces:**
- Consumes: `backend.models.ConfigEntry` (Task 1).
- Produces: `AUTHORITY: str` constant; `parse_content_query_output(output: str) -> list[tuple[str, str]]`; `list_clickshare(serial: str | None, prefix: str = "", adb_path: str = "adb") -> list[ConfigEntry]`. Later tasks in this file reuse `parse_content_query_output` and the internal `_adb_cmd`/`_run` helpers defined here.

- [ ] **Step 1: Write the failing tests**

`src/wave4-dev-tool/tests/test_config_provider.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.config_provider'`

- [ ] **Step 3: Write minimal implementation**

`src/wave4-dev-tool/backend/config_provider.py`:
```python
import re
import subprocess

from backend.models import ConfigEntry

AUTHORITY = "com.barco.clickshare.configurationmanager.provider"

_ROW_RE = re.compile(r"^Row:\s*\d+\s+(.*)$")
_KV_RE = re.compile(r"key=(.*?), value=(.*)$")


def parse_content_query_output(output: str) -> list[tuple[str, str]]:
    rows = []
    for line in output.splitlines():
        row_match = _ROW_RE.match(line.strip())
        if not row_match:
            continue
        kv_match = _KV_RE.search(row_match.group(1))
        if not kv_match:
            continue
        rows.append((kv_match.group(1), kv_match.group(2)))
    return rows


def _adb_cmd(serial: str | None, shell_args: list[str], adb_path: str = "adb") -> list[str]:
    cmd = [adb_path]
    if serial:
        cmd += ["-s", serial]
    cmd += ["shell"] + shell_args
    return cmd


def _run(cmd: list[str], timeout: float = 5.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "adb command timed out"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def list_clickshare(serial: str | None, prefix: str = "", adb_path: str = "adb") -> list[ConfigEntry]:
    uri = f"content://{AUTHORITY}/clickshare/{prefix}"
    cmd = _adb_cmd(
        serial,
        ["content", "query", "--uri", uri, "--projection", "key:value"],
        adb_path,
    )
    ok, output = _run(cmd)
    if not ok:
        return []
    return [
        ConfigEntry(domain="clickshare", key=key, value=value, editable=True)
        for key, value in parse_content_query_output(output)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wave4-dev-tool/backend/config_provider.py src/wave4-dev-tool/tests/test_config_provider.py
git commit -m "add content-query parser and clickshare list"
```

---

### Task 4: ClickShare write, insert, delete, and export

**Files:**
- Modify: `src/wave4-dev-tool/backend/config_provider.py`
- Modify: `src/wave4-dev-tool/tests/test_config_provider.py`

**Interfaces:**
- Consumes: `_adb_cmd`, `_run`, `AUTHORITY` (Task 3, same file).
- Produces: `update_clickshare(serial, key, value, adb_path="adb") -> tuple[bool, str]`; `insert_clickshare(serial, key, value, adb_path="adb") -> tuple[bool, str]`; `delete_clickshare(serial, key, adb_path="adb") -> tuple[bool, str]`; `export_clickshare_config(serial, adb_path="adb") -> tuple[bool, str]`. Task 8 (`app.py`) calls all four directly.

**Note on `export_clickshare_config`:** this parses the text form of
`adb shell content call --method export_config`'s `Result: Bundle[{...}]`
output to pull out the `json=` field. Android's `Bundle.toString()` format is
consistent across versions but has not been verified against a real Duvel —
Task 12's manual smoke test **must** confirm the actual output and adjust
`_extract_json_field` if it differs. On parse failure the function returns
`(False, raw_output)` so the caller sees the raw text instead of silently
losing data.

- [ ] **Step 1: Write the failing tests**

Append to `src/wave4-dev-tool/tests/test_config_provider.py`:
```python
from backend.config_provider import (
    delete_clickshare,
    export_clickshare_config,
    insert_clickshare,
    update_clickshare,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: FAIL with `ImportError: cannot import name 'update_clickshare'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/wave4-dev-tool/backend/config_provider.py`:
```python
def update_clickshare(serial: str | None, key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/clickshare/{key}"
    cmd = _adb_cmd(serial, ["content", "update", "--uri", uri, "--bind", f"value:s:{value}"], adb_path)
    ok, output = _run(cmd)
    if ok and "0 rows" not in output.lower():
        return True, output
    return insert_clickshare(serial, key, value, adb_path)


def insert_clickshare(serial: str | None, key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/clickshare/{key}"
    cmd = _adb_cmd(serial, ["content", "insert", "--uri", uri, "--bind", f"value:s:{value}"], adb_path)
    return _run(cmd)


def delete_clickshare(serial: str | None, key: str, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/clickshare/{key}"
    cmd = _adb_cmd(serial, ["content", "delete", "--uri", uri], adb_path)
    return _run(cmd)


def _extract_json_field(output: str) -> str | None:
    idx = output.find("json=")
    if idx == -1:
        return None
    remainder = output[idx + len("json="):].strip()
    if remainder.endswith("}]"):
        remainder = remainder[:-2]
    return remainder.strip() or None


def export_clickshare_config(serial: str | None, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/clickshare"
    cmd = _adb_cmd(serial, ["content", "call", "--uri", uri, "--method", "export_config"], adb_path)
    ok, output = _run(cmd)
    if not ok:
        return False, output
    json_payload = _extract_json_field(output)
    if json_payload is None:
        return False, output
    return True, json_payload
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wave4-dev-tool/backend/config_provider.py src/wave4-dev-tool/tests/test_config_provider.py
git commit -m "add clickshare write, insert, delete, export"
```

---

### Task 5: System domain (fixed key table)

**Files:**
- Modify: `src/wave4-dev-tool/backend/config_provider.py`
- Modify: `src/wave4-dev-tool/tests/test_config_provider.py`

**Interfaces:**
- Consumes: `_adb_cmd`, `_run`, `AUTHORITY`, `parse_content_query_output` (Task 3, same file).
- Produces: `SYSTEM_KEYS: dict[str, bool]` (logical key → editable); `get_system_value(serial, logical_key, adb_path="adb") -> str | None`; `list_system(serial, adb_path="adb") -> list[ConfigEntry]`; `update_system(serial, logical_key, value, adb_path="adb") -> tuple[bool, str]`. Task 8 (`app.py`) calls `list_system` and `update_system` directly.

- [ ] **Step 1: Write the failing tests**

Append to `src/wave4-dev-tool/tests/test_config_provider.py`:
```python
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
    entries = list_system("1882000501")
    assert mock_run.call_count == len(SYSTEM_KEYS)
    assert len(entries) == len(SYSTEM_KEYS)
    by_key = {e.key: e for e in entries}
    assert by_key["Settings.ScreenOffTimeout"].editable is True
    assert by_key["Properties.ModelName"].editable is False
    assert all(e.domain == "system" for e in entries)


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
    assert "value:s:300000" in called_cmd
    assert ok is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: FAIL with `ImportError: cannot import name 'SYSTEM_KEYS'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/wave4-dev-tool/backend/config_provider.py`:
```python
SYSTEM_KEYS: dict[str, bool] = {
    "Settings.ScreenOffTimeout": True,
    "Settings.SetupWizardHasRun": True,
    "Properties.SystemBuildDate": False,
    "Properties.SystemBuildVersion": False,
    "Properties.SystemBuildMinimalVersion": False,
    "Properties.ProductName": False,
    "Properties.ModelName": False,
    "Properties.DeviceName": False,
    "Properties.Brand": False,
    "Properties.Manufacturer": False,
    "Properties.SN": False,
    "Properties.BarcoDefaultSN": False,
    "Properties.BarcoPlatformName": False,
    "Properties.BarcoProductName": False,
    "Properties.BarcoArticleNumber": False,
    "Properties.BarcoFirstBoot": False,
    "Properties.BarcoCountryCode": False,
    "Properties.BarcoPlatform": False,
    "Properties.SysWlan0Mac": False,
    "Properties.MdepBuildId": False,
}


def get_system_value(serial: str | None, logical_key: str, adb_path: str = "adb") -> str | None:
    uri = f"content://{AUTHORITY}/system/{logical_key}"
    cmd = _adb_cmd(serial, ["content", "query", "--uri", uri], adb_path)
    ok, output = _run(cmd)
    if not ok:
        return None
    rows = parse_content_query_output(output)
    return rows[0][1] if rows else None


def list_system(serial: str | None, adb_path: str = "adb") -> list[ConfigEntry]:
    entries = []
    for logical_key, editable in SYSTEM_KEYS.items():
        value = get_system_value(serial, logical_key, adb_path) or ""
        entries.append(ConfigEntry(domain="system", key=logical_key, value=value, editable=editable))
    return entries


def update_system(serial: str | None, logical_key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    if not SYSTEM_KEYS.get(logical_key, False):
        return False, f"{logical_key} is read-only"
    uri = f"content://{AUTHORITY}/system/{logical_key}"
    cmd = _adb_cmd(serial, ["content", "update", "--uri", uri, "--bind", f"value:s:{value}"], adb_path)
    return _run(cmd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wave4-dev-tool/backend/config_provider.py src/wave4-dev-tool/tests/test_config_provider.py
git commit -m "add system domain fixed-key table and read/write"
```

---

### Task 6: MDEP domain (single-key lookup)

**Files:**
- Modify: `src/wave4-dev-tool/backend/config_provider.py`
- Modify: `src/wave4-dev-tool/tests/test_config_provider.py`

**Interfaces:**
- Consumes: `_adb_cmd`, `_run`, `AUTHORITY`, `parse_content_query_output` (Task 3, same file); `ConfigEntry` (Task 1).
- Produces: `get_mdep_value(serial, key, adb_path="adb") -> ConfigEntry | None`; `update_mdep(serial, key, value, adb_path="adb") -> tuple[bool, str]`. Task 8 (`app.py`) calls both directly.

- [ ] **Step 1: Write the failing tests**

Append to `src/wave4-dev-tool/tests/test_config_provider.py`:
```python
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
    assert "value:s:Disabled" in called_cmd
    assert ok is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_mdep_value'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/wave4-dev-tool/backend/config_provider.py`:
```python
def get_mdep_value(serial: str | None, key: str, adb_path: str = "adb") -> ConfigEntry | None:
    uri = f"content://{AUTHORITY}/mdep/{key}"
    cmd = _adb_cmd(serial, ["content", "query", "--uri", uri], adb_path)
    ok, output = _run(cmd)
    if not ok:
        return None
    rows = parse_content_query_output(output)
    if not rows:
        return None
    return ConfigEntry(domain="mdep", key=key, value=rows[0][1], editable=True)


def update_mdep(serial: str | None, key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/mdep/{key}"
    cmd = _adb_cmd(serial, ["content", "update", "--uri", uri, "--bind", f"value:s:{value}"], adb_path)
    return _run(cmd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/wave4-dev-tool/tests/test_config_provider.py -v`
Expected: PASS (22 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wave4-dev-tool/backend/config_provider.py src/wave4-dev-tool/tests/test_config_provider.py
git commit -m "add mdep domain single-key lookup and update"
```

---

### Task 7: pywebview Api bridge (app.py)

**Files:**
- Create: `src/wave4-dev-tool/app.py`

**Interfaces:**
- Consumes: `backend.adb_devices.{list_devices, connect_ip}` (Task 2); `backend.config_provider.{list_clickshare, list_system, update_clickshare, update_system, update_mdep, insert_clickshare, delete_clickshare, export_clickshare_config, get_mdep_value}` (Tasks 3–6).
- Produces: `Api` class with JSON-serializable-dict-returning methods called from JS as `pywebview.api.<name>(...)`: `list_devices()`, `connect_ip(ip_port)`, `select_device(serial)`, `list_config(domain)`, `get_mdep(key)`, `update_config(domain, key, value)`, `insert_clickshare(key, value)`, `delete_clickshare(key)`, `export_config()`, `save_json_to_file(json_str)`. Task 9's `app.js` calls every one of these by exact name.

This task has no automated test — pywebview requires a real WebView2 window,
which cannot run headless in this repo's environment. It is verified manually
in Step 3 below, and again end-to-end in Task 12.

- [ ] **Step 1: Write app.py**

`src/wave4-dev-tool/app.py`:
```python
import webview

from backend import adb_devices, config_provider


class Api:
    def __init__(self):
        self.serial: str | None = None
        self.window: webview.Window | None = None

    def list_devices(self):
        return [d.__dict__ for d in adb_devices.list_devices()]

    def connect_ip(self, ip_port: str):
        success, message = adb_devices.connect_ip(ip_port)
        return {"success": success, "message": message}

    def select_device(self, serial: str):
        self.serial = serial or None
        return {"success": True}

    def list_config(self, domain: str):
        if domain == "clickshare":
            entries = config_provider.list_clickshare(self.serial)
        elif domain == "system":
            entries = config_provider.list_system(self.serial)
        else:
            return {"success": False, "error": f"domain '{domain}' has no list API"}
        return {"success": True, "entries": [e.__dict__ for e in entries]}

    def get_mdep(self, key: str):
        entry = config_provider.get_mdep_value(self.serial, key)
        if entry is None:
            return {"success": False, "error": f"key '{key}' not found"}
        return {"success": True, "entry": entry.__dict__}

    def update_config(self, domain: str, key: str, value: str):
        if domain == "clickshare":
            ok, msg = config_provider.update_clickshare(self.serial, key, value)
        elif domain == "system":
            ok, msg = config_provider.update_system(self.serial, key, value)
        elif domain == "mdep":
            ok, msg = config_provider.update_mdep(self.serial, key, value)
        else:
            return {"success": False, "error": f"unknown domain '{domain}'"}
        return {"success": ok, "error": None if ok else msg}

    def insert_clickshare(self, key: str, value: str):
        ok, msg = config_provider.insert_clickshare(self.serial, key, value)
        return {"success": ok, "error": None if ok else msg}

    def delete_clickshare(self, key: str):
        ok, msg = config_provider.delete_clickshare(self.serial, key)
        return {"success": ok, "error": None if ok else msg}

    def export_config(self):
        ok, payload = config_provider.export_clickshare_config(self.serial)
        return {"success": ok, "json": payload if ok else None, "error": None if ok else payload}

    def save_json_to_file(self, json_str: str):
        if self.window is None:
            return {"success": False, "error": "window not ready"}
        file_path = self.window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename="clickshare_config.json",
        )
        if not file_path:
            return {"success": False, "error": "cancelled"}
        path = file_path if isinstance(file_path, str) else file_path[0]
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return {"success": True, "path": path}


def main():
    api = Api()
    window = webview.create_window(
        "Wave4 Dev Tool",
        "ui/index.html",
        js_api=api,
        width=1100,
        height=750,
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Install dependencies**

Run from `src/wave4-dev-tool/`:
```bash
pip install -r requirements.txt
```

- [ ] **Step 3: Manual smoke test (no `ui/index.html` yet, so use devtools console)**

`ui/index.html` doesn't exist yet (Task 9), so `webview.create_window` will
fail to load a page — that's expected at this point. Verify only that the
module imports and the `Api` class instantiates without error:

Run: `python -c "from app import Api; a = Api(); print(a.list_devices())"` (from `src/wave4-dev-tool/`)
Expected: prints a Python list (empty `[]` if no device attached, or a list of dicts if one is) — no traceback.

- [ ] **Step 4: Commit**

```bash
git add src/wave4-dev-tool/app.py
git commit -m "add pywebview Api bridge"
```

---

### Task 8: UI skeleton (HTML/CSS) + device selector

**Files:**
- Create: `src/wave4-dev-tool/ui/index.html`
- Create: `src/wave4-dev-tool/ui/style.css`
- Create: `src/wave4-dev-tool/ui/app.js` (device selector + init only; rendering added in Tasks 10–11)

**Interfaces:**
- Consumes: `pywebview.api.list_devices()`, `pywebview.api.connect_ip(ip_port)`, `pywebview.api.select_device(serial)` (Task 7).
- Produces: DOM element IDs that Tasks 10–11 attach behavior to: `#device-select`, `#rescan-btn`, `#connect-ip-input`, `#connect-ip-btn`, `.tab-btn[data-domain]`, `#search-input`, `#export-btn`, `#clickshare-panel`/`#system-panel`/`#mdep-panel` (each `.panel`), `#clickshare-tree`, `#add-key-btn`, `#system-table`, `#mdep-key-input`, `#mdep-query-btn`, `#mdep-table`, `#status-banner`. Global JS state object `state = { serial, domain, entries }` that Tasks 10–11 read and mutate.

- [ ] **Step 1: Write index.html**

`src/wave4-dev-tool/ui/index.html`:
```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <title>Wave4 Dev Tool</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div id="toolbar">
    <label>裝置:
      <select id="device-select"></select>
    </label>
    <button id="rescan-btn">重新掃描</button>
    <input id="connect-ip-input" placeholder="IP:port" />
    <button id="connect-ip-btn">Connect</button>
  </div>

  <div id="tabs">
    <button class="tab-btn active" data-domain="clickshare">ClickShare</button>
    <button class="tab-btn" data-domain="system">System</button>
    <button class="tab-btn" data-domain="mdep">MDEP</button>
    <button id="export-btn">匯出 JSON</button>
  </div>

  <div id="search-bar">
    <input id="search-input" placeholder="搜尋 key..." />
  </div>

  <div id="content-area">
    <div id="clickshare-panel" class="panel active">
      <div id="clickshare-tree"></div>
      <button id="add-key-btn">+ 新增 key</button>
    </div>
    <div id="system-panel" class="panel">
      <table id="system-table"><tbody></tbody></table>
    </div>
    <div id="mdep-panel" class="panel">
      <div id="mdep-query">
        <input id="mdep-key-input" placeholder="輸入 MDEP key..." />
        <button id="mdep-query-btn">查詢</button>
      </div>
      <table id="mdep-table"><tbody></tbody></table>
    </div>
  </div>

  <div id="status-banner" class="hidden"></div>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write style.css**

`src/wave4-dev-tool/ui/style.css`:
```css
body {
  font-family: "Segoe UI", sans-serif;
  margin: 0;
  padding: 0;
}

#toolbar, #tabs, #search-bar {
  padding: 8px 12px;
  border-bottom: 1px solid #ccc;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-btn {
  padding: 6px 14px;
  cursor: pointer;
}

.tab-btn.active {
  font-weight: bold;
  border-bottom: 2px solid #0078d4;
}

#export-btn {
  margin-left: auto;
}

.panel {
  display: none;
  padding: 12px;
}

.panel.active {
  display: block;
}

table {
  width: 100%;
  border-collapse: collapse;
}

table td, table th {
  padding: 4px 8px;
  border-bottom: 1px solid #eee;
  text-align: left;
}

ul {
  list-style: none;
  padding-left: 16px;
}

.leaf-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}

.leaf-key {
  min-width: 160px;
}

.leaf-value {
  flex: 1;
}

.tree-group {
  font-weight: bold;
  display: block;
  padding: 2px 0;
}

.row-error {
  color: #c00;
  font-size: 0.85em;
}

#status-banner {
  background: #fdecea;
  color: #611a15;
  padding: 8px 12px;
}

#status-banner.hidden {
  display: none;
}
```

- [ ] **Step 3: Write app.js (device selector + init skeleton only)**

`src/wave4-dev-tool/ui/app.js`:
```js
const state = {
  serial: null,
  domain: "clickshare",
  entries: [],
};

window.addEventListener("pywebviewready", init);

async function init() {
  await refreshDevices();
  document.getElementById("rescan-btn").addEventListener("click", refreshDevices);
  document.getElementById("connect-ip-btn").addEventListener("click", onConnectIp);
  document.getElementById("device-select").addEventListener("change", onDeviceChange);
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.domain));
  });
}

async function refreshDevices() {
  const devices = await pywebview.api.list_devices();
  const select = document.getElementById("device-select");
  select.innerHTML = "";
  devices.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.serial;
    opt.textContent = `${d.serial} (${d.model})`;
    select.appendChild(opt);
  });
  if (devices.length > 0) {
    state.serial = devices[0].serial;
    await pywebview.api.select_device(state.serial);
  }
}

async function onConnectIp() {
  const ip = document.getElementById("connect-ip-input").value.trim();
  if (!ip) return;
  const result = await pywebview.api.connect_ip(ip);
  if (result.success) {
    await refreshDevices();
  } else {
    showStatus(`連線失敗: ${result.message}`);
  }
}

async function onDeviceChange(e) {
  state.serial = e.target.value;
  await pywebview.api.select_device(state.serial);
}

function switchTab(domain) {
  state.domain = domain;
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.domain === domain));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  document.getElementById(`${domain}-panel`).classList.add("active");
  document.getElementById("export-btn").style.display = domain === "clickshare" ? "" : "none";
}

function showStatus(msg) {
  const el = document.getElementById("status-banner");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideStatus() {
  document.getElementById("status-banner").classList.add("hidden");
}
```

- [ ] **Step 4: Manual smoke test**

Run from `src/wave4-dev-tool/`: `python app.py`
Expected: a window titled "Wave4 Dev Tool" opens, shows the toolbar/tabs/search bar layout, device dropdown populates if a device is attached (or stays empty if not — no error dialog either way), and clicking each of the 3 tab buttons switches the visible panel and toggles the `active` CSS class.

- [ ] **Step 5: Commit**

```bash
git add src/wave4-dev-tool/ui/index.html src/wave4-dev-tool/ui/style.css src/wave4-dev-tool/ui/app.js
git commit -m "add UI skeleton with device selector and tab switching"
```

---

### Task 9: ClickShare tree rendering + search filter

**Files:**
- Modify: `src/wave4-dev-tool/ui/app.js`

**Interfaces:**
- Consumes: `pywebview.api.list_config("clickshare")` (Task 7); `state` object, `switchTab`, `showStatus`, `hideStatus` (Task 8, same file).
- Produces: `loadDomain(domain)`, `render()`, `buildTree(entries)`, `renderTree(entries)`, `renderNode(node, path)` — Task 10 adds edit/delete controls that call into `renderTree`'s row output, Task 11's System/MDEP rendering follows the same `render()` dispatch pattern.

- [ ] **Step 1: Add domain loading and tree rendering to app.js**

Modify `switchTab` in `src/wave4-dev-tool/ui/app.js` to call `loadDomain` for
list-capable domains, and append the tree-building functions:
```js
function switchTab(domain) {
  state.domain = domain;
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.domain === domain));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  document.getElementById(`${domain}-panel`).classList.add("active");
  document.getElementById("export-btn").style.display = domain === "clickshare" ? "" : "none";
  if (domain !== "mdep") {
    loadDomain(domain);
  }
}

async function loadDomain(domain) {
  hideStatus();
  const result = await pywebview.api.list_config(domain);
  if (!result.success) {
    showStatus(result.error || "無法連接裝置");
    state.entries = [];
  } else {
    state.entries = result.entries;
  }
  render();
}

function render() {
  if (state.domain === "clickshare") {
    renderTree(state.entries);
  }
}

function buildTree(entries) {
  const root = { children: {} };
  entries.forEach((entry) => {
    const parts = entry.key.split(".");
    let node = root;
    parts.forEach((part, i) => {
      if (!node.children) node.children = {};
      if (!node.children[part]) node.children[part] = {};
      node = node.children[part];
      if (i === parts.length - 1) {
        node.entry = entry;
      }
    });
  });
  return root;
}

function renderTree(entries) {
  const container = document.getElementById("clickshare-tree");
  container.innerHTML = "";
  const filter = document.getElementById("search-input").value.trim().toLowerCase();
  const filtered = filter ? entries.filter((e) => e.key.toLowerCase().includes(filter)) : entries;
  const tree = buildTree(filtered);
  container.appendChild(renderNode(tree));
}

function renderNode(node) {
  const ul = document.createElement("ul");
  Object.entries(node.children || {}).forEach(([name, child]) => {
    const li = document.createElement("li");
    if (child.entry) {
      li.appendChild(renderLeafRow(child.entry));
    } else {
      const label = document.createElement("span");
      label.className = "tree-group";
      label.textContent = `▾ ${name}`;
      li.appendChild(label);
      li.appendChild(renderNode(child));
    }
    ul.appendChild(li);
  });
  return ul;
}

function renderLeafRow(entry) {
  const row = document.createElement("div");
  row.className = "leaf-row";

  const keyLabel = document.createElement("span");
  keyLabel.className = "leaf-key";
  keyLabel.textContent = entry.key.split(".").pop();
  row.appendChild(keyLabel);

  const valueSpan = document.createElement("span");
  valueSpan.className = "leaf-value";
  valueSpan.textContent = entry.value;
  row.appendChild(valueSpan);

  return row;
}
```

Also add the search box listener inside `init()`:
```js
  document.getElementById("search-input").addEventListener("input", () => render());
```

And load the ClickShare tab's data on startup, at the end of `init()`:
```js
  await loadDomain("clickshare");
```

- [ ] **Step 2: Manual smoke test**

Run: `python app.py` (from `src/wave4-dev-tool/`), with a real Duvel device
attached and `adb` on PATH.
Expected: ClickShare tab shows a collapsible tree grouped by `.`-separated
key prefixes (e.g. a `clickshare` group node expands to reveal `button` →
`timeout = 30`); typing in the search box filters the tree to matching
leaves as you type.

If no device is attached, expected: the `#status-banner` shows "無法連接裝置"
instead of a blank/broken tree.

- [ ] **Step 3: Commit**

```bash
git add src/wave4-dev-tool/ui/app.js
git commit -m "add clickshare tree rendering and search filter"
```

---

### Task 10: Inline edit/save/cancel + delete + add key (ClickShare tab)

**Files:**
- Modify: `src/wave4-dev-tool/ui/app.js`

**Interfaces:**
- Consumes: `pywebview.api.update_config(domain, key, value)`, `pywebview.api.delete_clickshare(key)`, `pywebview.api.insert_clickshare(key, value)` (Task 7); `renderLeafRow`, `loadDomain` (Task 9, same file).
- Produces: `startEdit(row, entry, valueEl)` (reused unmodified by Task 11 for the System tab's flat rows); `onDelete(key)`; `onAddKey()`; `showRowError(row, message)`.

- [ ] **Step 1: Add edit/delete controls to renderLeafRow, and the supporting handlers**

Replace `renderLeafRow` in `src/wave4-dev-tool/ui/app.js` with:
```js
function renderLeafRow(entry) {
  const row = document.createElement("div");
  row.className = "leaf-row";

  const keyLabel = document.createElement("span");
  keyLabel.className = "leaf-key";
  keyLabel.textContent = entry.key.split(".").pop();
  row.appendChild(keyLabel);

  const valueSpan = document.createElement("span");
  valueSpan.className = "leaf-value";
  valueSpan.textContent = entry.value;
  row.appendChild(valueSpan);

  if (entry.editable) {
    const editBtn = document.createElement("button");
    editBtn.textContent = "✎";
    editBtn.addEventListener("click", () => startEdit(row, entry, valueSpan));
    row.appendChild(editBtn);
  }

  if (entry.domain === "clickshare") {
    const delBtn = document.createElement("button");
    delBtn.textContent = "🗑";
    delBtn.addEventListener("click", () => onDelete(entry.key));
    row.appendChild(delBtn);
  }

  return row;
}
```

Append the shared edit/delete/add-key handlers:
```js
function startEdit(row, entry, valueEl) {
  const input = document.createElement("input");
  input.value = entry.value;

  const saveBtn = document.createElement("button");
  saveBtn.textContent = "Save";
  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "Cancel";

  saveBtn.addEventListener("click", async () => {
    const result = await pywebview.api.update_config(entry.domain, entry.key, input.value);
    if (result.success) {
      entry.value = input.value;
      valueEl.textContent = entry.value;
      row.replaceChild(valueEl, input);
      saveBtn.remove();
      cancelBtn.remove();
    } else {
      showRowError(row, result.error);
    }
  });

  cancelBtn.addEventListener("click", () => {
    row.replaceChild(valueEl, input);
    saveBtn.remove();
    cancelBtn.remove();
  });

  row.replaceChild(input, valueEl);
  row.appendChild(saveBtn);
  row.appendChild(cancelBtn);
}

function showRowError(row, message) {
  let errEl = row.querySelector(".row-error");
  if (!errEl) {
    errEl = document.createElement("span");
    errEl.className = "row-error";
    row.appendChild(errEl);
  }
  errEl.textContent = message || "儲存失敗";
}

async function onDelete(key) {
  const result = await pywebview.api.delete_clickshare(key);
  if (result.success) {
    await loadDomain("clickshare");
  } else {
    showStatus(`刪除失敗: ${result.error}`);
  }
}

async function onAddKey() {
  const key = prompt("新 key 名稱:");
  if (!key) return;
  const value = prompt("初始值:") || "";
  const result = await pywebview.api.insert_clickshare(key, value);
  if (result.success) {
    await loadDomain("clickshare");
  } else {
    showStatus(`新增失敗: ${result.error}`);
  }
}
```

Wire up the "+ 新增 key" button inside `init()`:
```js
  document.getElementById("add-key-btn").addEventListener("click", onAddKey);
```

- [ ] **Step 2: Manual smoke test**

Run: `python app.py` with a real device attached.
Expected:
1. Click ✎ on a ClickShare leaf → value becomes an editable text box with
   Save/Cancel. Change the value, click Save → row reverts to display mode
   with the new value; re-running `adb shell content query --uri
   content://com.barco.clickshare.configurationmanager.provider/clickshare/<key>`
   from a terminal confirms the device actually changed.
2. Click Cancel instead → row reverts to display mode with the original
   value, no device write happens.
3. Click 🗑 on a leaf → row disappears from the tree (tree reloads); confirm
   via `adb shell content query` that the key is gone.
4. Click "+ 新增 key" → enter a new key/value in the two prompts → new leaf
   appears in the tree in the correct branch.

- [ ] **Step 3: Commit**

```bash
git add src/wave4-dev-tool/ui/app.js
git commit -m "add clickshare inline edit, delete, and add-key flows"
```

---

### Task 11: System and MDEP tab rendering

**Files:**
- Modify: `src/wave4-dev-tool/ui/app.js`

**Interfaces:**
- Consumes: `pywebview.api.list_config("system")`, `pywebview.api.get_mdep(key)` (Task 7); `startEdit`, `loadDomain`, `render`, `showStatus`, `hideStatus` (Tasks 9–10, same file).
- Produces: `renderFlatTable(entries, tableId)` (used by both System and MDEP tabs); `onMdepQuery()`.

- [ ] **Step 1: Add flat table rendering and wire it into `render()` and the MDEP query flow**

Update `render()` in `src/wave4-dev-tool/ui/app.js`:
```js
function render() {
  if (state.domain === "clickshare") {
    renderTree(state.entries);
  } else if (state.domain === "system") {
    renderFlatTable(state.entries, "system-table");
  }
}
```

Append:
```js
function renderFlatTable(entries, tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  const filter = document.getElementById("search-input").value.trim().toLowerCase();
  const filtered = filter ? entries.filter((e) => e.key.toLowerCase().includes(filter)) : entries;
  filtered.forEach((entry) => {
    const tr = document.createElement("tr");

    const keyTd = document.createElement("td");
    keyTd.textContent = entry.key;
    tr.appendChild(keyTd);

    const valueTd = document.createElement("td");
    valueTd.textContent = entry.value;
    tr.appendChild(valueTd);

    const actionTd = document.createElement("td");
    if (entry.editable) {
      const editBtn = document.createElement("button");
      editBtn.textContent = "✎";
      editBtn.addEventListener("click", () => startEdit(tr, entry, valueTd));
      actionTd.appendChild(editBtn);
    }
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  });
}

async function onMdepQuery() {
  const key = document.getElementById("mdep-key-input").value.trim();
  if (!key) return;
  const result = await pywebview.api.get_mdep(key);
  const tbody = document.querySelector("#mdep-table tbody");
  tbody.innerHTML = "";
  if (!result.success) {
    showStatus(result.error);
    return;
  }
  hideStatus();
  renderFlatTable([result.entry], "mdep-table");
}
```

Wire up the MDEP query button inside `init()`:
```js
  document.getElementById("mdep-query-btn").addEventListener("click", onMdepQuery);
```

- [ ] **Step 2: Manual smoke test**

Run: `python app.py` with a real device attached.
Expected:
1. System tab: loads automatically on click, shows a flat table; rows for
   `Properties.*` keys have no ✎ button (read-only, per spec); rows for
   `Settings.*` keys have ✎ and editing one round-trips through
   `adb shell content query --uri content://.../system/Settings.ScreenOffTimeout`.
2. MDEP tab: type a known MDEP key into the input, click 查詢 → single-row
   table appears with the value and an edit button; typing an unknown key
   shows the status banner with the "not found" error instead of a blank
   table.

- [ ] **Step 3: Commit**

```bash
git add src/wave4-dev-tool/ui/app.js
git commit -m "add system and mdep tab rendering"
```

---

### Task 12: Export JSON, PyInstaller packaging, full smoke test

**Files:**
- Modify: `src/wave4-dev-tool/ui/app.js` (export button handler)
- Create: `src/wave4-dev-tool/build.bat`

**Interfaces:**
- Consumes: `pywebview.api.export_config()`, `pywebview.api.save_json_to_file(json_str)` (Task 7).
- Produces: a working `dist/wave4-dev-tool.exe` (build artifact, not committed).

- [ ] **Step 1: Add the export button handler**

Append to `src/wave4-dev-tool/ui/app.js`:
```js
async function onExport() {
  const result = await pywebview.api.export_config();
  if (!result.success) {
    showStatus(`匯出失敗: ${result.error}`);
    return;
  }
  const saveResult = await pywebview.api.save_json_to_file(result.json);
  if (!saveResult.success && saveResult.error !== "cancelled") {
    showStatus(`儲存失敗: ${saveResult.error}`);
  }
}
```

Wire up the button inside `init()`:
```js
  document.getElementById("export-btn").addEventListener("click", onExport);
```

- [ ] **Step 2: Manual smoke test — export**

Run: `python app.py` with a real device attached, ClickShare tab active,
click "匯出 JSON".
Expected: a native "Save As" file dialog opens. Save to a local path;
confirm the saved file contains valid JSON. **This is also the point to
verify the `export_config` Bundle-parsing assumption from Task 4** — if the
save fails or the JSON looks truncated/wrong, run
`adb shell content call --uri content://com.barco.clickshare.configurationmanager.provider/clickshare --method export_config`
manually from a terminal, inspect the actual `Result: Bundle[...]` text, and
adjust `_extract_json_field` in `backend/config_provider.py` (with a
corresponding test update in `test_config_provider.py`) to match.

- [ ] **Step 3: Write build.bat**

`src/wave4-dev-tool/build.bat`:
```bat
@echo off
cd /d "%~dp0"
pip install -r requirements.txt
pyinstaller --onefile --add-data "ui;ui" --name wave4-dev-tool app.py
echo.
echo Build complete: dist\wave4-dev-tool.exe
pause
```

- [ ] **Step 4: Run the build**

Run: `src\wave4-dev-tool\build.bat`
Expected: completes without error, produces `src/wave4-dev-tool/dist/wave4-dev-tool.exe`.

- [ ] **Step 5: Full smoke test against the packaged exe**

Run: `src\wave4-dev-tool\dist\wave4-dev-tool.exe` directly (not via `python app.py`) with a real device attached.
Expected: same behavior as Task 11's manual smoke tests — window opens, all
three tabs work, edit/delete/add-key/export all function — but now with zero
Python installed in the shell running it (test from a fresh `cmd.exe`, not
one with an activated venv, to confirm no hidden dependency on the dev
environment).

- [ ] **Step 6: Commit**

```bash
git add src/wave4-dev-tool/ui/app.js src/wave4-dev-tool/build.bat
git commit -m "add export-to-json flow and pyinstaller build script"
```

(Do not commit `dist/` or `build/` — add them to `.gitignore` if not already covered by an existing rule; check `git status` after Step 6 and add a `src/wave4-dev-tool/.gitignore` with `dist/` and `build/` and `*.spec` if PyInstaller's output shows up as untracked.)

---

### Task 13: Documentation sync (README.md, CLAUDE.md)

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Add a "Wave4 Dev Tool" section to README.md**

Find the section documenting `src/` utilities in `README.md` (mirrors the
existing `src/timesheet` / `src/hid-test` write-ups) and add a matching
entry, e.g.:

```markdown
### Wave4 Dev Tool (`src/wave4-dev-tool/`)

Standalone Windows GUI for browsing and editing `configuration-manager-apk`
settings over ADB, across multiple connected devices. Built with
Python + pywebview (HTML/CSS/JS UI) and packaged as a single `.exe` via
PyInstaller.

```bash
# Run from source
pip install -r src/wave4-dev-tool/requirements.txt
python src/wave4-dev-tool/app.py

# Build a standalone .exe
src\wave4-dev-tool\build.bat
```

Three tabs: **ClickShare** (full CRUD, tree view grouped by `.`-separated
key prefix, supports add/delete/export-to-JSON), **System** (fixed set of OS
settings/properties — `Settings.*` editable, `Properties.*` read-only),
**MDEP** (single-key lookup, no list API). Device dropdown lists all
`adb devices -l` output; supports connecting to a new device by `IP:port`.
```

- [ ] **Step 2: Add the src/ utilities entry to CLAUDE.md**

In `CLAUDE.md`, under the `## src/ utilities` section (after the `src/hid-desc/`
write-up, before `## Architecture`), add:

```markdown
**Wave4 dev tool** (`src/wave4-dev-tool/`): Standalone Windows GUI (Python +
pywebview + PyInstaller `--onefile`) for browsing/editing
`configuration-manager-apk` settings over ADB across multiple connected
devices. Talks to the APK's `ContentProvider`
(`com.barco.clickshare.configurationmanager.provider`) via
`adb shell content query/insert/update/delete/call` — no root required.

```bash
pip install -r src/wave4-dev-tool/requirements.txt
python src/wave4-dev-tool/app.py       # run from source
src\wave4-dev-tool\build.bat            # build dist\wave4-dev-tool.exe
```

`backend/config_provider.py` covers three ContentProvider subtrees:
`clickshare/*` (arbitrary key-value store, full CRUD + `export_config` call
method for a full JSON dump), `system/*` (fixed key table in `SYSTEM_KEYS` —
`Settings.*` read/write, `Properties.*` read-only because the APK itself
rejects writes to that prefix), `mdep/*` (single-key get/set, no list API).
The `system/*` key table has no enumeration API on the APK side and must be
hand-updated in `SYSTEM_KEYS` if `configuration-manager-apk`'s
`SystemManagerImpl.kt` changes. UI: `ui/index.html` + `ui/app.js` render the
ClickShare tab as a collapsible tree (grouped by splitting keys on `.`) and
the System/MDEP tabs as flat tables; edits are inline (Save/Cancel, no
confirmation dialog, no backup of the previous value) via
`pywebview.api.update_config(domain, key, value)`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "document wave4-dev-tool in README and CLAUDE.md"
```

---

## Self-Review Notes

- **Spec coverage:** all 8 design-doc sections map to tasks — ContentProvider
  domains → Tasks 3–6; multi-device → Task 2 + Task 8; UI layout/tree →
  Tasks 8–11; data flow/error handling → Tasks 7, 9–11; export →
  Task 4 + Task 12; packaging → Task 12; docs → Task 13.
- **Known open risk, flagged explicitly rather than hidden:** the
  `export_config` Bundle-string parsing in Task 4 is built from the standard
  Android `Bundle.toString()` format but not yet verified against a real
  device — Task 12 Step 2 is the checkpoint that confirms or fixes it before
  the plan is considered done.
- **Type/name consistency checked:** `ConfigEntry(domain, key, value, editable)`
  from Task 1 is used identically in every backend function's return type
  (Tasks 3–6) and every `.__dict__` serialization in `app.py` (Task 7);
  `state.serial`/`state.domain`/`state.entries` set in Task 8 are the exact
  names read in Tasks 9–11; `pywebview.api.*` method names in `app.py`
  (Task 7) match every `pywebview.api.*` call site in `app.js` (Tasks 8–12).

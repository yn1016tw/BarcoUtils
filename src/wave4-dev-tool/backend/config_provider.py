import json
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


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


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


def list_clickshare(serial: str | None, prefix: str = "", adb_path: str = "adb") -> tuple[bool, list[ConfigEntry]]:
    if not prefix:
        # The real ContentProvider's query() bails out ("No key found from
        # query uri") whenever the URI has no key segment past "clickshare"
        # — confirmed against a real device: `clickshare/` and `clickshare`
        # both return zero rows even though the device has ~90 real entries,
        # while `clickshare/<any-prefix>` works fine. export_config is the
        # APK's own reliable way to get everything, so listing-all goes
        # through it instead of a direct content query.
        ok, payload = export_clickshare_config(serial, adb_path)
        if not ok:
            return False, []
        try:
            config = json.loads(payload).get("config", {})
        except (json.JSONDecodeError, AttributeError, TypeError):
            return False, []
        entries = [
            ConfigEntry(domain="clickshare", key=key, value=str(value), editable=True)
            for key, value in config.items()
        ]
        return True, entries

    uri = f"content://{AUTHORITY}/clickshare/{_shell_quote(prefix)}"
    cmd = _adb_cmd(
        serial,
        ["content", "query", "--uri", uri, "--projection", "key:value"],
        adb_path,
    )
    ok, output = _run(cmd)
    if not ok:
        return False, []
    entries = [
        ConfigEntry(domain="clickshare", key=key, value=value, editable=True)
        for key, value in parse_content_query_output(output)
    ]
    return True, entries


def update_clickshare(serial: str | None, key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    ok, existing = list_clickshare(serial, prefix=key, adb_path=adb_path)
    exists = ok and any(e.key == key for e in existing)
    if exists:
        uri = f"content://{AUTHORITY}/clickshare/{_shell_quote(key)}"
        cmd = _adb_cmd(
            serial,
            ["content", "update", "--uri", uri, "--bind", _shell_quote(f"value:s:{value}")],
            adb_path,
        )
        return _run(cmd)
    return insert_clickshare(serial, key, value, adb_path)


def insert_clickshare(serial: str | None, key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/clickshare/{_shell_quote(key)}"
    cmd = _adb_cmd(
        serial,
        ["content", "insert", "--uri", uri, "--bind", _shell_quote(f"value:s:{value}")],
        adb_path,
    )
    return _run(cmd)


def delete_clickshare(serial: str | None, key: str, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/clickshare/{_shell_quote(key)}"
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


def _query_single_value(serial: str | None, uri: str, adb_path: str) -> tuple[bool, str | None]:
    cmd = _adb_cmd(serial, ["content", "query", "--uri", uri], adb_path)
    ok, output = _run(cmd)
    if not ok:
        return False, None
    rows = parse_content_query_output(output)
    return True, (rows[0][1] if rows else None)


def get_system_value(serial: str | None, logical_key: str, adb_path: str = "adb") -> str | None:
    uri = f"content://{AUTHORITY}/system/{_shell_quote(logical_key)}"
    ok, value = _query_single_value(serial, uri, adb_path)
    return value if ok else None


def list_system(serial: str | None, adb_path: str = "adb") -> tuple[bool, list[ConfigEntry]]:
    entries = []
    for i, (logical_key, editable) in enumerate(SYSTEM_KEYS.items()):
        uri = f"content://{AUTHORITY}/system/{_shell_quote(logical_key)}"
        ok, value = _query_single_value(serial, uri, adb_path)
        if not ok:
            if i == 0:
                return False, []
            value = None
        entries.append(ConfigEntry(domain="system", key=logical_key, value=value or "", editable=editable))
    return True, entries


def update_system(serial: str | None, logical_key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    if not SYSTEM_KEYS.get(logical_key, False):
        return False, f"{logical_key} is read-only"
    uri = f"content://{AUTHORITY}/system/{_shell_quote(logical_key)}"
    cmd = _adb_cmd(
        serial,
        ["content", "update", "--uri", uri, "--bind", _shell_quote(f"value:s:{value}")],
        adb_path,
    )
    return _run(cmd)


def get_mdep_value(serial: str | None, key: str, adb_path: str = "adb") -> ConfigEntry | None:
    uri = f"content://{AUTHORITY}/mdep/{_shell_quote(key)}"
    cmd = _adb_cmd(serial, ["content", "query", "--uri", uri], adb_path)
    ok, output = _run(cmd)
    if not ok:
        return None
    rows = parse_content_query_output(output)
    if not rows:
        return None
    return ConfigEntry(domain="mdep", key=key, value=rows[0][1], editable=True)


def update_mdep(serial: str | None, key: str, value: str, adb_path: str = "adb") -> tuple[bool, str]:
    uri = f"content://{AUTHORITY}/mdep/{_shell_quote(key)}"
    cmd = _adb_cmd(
        serial,
        ["content", "update", "--uri", uri, "--bind", _shell_quote(f"value:s:{value}")],
        adb_path,
    )
    return _run(cmd)

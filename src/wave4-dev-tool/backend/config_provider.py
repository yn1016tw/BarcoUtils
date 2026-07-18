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

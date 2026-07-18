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

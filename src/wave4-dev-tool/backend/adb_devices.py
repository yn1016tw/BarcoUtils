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
    try:
        result = subprocess.run(
            [adb_path, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return parse_devices_output(result.stdout)


def connect_ip(ip_port: str, adb_path: str = "adb", timeout: float = 5.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [adb_path, "connect", ip_port],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "adb not found or timed out"
    output = (result.stdout or "") + (result.stderr or "")
    success = "connected to" in output.lower()
    return success, output.strip()

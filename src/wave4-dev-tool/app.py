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
            ok, entries = config_provider.list_clickshare(self.serial)
        elif domain == "system":
            ok, entries = config_provider.list_system(self.serial)
        else:
            return {"success": False, "error": f"domain '{domain}' has no list API"}
        if not ok:
            return {"success": False, "error": "無法連接裝置"}
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

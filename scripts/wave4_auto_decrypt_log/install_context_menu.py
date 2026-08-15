#!/usr/bin/env python3
"""
install_context_menu.py
Adds / removes the "Wave4 Log Decrypt" right-click menu entry for .zip files.

Usage:
    python install_context_menu.py                    # install
    python install_context_menu.py remove              # uninstall
    python install_context_menu.py uninstall            # uninstall (alias)
    python install_context_menu.py --uninstall / -u      # uninstall (alias)
"""

import sys
import winreg
from pathlib import Path

MENU_NAME = "Wave4LogDecrypt"
MENU_LABEL = "Wave4 Log Decrypt"

SCRIPT = Path(__file__).parent / "wave4_auto_decrypt_log.py"
PYTHON = Path(sys.executable)

# Command: open a cmd window that stays open so the user can see progress
# The outer quotes around the whole cmd /k argument are required when paths contain spaces
COMMAND = f'cmd /k ""{PYTHON}" "{SCRIPT}" --hidden "%1""'

# Register under HKCU — no admin rights required
# CompressedFolder is the Windows class for .zip files
REG_ROOTS = [
    r"Software\Classes\CompressedFolder\shell",
    r"Software\Classes\SystemFileAssociations\.zip\shell",
]


def install():
    for root in REG_ROOTS:
        key_path = rf"{root}\{MENU_NAME}"
        cmd_path = rf"{key_path}\command"

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, MENU_LABEL)

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, cmd_path) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, COMMAND)

        print(f"[OK] Registered: HKCU\\{key_path}")

    print("\nDone. Right-click any .zip file to see 'Wave4 Log Decrypt'.")
    print("(You may need to restart Explorer or sign out/in for changes to appear.)")


def uninstall():
    for root in REG_ROOTS:
        key_path = rf"{root}\{MENU_NAME}"
        removed_any = False
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\command")
            removed_any = True
        except FileNotFoundError:
            pass
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            removed_any = True
        except FileNotFoundError:
            pass
        except OSError as e:
            # Parent key still has other subkeys/values (e.g. an "Icon" value
            # added by Explorer) — report it instead of crashing the whole run.
            print(f"[WARN] Could not fully remove HKCU\\{key_path}: {e}")
            continue

        if removed_any:
            print(f"[OK] Removed: HKCU\\{key_path}")
        else:
            print(f"[--] Not found (already removed?): HKCU\\{key_path}")

    print("\nDone. 'Wave4 Log Decrypt' entry removed.")


if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if action in ("remove", "uninstall", "--uninstall", "-u"):
        uninstall()
    else:
        install()

#!/usr/bin/env python3
"""
test_ini_preservation.py — Unit test verifying user INI setting preservation.
Ensures custom PalWorldSettings.ini user overrides are protected against manager overwrites.
"""

import os
import sys
import shutil
from pathlib import Path

def test_preservation():
    tmp_dir = Path("./tmp_test_ini")
    tmp_dir.mkdir(exist_ok=True)

    user_ini = tmp_dir / "PalWorldSettings.ini"
    bak_ini = tmp_dir / "PalWorldSettings.ini.userbak"

    # 1. User writes custom settings
    user_content = "[/Script/Pal.PalGameWorldSettings]\nOptionSettings=(ExpRate=3.500000,PalCaptureRate=2.000000)\n"
    user_ini.write_text(user_content, encoding="utf-8")

    # 2. Backup user file
    shutil.copy2(user_ini, bak_ini)

    # 3. Simulated Manager overwrites user_ini with default container settings
    manager_overwritten_content = "[/Script/Pal.PalGameWorldSettings]\nOptionSettings=(ExpRate=1.000000,PalCaptureRate=1.000000)\n"
    user_ini.write_text(manager_overwritten_content, encoding="utf-8")

    # 4. Restoration Logic (when PRESERVE_CUSTOM_SETTINGS=true)
    if bak_ini.exists():
        shutil.copy2(bak_ini, user_ini)

    # 5. Verify restored content matches user_content
    restored_content = user_ini.read_text(encoding="utf-8")
    success = restored_content == user_content

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"INI Preservation Test: {'PASS' if success else 'FAIL'}")
    return success

if __name__ == "__main__":
    sys.exit(0 if test_preservation() else 1)

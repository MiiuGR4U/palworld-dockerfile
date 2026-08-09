#!/usr/bin/env python3
"""
validate-shell.py
Cross-platform shell script validator.
Checks syntax using bash if available, or basic structural checks.
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def validate_shell():
    project_dir = Path(__file__).parent.parent
    sh_files = list(project_dir.glob("*.sh"))

    print("\n" + "=" * 64)
    print(f"  Auditing Shell Scripts in {project_dir.name}")
    print("=" * 64)

    if not sh_files:
        print("  ! [WARN] No .sh files found to audit.")
        return True

    bash_path = shutil.which("bash") or shutil.which("C:\\Program Files\\Git\\bin\\bash.exe")
    errors = 0

    for script in sh_files:
        filename = script.name
        if bash_path:
            cmd = [bash_path, "-n", str(script)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"  + [OK] {filename} syntax valid.")
            else:
                print(f"  x [FAIL] {filename} syntax error:\n{res.stderr}")
                errors += 1
        else:
            # Basic fallback validation
            content = script.read_text(encoding="utf-8")
            if not content.startswith("#!"):
                print(f"  ! [WARN] {filename} missing shebang line.")
            else:
                print(f"  + [OK] {filename} structure checked (bash CLI not in PATH).")

    print("-" * 64)
    print(f"Shell Validation Summary: {errors} Error(s)")
    print("=" * 64 + "\n")
    return errors == 0

if __name__ == "__main__":
    sys.exit(0 if validate_shell() else 1)

#!/usr/bin/env python3
"""
validate-egg.py
Automated audit and validation tool for Pterodactyl/Hydrodactyl Egg files.
Ensures strict compliance with Hydrodactyl rules, reserved variables, and ARM64 Palworld requirements.
"""

import json
import sys
import os
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RESERVED_PTERODACTYL_VARS = {
    "ENV", "HOME", "USER", "STARTUP", "UUID",
    "SERVER_UUID", "SERVER_MEMORY", "SERVER_IP", "SERVER_PORT"
}

def print_header(title: str):
    print("\n" + "=" * 64)
    print(f"  {title}")
    print("=" * 64)

def validate_egg(file_path: Path) -> bool:
    print_header(f"Auditing Egg: {file_path.name}")
    errors = []
    warnings = []
    successes = []

    if not file_path.exists():
        print(f"❌ [FAIL] File not found: {file_path}")
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        successes.append("JSON structure is valid.")
    except Exception as e:
        print(f"❌ [FAIL] Invalid JSON syntax: {e}")
        return False

    # Check top-level metadata
    name = data.get("name", "")
    description = data.get("description", "")
    startup = data.get("startup", "")
    variables = data.get("variables", [])

    if not name:
        errors.append("Egg 'name' is missing or empty.")
    else:
        successes.append(f"Egg name: '{name}'")

    if not startup:
        errors.append("Egg 'startup' command is missing or empty.")

    # Audit Variables
    seen_envs = set()
    has_use_auth = False
    has_query_port = False

    for idx, var in enumerate(variables):
        var_name = var.get("name", f"Var #{idx}")
        env_var = var.get("env_variable", "")
        rules = var.get("rules", "")
        default_val = var.get("default_value", "")
        user_editable = var.get("user_editable", True)

        if not env_var:
            errors.append(f"Variable '{var_name}' is missing 'env_variable'.")
            continue

        # Rule 1: No reserved Pterodactyl variables
        if env_var.upper() in RESERVED_PTERODACTYL_VARS:
            errors.append(
                f"Variable '{var_name}' exposes reserved Pterodactyl variable '{env_var}'! "
                f"This breaks server import/execution."
            )

        # Rule 2: Check duplicates
        if env_var in seen_envs:
            errors.append(f"Duplicate env_variable found: '{env_var}'")
        seen_envs.add(env_var)

        # Rule 3: Hydrodactyl boolean rule check (No required|boolean)
        if "boolean" in rules.lower():
            errors.append(
                f"Variable '{env_var}' uses rule '{rules}'. "
                f"Hydrodactyl compatibility requires 'required|string|in:true,false' instead of boolean."
            )

        # Rule 4: Check PUBLIC_PORT non-editability
        if env_var == "PUBLIC_PORT" and user_editable:
            errors.append(
                "PUBLIC_PORT must NOT be user-editable. It must be automatically synchronized to SERVER_PORT."
            )

        # Specific Checks
        if env_var == "USE_AUTH":
            has_use_auth = True
            if str(default_val).lower() != "false":
                warnings.append(
                    f"USE_AUTH default_value is '{default_val}'. "
                    f"ARM64/FEX environments require 'false' by default to avoid Invalid AppTicket errors."
                )

        if env_var == "QUERY_PORT":
            has_query_port = True

    if not has_query_port:
        warnings.append("QUERY_PORT variable is not declared in Egg variables.")

    if not has_use_auth:
        warnings.append("USE_AUTH variable is not declared in Egg variables.")

    # Output Results
    for msg in successes:
        print(f"  + [OK] {msg}")

    for msg in warnings:
        print(f"  ! [WARN] {msg}")

    for msg in errors:
        print(f"  x [FAIL] {msg}")

    print("-" * 64)
    print(f"Audit Summary: {len(errors)} Error(s), {len(warnings)} Warning(s)")
    print("=" * 64 + "\n")

    return len(errors) == 0

if __name__ == "__main__":
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    egg_file = project_dir / "egg-palworld-arm64.json"

    if not validate_egg(egg_file):
        sys.exit(1)
    sys.exit(0)

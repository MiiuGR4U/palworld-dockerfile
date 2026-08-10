#!/usr/bin/env python3
"""Static safety validation for the Pterodactyl/Hydrodactyl Egg."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


RESERVED_PTERODACTYL_VARS = {
    "ENV",
    "HOME",
    "SERVER_IP",
    "SERVER_MEMORY",
    "SERVER_PORT",
    "SERVER_UUID",
    "STARTUP",
    "USER",
    "UUID",
}

BOOLEAN_RULE = "required|string|in:true,false"
REQUIRED_VARIABLES = {"QUERY_PORT", "USE_AUTH"}
REQUIRED_MOD_FLAGS = {
    "ENABLE_BLUEPRINT_MODS",
    "ENABLE_CPP_MODS",
    "ENABLE_LUA_MODS",
    "ENABLE_PATCH_MODS",
    "MODS_BACKUP_ON_CHANGE",
    "MODS_DEBUG",
    "MODS_ENABLED",
    "MODS_FAIL_ON_ERROR",
    "MODS_SAFE_MODE",
    "MODS_SERVER_SIDE_ONLY",
    "MODS_STRICT_VERSION_CHECK",
    "MODS_UE4SS_TEST_MODE",
}
INTERNAL_PORT_DEFAULTS = {
    "REST_API_PORT": "8212",
    "RCON_PORT": "25575",
}
SAFE_FALSE_DEFAULTS = {
    "MODS_ENABLED",
    "MODS_SAFE_MODE",
    "MODS_STRICT_VERSION_CHECK",
    "MODS_UE4SS_TEST_MODE",
    "MODS_DEBUG",
    "ENABLE_BLUEPRINT_MODS",
    "ENABLE_LUA_MODS",
    "ENABLE_CPP_MODS",
}
SAFE_TRUE_DEFAULTS = {
    "MODS_SERVER_SIDE_ONLY",
    "MODS_BACKUP_ON_CHANGE",
    "MODS_FAIL_ON_ERROR",
    "ENABLE_PATCH_MODS",
}


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    successes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _as_lower(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def _validate_variable(
    variable: dict[str, Any], index: int, seen: set[str], report: ValidationReport
) -> None:
    name = str(variable.get("name") or f"variable #{index}")
    env = str(variable.get("env_variable") or "").strip()
    rules = str(variable.get("rules") or "").strip()
    default = variable.get("default_value", "")

    if not env:
        report.errors.append(f"{name}: missing env_variable")
        return

    canonical_env = env.upper()
    if canonical_env in seen:
        report.errors.append(f"Duplicate env_variable: {env}")
    seen.add(canonical_env)

    if canonical_env in RESERVED_PTERODACTYL_VARS:
        report.errors.append(f"Reserved Pterodactyl variable declared: {env}")

    if canonical_env == "PUBLIC_PORT":
        report.errors.append(
            "PUBLIC_PORT must not be an Egg variable; runtime must synchronize it from SERVER_PORT"
        )

    if "boolean" in rules.lower():
        report.errors.append(
            f"{env}: Hydrodactyl does not accept boolean validation; use {BOOLEAN_RULE}"
        )

    default_lower = _as_lower(default)
    if default_lower in {"true", "false"} and rules != BOOLEAN_RULE:
        report.errors.append(f"{env}: string boolean must use exactly {BOOLEAN_RULE}")

    if canonical_env == "USE_AUTH" and default_lower != "false":
        report.errors.append("USE_AUTH must default to false on the ARM64/FEX backend")

    if canonical_env in SAFE_FALSE_DEFAULTS and default_lower != "false":
        report.errors.append(f"{env} has an unsafe default; expected false")

    if canonical_env in SAFE_TRUE_DEFAULTS and default_lower != "true":
        report.errors.append(f"{env} has an unsafe default; expected true")

    expected_internal_port = INTERNAL_PORT_DEFAULTS.get(canonical_env)
    if expected_internal_port and str(default) != expected_internal_port:
        report.errors.append(
            f"{env} must default to the internal port {expected_internal_port}, got {default!r}"
        )

    if canonical_env in {"REST_API_PORT", "RCON_PORT"}:
        if variable.get("user_viewable", True) or variable.get("user_editable", True):
            report.errors.append(f"{env} must remain hidden and non-editable by default")

    if canonical_env == "QUERY_PORT":
        description = str(variable.get("description") or "").lower()
        if "extra" not in description or "allocation" not in description:
            report.errors.append(
                "QUERY_PORT description must clearly identify an EXTRA Pterodactyl Allocation"
            )


def validate_egg_data(data: Any) -> ValidationReport:
    report = ValidationReport()
    if not isinstance(data, dict):
        report.errors.append("Egg root must be a JSON object")
        return report

    if data.get("meta", {}).get("version") != "PTDL_v2":
        report.errors.append("Egg meta.version must be PTDL_v2")

    if not str(data.get("name") or "").strip():
        report.errors.append("Egg name is missing")

    if not str(data.get("startup") or "").strip():
        report.errors.append("Egg startup command is missing")

    docker_images = data.get("docker_images")
    if not isinstance(docker_images, dict) or not docker_images:
        report.errors.append("Egg docker_images is missing or empty")
    else:
        invalid_images = [value for value in docker_images.values() if not str(value).strip()]
        if invalid_images:
            report.errors.append("Egg contains an empty Docker image reference")

    installation = data.get("scripts", {}).get("installation", {})
    if not isinstance(installation, dict):
        report.errors.append("Egg installation definition is missing")
        installation = {}

    installer_image = str(installation.get("container") or "").strip()
    installer_script = str(installation.get("script") or "")
    if not installer_image:
        report.errors.append("Installer Docker image is missing")
    if not installer_script.strip():
        report.errors.append("Installer script is missing")
    else:
        lowered_script = installer_script.lower()
        forbidden_package_managers = ("apt-get", "apt ", "dpkg")
        for token in forbidden_package_managers:
            if token in lowered_script:
                report.errors.append(f"Installer must not invoke package manager token: {token}")
        if "2394010" not in installer_script:
            report.errors.append("Installer does not reference Palworld App ID 2394010")
        if "-os linux" not in installer_script.replace('"', ""):
            report.errors.append("Installer must request the Linux depot")
        if "-osarch 64" not in installer_script.replace('"', ""):
            report.errors.append("Installer must request the 64-bit depot")
        if "Pal/Saved" not in installer_script:
            report.warnings.append(
                "Installer does not explicitly prepare or document the persistent Pal/Saved path"
            )

    variables = data.get("variables")
    if not isinstance(variables, list):
        report.errors.append("Egg variables must be a JSON array")
        variables = []

    seen: set[str] = set()
    for index, variable in enumerate(variables, start=1):
        if not isinstance(variable, dict):
            report.errors.append(f"variable #{index} must be a JSON object")
            continue
        _validate_variable(variable, index, seen, report)

    missing = sorted(REQUIRED_VARIABLES - seen)
    for env in missing:
        report.errors.append(f"Required Egg variable is missing: {env}")

    missing_mod_flags = sorted(REQUIRED_MOD_FLAGS - seen)
    for env in missing_mod_flags:
        report.errors.append(f"Required Mod System feature flag is missing: {env}")

    stop_command = str(data.get("config", {}).get("stop") or "")
    if not stop_command:
        report.errors.append("Egg stop command is missing")

    report.successes.extend(
        [
            "JSON structure loaded",
            f"Validated {len(variables)} unique Egg variable declarations",
            "Reserved-variable and Hydrodactyl boolean checks completed",
            "Installer and image safety checks completed",
        ]
    )
    return report


def validate_egg(path: Path) -> ValidationReport:
    report = ValidationReport()
    if not path.is_file():
        report.errors.append(f"Egg file not found: {path}")
        return report

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report.errors.append(f"Invalid Egg JSON: {exc}")
        return report
    return validate_egg_data(data)


def print_report(path: Path, report: ValidationReport) -> None:
    print("\n" + "=" * 64)
    print(f"  Auditing Egg: {path.name}")
    print("=" * 64)
    for message in report.successes:
        print(f"  + [OK] {message}")
    for message in report.warnings:
        print(f"  ! [WARN] {message}")
    for message in report.errors:
        print(f"  x [FAIL] {message}")
    print("-" * 64)
    print(f"Audit Summary: {len(report.errors)} Error(s), {len(report.warnings)} Warning(s)")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "egg",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "egg-palworld-arm64.json",
    )
    args = parser.parse_args(argv)
    report = validate_egg(args.egg)
    print_report(args.egg, report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

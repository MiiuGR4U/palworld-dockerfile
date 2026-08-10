"""palmodctl command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import logging as log
from .backup import BackupManager
from .config import ModConfig
from .deployer import Deployer
from .scanner import inventory_hash, scan
from .state import read_json, set_override, set_quarantine
from .ue4ss import inspect_bundle
from .validators import validate


def _print_data(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
        return
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    else:
        print(data)


def _print_scan(payload: dict[str, Any], validated: bool) -> None:
    mods = payload.get("mods", [])
    print("[palmodctl] Mod inventory")
    print(f"[palmodctl] Inventory SHA256 : {payload.get('inventory_hash')}")
    print(f"[palmodctl] Detected         : {len(mods)}")
    if validated:
        counts = payload.get("counts", {})
        print(
            "[palmodctl] Types            : "
            f"Patch={counts.get('patch', 0)} Blueprint={counts.get('blueprint', 0)} "
            f"Lua={counts.get('lua', 0)} C++={counts.get('cpp', 0)} "
            f"Rejected={counts.get('rejected', 0)}"
        )
        print(
            f"[palmodctl] UE4SS required   : "
            f"{'yes' if payload.get('ue4ss_required') else 'no'}"
        )
    for mod in mods:
        state = "enabled" if mod.get("enabled") else "disabled"
        validity = "valid" if mod.get("valid") else "rejected"
        print(
            f"[palmodctl] priority={mod.get('priority')} id={mod.get('id')} "
            f"type={mod.get('type')} status={mod.get('status')} {state}/{validity}"
        )
    for warning in payload.get("warnings", []):
        log.warn(warning)
    for error in payload.get("errors", []):
        log.error(error)


def _print_status(inventory: dict[str, Any], config: ModConfig) -> None:
    mods = inventory.get("mods", []) if isinstance(inventory.get("mods"), list) else []
    counts = {mod_type: 0 for mod_type in ("patch", "blueprint", "lua", "cpp")}
    rejected = 0
    quarantined = 0
    for mod in mods:
        if not isinstance(mod, dict):
            continue
        if mod.get("type") in counts:
            counts[mod["type"]] += 1
        rejected += 0 if mod.get("valid", True) else 1
        quarantined += 1 if mod.get("quarantined") else 0
    deployment = inventory.get("deployment", {})
    deployed_count = len(deployment.get("files", [])) if isinstance(deployment, dict) else 0
    print("============================================================")
    print(" Mod System")
    print("------------------------------------------------------------")
    print(f" Enabled      : {'yes' if config.enabled else 'no'}")
    print(f" Safe Mode    : {'yes' if config.safe_mode else 'no'}")
    print(f" State        : {inventory.get('status', 'not-deployed')}")
    print(f" Patch Pak    : {counts['patch']}")
    print(f" Blueprint    : {counts['blueprint']}")
    print(f" Lua          : {counts['lua']}")
    print(f" C++ Linux    : {counts['cpp']}")
    print(f" Rejected     : {rejected}")
    print(f" Quarantined  : {quarantined}")
    print(f" Deployed     : {deployed_count} files")
    print(
        f" UE4SS        : {'required (EXPERIMENTAL)' if inventory.get('ue4ss_required') else 'off'}"
    )
    print("============================================================")


def _scan_payload(config: ModConfig, validated: bool) -> dict[str, Any]:
    if validated:
        result = validate(config)
        return {
            "inventory_hash": result.inventory_hash,
            "counts": result.counts(),
            "ue4ss_required": result.ue4ss_required or config.ue4ss_test_mode,
            "errors": result.errors,
            "warnings": result.warnings,
            "mods": [mod.to_dict() for mod in result.mods],
        }
    records = scan(config)
    return {
        "inventory_hash": inventory_hash(records),
        "mods": [record.to_dict() for record in records],
    }


def _doctor(config: ModConfig) -> dict[str, Any]:
    result = validate(config)
    ue4ss = inspect_bundle(config)
    ue4ss_required = result.ue4ss_required or config.ue4ss_test_mode
    fex_binary = shutil.which("FEXBash")
    fex_rootfs = os.getenv("FEX_ROOTFS")
    checks: dict[str, Any] = {
        "server_root": {
            "path": str(config.server_root),
            "exists": config.server_root.is_dir(),
            "writable": os.access(config.server_root, os.W_OK),
        },
        "mods_root": {
            "path": str(config.mods_root),
            "exists": config.mods_root.is_dir(),
            "writable": os.access(config.mods_root, os.W_OK),
        },
        "fex": {
            "binary": fex_binary,
            "rootfs": fex_rootfs,
        },
        "mod_validation_errors": result.errors,
        "ue4ss_required": ue4ss_required,
        "ue4ss": ue4ss.to_dict(),
    }
    checks["ok"] = bool(
        checks["server_root"]["exists"]
        and checks["server_root"]["writable"]
        and checks["mods_root"]["exists"]
        and checks["mods_root"]["writable"]
        and bool(fex_binary)
        and bool(fex_rootfs)
        and not result.errors
        and (not ue4ss_required or ue4ss.available)
    )
    return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palmodctl", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--server-root", type=Path, help="Override /home/container for testing")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in (
        "scan",
        "list",
        "validate",
        "doctor",
        "deploy",
        "clean",
        "status",
        "preload-path",
    ):
        subparsers.add_parser(command)
    subparsers.add_parser("backup")
    subparsers.add_parser("backup-if-needed")

    enable = subparsers.add_parser("enable")
    enable.add_argument("mod_id")
    disable = subparsers.add_parser("disable")
    disable.add_argument("mod_id")

    quarantine = subparsers.add_parser("quarantine")
    quarantine.add_argument("mod_id")
    quarantine.add_argument("reason", nargs="?", default="operator quarantine")
    quarantine.add_argument("--clear", action="store_true")

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("backup")
    rollback.add_argument(
        "--restore-saves",
        action="store_true",
        help="Explicitly restore SaveGames and Config from the selected backup",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    config = ModConfig.from_env(args.server_root)
    command = args.command

    if command in {"scan", "list"}:
        payload = _scan_payload(config, validated=False)
        _print_data(payload, True) if args.json else _print_scan(payload, validated=False)
        return 0
    if command == "validate":
        payload = _scan_payload(config, validated=True)
        _print_data(payload, True) if args.json else _print_scan(payload, validated=True)
        return 0 if not payload["errors"] else 2

    if command in {
        "doctor",
        "deploy",
        "clean",
        "backup",
        "backup-if-needed",
        "enable",
        "disable",
        "quarantine",
        "rollback",
    }:
        config.initialize_directories()

    if command == "doctor":
        payload = _doctor(config)
        _print_data(payload, args.json)
        return 0 if payload["ok"] else 2
    if command == "deploy":
        payload = Deployer(config).deploy()
        _print_data(payload, args.json)
        return 0
    if command == "clean":
        removed = Deployer(config).clean()
        _print_data({"status": "clean", "removed": [str(path) for path in removed]}, args.json)
        return 0
    if command == "status":
        payload = read_json(config.inventory_path, {"status": "not-deployed"})
        _print_data(payload, True) if args.json else _print_status(payload, config)
        return 0
    if command == "preload-path":
        inventory = read_json(config.inventory_path, {})
        library = config.ue4ss_deploy_root / "libUE4SS.so"
        if (
            isinstance(inventory, dict)
            and inventory.get("status") == "deployed"
            and inventory.get("ue4ss_required") is True
            and library.is_file()
        ):
            print(str(library))
            return 0
        return 4
    if command in {"enable", "disable"}:
        set_override(config.overrides_path, args.mod_id, command == "enable")
        _print_data({"mod": args.mod_id, "enabled": command == "enable"}, args.json)
        return 0
    if command == "quarantine":
        reason = None if args.clear else args.reason
        set_quarantine(config.quarantine_path, args.mod_id, reason)
        _print_data(
            {"mod": args.mod_id, "quarantined": not args.clear, "reason": reason},
            args.json,
        )
        return 0
    if command in {"backup", "backup-if-needed"}:
        result = validate(config)
        manager = BackupManager(config)
        if command == "backup-if-needed" and not manager.needs_backup(result.inventory_hash):
            _print_data(
                {"status": "unchanged", "inventory_hash": result.inventory_hash}, args.json
            )
            return 0
        path = manager.create(
            "explicit operator backup" if command == "backup" else "mod inventory changed",
            result.inventory_hash,
        )
        _print_data({"status": "backed-up", "backup": str(path)}, args.json)
        return 0
    if command == "rollback":
        manager = BackupManager(config)
        source, preserved = manager.rollback(args.backup, restore_saves=args.restore_saves)
        deployment = Deployer(config).deploy()
        _print_data(
            {
                "status": "rolled-back",
                "source_backup": str(source),
                "preserved_current_backup": str(preserved),
                "restore_saves": args.restore_saves,
                "deployment": deployment,
            },
            args.json,
        )
        return 0
    raise AssertionError(f"Unhandled command: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError) as exc:
        log.error(str(exc))
        return 3


if __name__ == "__main__":
    sys.exit(main())

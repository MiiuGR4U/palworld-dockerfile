"""Purely static validation for Patch, Blueprint, Lua, and native mods."""

from __future__ import annotations

import struct
from pathlib import Path

from .config import ModConfig
from .models import ModRecord, ScanResult
from .scanner import inventory_hash, scan


def _asset_groups(record: ModRecord) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for relative in record.files:
        path = Path(relative)
        suffix = path.suffix.lower()
        if suffix not in {".pak", ".utoc", ".ucas"}:
            continue
        key = path.with_suffix("").as_posix().lower()
        groups.setdefault(key, set()).add(suffix)
    return groups


def _validate_pak_groups(record: ModRecord) -> None:
    groups = _asset_groups(record)
    if not groups:
        record.errors.append("no .pak payload found")
        return

    for group, suffixes in groups.items():
        if ".pak" not in suffixes:
            record.errors.append(f"incomplete pak group {group}: .pak is missing")
        if suffixes & {".utoc", ".ucas"} and suffixes != {".pak", ".utoc", ".ucas"}:
            missing = sorted({".pak", ".utoc", ".ucas"} - suffixes)
            record.errors.append(
                f"incomplete pak trio {group}: missing {', '.join(missing)}"
            )


def inspect_elf_shared_object(path: Path) -> tuple[bool, str]:
    try:
        header = path.read_bytes()[:64]
    except OSError as exc:
        return False, f"cannot read native module: {exc}"

    if header.startswith(b"MZ"):
        return (
            False,
            "Windows DLL detected. Current backend: Linux x86_64 under FEX. "
            "Required: Linux x86_64 ELF .so.",
        )
    if len(header) < 20 or header[:4] != b"\x7fELF":
        return False, "native module is not an ELF binary"
    if header[4] != 2:
        return False, "native module is not ELF 64-bit"
    if header[5] not in {1, 2}:
        return False, "native module has an invalid ELF byte order"
    byte_order = "<" if header[5] == 1 else ">"
    elf_type, machine = struct.unpack(f"{byte_order}HH", header[16:20])
    if machine != 62:
        return False, f"native module machine is {machine}, expected x86-64 (62)"
    if elf_type != 3:
        return False, f"native module ELF type is {elf_type}, expected shared object (3)"
    return True, "Linux x86_64 ELF shared object"


def _validate_cpp(record: ModRecord) -> None:
    dlls = [relative for relative in record.files if Path(relative).suffix.lower() == ".dll"]
    for relative in dlls:
        record.errors.append(
            f"{relative}: Windows DLL detected. Current backend: Linux x86_64 under FEX. "
            "Required: Linux x86_64 ELF .so."
        )

    shared_objects = [
        relative for relative in record.files if Path(relative).suffix.lower() == ".so"
    ]
    if not shared_objects:
        record.errors.append("no Linux x86_64 .so payload found")
    for relative in shared_objects:
        valid, reason = inspect_elf_shared_object(record.source / relative)
        if not valid:
            record.errors.append(f"{relative}: {reason}")

    record.warnings.append(
        "Native mod code runs with the same permissions as the Palworld server."
    )


def _validate_record(record: ModRecord, config: ModConfig) -> None:
    if record.type == "unknown":
        return

    if not config.type_enabled(record.type):
        record.enabled = False
        record.warnings.append(f"{record.type} support is disabled by feature flag")

    if record.type != "cpp":
        cross_category_binaries = [
            relative
            for relative in record.files
            if Path(relative).suffix.lower() in {".dll", ".so"}
        ]
        for relative in cross_category_binaries:
            record.errors.append(
                f"native payload {relative} is not allowed in mods/{record.type}; "
                "Windows DLL is unsupported and Linux .so belongs in mods/cpp"
            )

    if record.type == "patch":
        _validate_pak_groups(record)
    elif record.type == "blueprint":
        _validate_pak_groups(record)
        record.warnings.append("Blueprint support is experimental and requires UE4SS/loader preflight.")
    elif record.type == "lua":
        if "scripts/main.lua" not in record.files:
            record.errors.append("Lua mod requires case-sensitive scripts/main.lua")
        record.warnings.append("Lua support through UE4SS Linux is experimental.")
    elif record.type == "cpp":
        _validate_cpp(record)

    if config.server_side_only:
        if record.client_required is True:
            record.errors.append("client_required=true is rejected by server-side-only mode")
        elif record.server_side is not True:
            message = "server-side compatibility is UNKNOWN; manifest does not assert server_side=true"
            if config.unknown_server_side_policy == "reject":
                record.errors.append(message)
            else:
                record.warnings.append(message)


def validate(config: ModConfig) -> ScanResult:
    records = scan(config)
    for record in records:
        _validate_record(record, config)

    by_id: dict[str, list[ModRecord]] = {}
    for record in records:
        by_id.setdefault(record.id, []).append(record)
    for mod_id, duplicates in by_id.items():
        if len(duplicates) > 1:
            for record in duplicates:
                record.errors.append(f"duplicate mod id: {mod_id}")

    active_ids = {record.id for record in records if record.enabled}
    for record in records:
        for conflict in record.conflicts:
            if conflict in active_ids:
                record.warnings.append(f"declared conflict is also enabled: {conflict}")
        for requirement in record.requires:
            if requirement != "ue4ss-linux" and requirement not in active_ids:
                record.errors.append(f"required mod is not enabled: {requirement}")

    records.sort(key=lambda item: (item.priority, item.id, item.type))
    return ScanResult(mods=records, inventory_hash=inventory_hash(records))

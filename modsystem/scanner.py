"""Static filesystem inventory. No mod code is imported or executed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import MOD_TYPES, ModConfig
from .manifests import load_manifest, slugify, validate_manifest
from .models import ModRecord, TYPE_STATUS
from .state import read_json


RESERVED_ROOTS = {
    *MOD_TYPES,
    "configs",
    "disabled",
    "quarantine",
    "manifests",
    "state",
    "cache",
    "backups",
}


def _static_file_inventory(source: Path) -> tuple[list[str], str, list[str]]:
    files: list[str] = []
    errors: list[str] = []
    digest = hashlib.sha256()

    for path in sorted(source.rglob("*"), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(source).as_posix()
        if path.is_symlink():
            errors.append(f"symbolic links are not allowed: {relative}")
            continue
        if not path.is_file():
            continue

        files.append(relative)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
        except OSError as exc:
            errors.append(f"cannot read {relative}: {exc}")
        digest.update(b"\0")

    return files, digest.hexdigest(), errors


def _record_from_directory(
    source: Path,
    category: str,
    overrides: dict[str, bool],
    quarantine: dict[str, str],
) -> ModRecord:
    manifest, errors = load_manifest(source / "mod.json")
    errors.extend(validate_manifest(manifest, category))

    raw_id = manifest.get("id") if isinstance(manifest.get("id"), str) else source.name
    mod_id = raw_id if isinstance(raw_id, str) else source.name
    if not mod_id or mod_id != slugify(mod_id):
        if "id" not in manifest:
            mod_id = slugify(source.name)

    files, digest, file_errors = _static_file_inventory(source)
    errors.extend(file_errors)
    enabled = manifest.get("enabled", True)
    if not isinstance(enabled, bool):
        enabled = False
    if mod_id in overrides:
        enabled = bool(overrides[mod_id])

    priority = manifest.get("priority", 100)
    if isinstance(priority, bool) or not isinstance(priority, int):
        priority = 100

    record = ModRecord(
        id=mod_id,
        name=str(manifest.get("name") or source.name),
        type=category,
        source=source,
        manifest=manifest,
        enabled=enabled,
        priority=priority,
        hash=digest,
        files=files,
        status=TYPE_STATUS[category],
        server_side=manifest.get("server_side")
        if isinstance(manifest.get("server_side"), bool)
        else None,
        client_required=manifest.get("client_required")
        if isinstance(manifest.get("client_required"), bool)
        else None,
        client_optional=manifest.get("client_optional")
        if isinstance(manifest.get("client_optional"), bool)
        else None,
        requires=list(manifest.get("requires", []))
        if isinstance(manifest.get("requires", []), list)
        else [],
        conflicts=list(manifest.get("conflicts", []))
        if isinstance(manifest.get("conflicts", []), list)
        else [],
        errors=errors,
    )
    if mod_id in quarantine:
        record.quarantined = True
        record.enabled = False
        record.warnings.append(f"logically quarantined: {quarantine[mod_id]}")
    return record


def scan(config: ModConfig) -> list[ModRecord]:
    overrides = read_json(config.overrides_path, {})
    quarantine = read_json(config.quarantine_path, {})
    if not isinstance(overrides, dict):
        raise ValueError("overrides.json must contain an object")
    if not isinstance(quarantine, dict):
        raise ValueError("quarantine.json must contain an object")

    records: list[ModRecord] = []
    for category in MOD_TYPES:
        category_root = config.mods_root / category
        if not category_root.exists():
            continue
        for source in sorted(category_root.iterdir(), key=lambda item: item.name.lower()):
            if source.is_symlink() or not source.is_dir():
                record = ModRecord(
                    id=f"unknown-{slugify(source.name)}",
                    name=source.name,
                    type="unknown",
                    source=source,
                    enabled=False,
                    status="UNKNOWN",
                )
                record.errors.append(
                    f"ambiguous entry in mods/{category}; place each mod in its own directory"
                )
                records.append(record)
                continue
            records.append(_record_from_directory(source, category, overrides, quarantine))

    if config.mods_root.exists():
        for source in sorted(config.mods_root.iterdir(), key=lambda item: item.name.lower()):
            if source.name in RESERVED_ROOTS:
                continue
            record = ModRecord(
                id=f"unknown-{slugify(source.name)}",
                name=source.name,
                type="unknown",
                source=source,
                enabled=False,
                status="UNKNOWN",
            )
            record.errors.append(
                "unknown mod input; move it explicitly into patch, blueprint, lua, or cpp"
            )
            records.append(record)

    return records


def inventory_hash(records: list[ModRecord]) -> str:
    canonical = [
        {
            "id": record.id,
            "type": record.type,
            "hash": record.hash,
            "enabled": record.enabled,
            "priority": record.priority,
            "quarantined": record.quarantined,
            "errors": record.errors,
        }
        for record in sorted(records, key=lambda item: (item.priority, item.id, item.type))
    ]
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

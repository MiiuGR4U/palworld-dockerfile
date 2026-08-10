"""Untrusted mod.json parsing and schema checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
VALID_TYPES = {"patch", "blueprint", "lua", "cpp"}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-._")
    return slug[:128] or "unknown"


def load_manifest(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, []
    if not path.is_file():
        return {}, ["mod.json is not a regular file"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"invalid manifest: {exc}"]
    if not isinstance(data, dict):
        return {}, ["invalid manifest: root must be an object"]
    return data, []


def validate_manifest(manifest: dict[str, Any], category: str) -> list[str]:
    errors: list[str] = []
    if not manifest:
        return errors

    manifest_id = manifest.get("id")
    if manifest_id is not None and (
        not isinstance(manifest_id, str) or not ID_PATTERN.fullmatch(manifest_id)
    ):
        errors.append("manifest id must match ^[a-z0-9][a-z0-9._-]{0,127}$")

    manifest_type = manifest.get("type")
    if manifest_type is not None:
        if manifest_type not in VALID_TYPES:
            errors.append(f"manifest type is invalid: {manifest_type!r}")
        elif manifest_type != category:
            errors.append(
                f"manifest type {manifest_type!r} does not match source category {category!r}"
            )

    for field in ("enabled", "server_side", "client_required", "client_optional"):
        if field in manifest and not isinstance(manifest[field], bool):
            errors.append(f"manifest field {field!r} must be boolean")

    if "priority" in manifest and (
        isinstance(manifest["priority"], bool) or not isinstance(manifest["priority"], int)
    ):
        errors.append("manifest priority must be an integer")

    for field in ("requires", "conflicts"):
        value = manifest.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"manifest field {field!r} must be an array of strings")

    if category == "cpp" and manifest.get("platform") not in {None, "linux-x86_64"}:
        errors.append("C++ manifest platform must be linux-x86_64")

    return errors

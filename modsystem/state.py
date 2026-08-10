"""Atomic JSON state operations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read state file {path}: {exc}") from exc


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp.chmod(0o644)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def set_override(path: Path, mod_id: str, enabled: bool) -> None:
    data = read_json(path, {})
    if not isinstance(data, dict):
        raise ValueError(f"Invalid overrides state in {path}")
    data[mod_id] = enabled
    atomic_write_json(path, data)


def set_quarantine(path: Path, mod_id: str, reason: str | None) -> None:
    data = read_json(path, {})
    if not isinstance(data, dict):
        raise ValueError(f"Invalid quarantine state in {path}")
    if reason is None:
        data.pop(mod_id, None)
    else:
        data[mod_id] = reason
    atomic_write_json(path, data)

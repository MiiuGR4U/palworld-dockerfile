"""Change-aware backups and explicit rollback."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import MOD_TYPES, ModConfig
from .state import atomic_write_json, read_json


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def _copy_tree_if_present(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, copy_function=shutil.copy2)
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        shutil.copy2(source, target)


def _safe_child(path: Path, parent: Path) -> Path:
    resolved_parent = parent.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError(f"Path escapes allowed root {resolved_parent}: {resolved_path}") from exc
    return resolved_path


class BackupManager:
    def __init__(self, config: ModConfig):
        self.config = config

    def previous_inventory_hash(self) -> str | None:
        inventory = read_json(self.config.inventory_path, {})
        if isinstance(inventory, dict):
            value = inventory.get("inventory_hash")
            return value if isinstance(value, str) else None
        return None

    def needs_backup(self, inventory_hash: str) -> bool:
        return inventory_hash != self.previous_inventory_hash()

    def create(
        self,
        reason: str,
        inventory_hash: str | None = None,
        protected: set[Path] | None = None,
    ) -> Path:
        destination = self.config.backup_root / _timestamp()
        destination.mkdir(parents=True, mode=0o755)

        _copy_tree_if_present(
            self.config.server_root / "Pal" / "Saved" / "SaveGames",
            destination / "Pal" / "Saved" / "SaveGames",
        )
        _copy_tree_if_present(
            self.config.server_root / "Pal" / "Saved" / "Config",
            destination / "Pal" / "Saved" / "Config",
        )
        _copy_tree_if_present(self.config.state_root, destination / "mods" / "state")
        for category in MOD_TYPES:
            _copy_tree_if_present(
                self.config.mods_root / category,
                destination / "mods" / "source" / category,
            )
        for name in ("configs", "manifests"):
            _copy_tree_if_present(
                self.config.mods_root / name,
                destination / "mods" / "source" / name,
            )

        atomic_write_json(
            destination / "backup.json",
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "inventory_hash": inventory_hash,
                "restore_saves_by_default": False,
            },
        )
        self.enforce_retention(protected=protected)
        return destination

    def enforce_retention(self, protected: set[Path] | None = None) -> None:
        protected_resolved = {path.resolve() for path in (protected or set())}
        backups = sorted(
            (path for path in self.config.backup_root.iterdir() if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        )
        retained = 0
        for old_backup in backups:
            if old_backup.resolve() in protected_resolved:
                continue
            retained += 1
            if retained <= self.config.backup_retention:
                continue
            _safe_child(old_backup, self.config.backup_root)
            shutil.rmtree(old_backup)

    def resolve_backup(self, value: str) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.config.backup_root / candidate
        candidate = _safe_child(candidate, self.config.backup_root)
        if not (candidate / "backup.json").is_file():
            raise ValueError(f"Not a palmodctl backup: {candidate}")
        return candidate

    def rollback(self, value: str, restore_saves: bool = False) -> tuple[Path, Path]:
        source = self.resolve_backup(value)
        preserved = self.create(
            "pre-rollback preservation",
            protected={source.resolve()},
        )

        source_root = source / "mods" / "source"
        for name in (*MOD_TYPES, "configs", "manifests"):
            current = _safe_child(self.config.mods_root / name, self.config.mods_root)
            restored = source_root / name
            if current.exists():
                shutil.rmtree(current)
            if restored.is_dir():
                shutil.copytree(restored, current, copy_function=shutil.copy2)
            else:
                current.mkdir(parents=True, exist_ok=True, mode=0o755)

        current_state = _safe_child(self.config.state_root, self.config.mods_root)
        restored_state = source / "mods" / "state"
        if current_state.exists():
            shutil.rmtree(current_state)
        if restored_state.is_dir():
            shutil.copytree(restored_state, current_state, copy_function=shutil.copy2)
        else:
            current_state.mkdir(parents=True, exist_ok=True, mode=0o755)

        if restore_saves:
            for relative in (
                Path("Pal/Saved/SaveGames"),
                Path("Pal/Saved/Config"),
            ):
                restored = source / relative
                current = _safe_child(self.config.server_root / relative, self.config.server_root)
                if current.exists():
                    shutil.rmtree(current)
                if restored.is_dir():
                    shutil.copytree(restored, current, copy_function=shutil.copy2)

        operation = {
            "source_backup": str(source),
            "preserved_current_backup": str(preserved),
            "restore_saves": restore_saves,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(self.config.state_root / "last-rollback.json", operation)
        return source, preserved

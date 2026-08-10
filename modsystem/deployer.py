"""Transactional deployment of validated mod payloads."""

from __future__ import annotations

import os
import re
import shutil
import uuid
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import logging as log
from .backup import BackupManager
from .config import ModConfig
from .models import ModRecord, ScanResult
from .scanner import inventory_hash
from .state import atomic_write_json, read_json, set_quarantine
from .ue4ss import inspect_bundle
from .validators import validate


MANAGED_BLOCK_START = "; palmodctl managed entries - begin"
MANAGED_BLOCK_END = "; palmodctl managed entries - end"


@dataclass(frozen=True)
class DeploymentFile:
    target: Path
    source: Path | None = None
    content: bytes | None = None
    managed_block: bool = False


def _safe_target(
    target: Path,
    allowed_roots: list[Path],
    allowed_files: set[Path] | None = None,
) -> Path:
    if target.is_symlink():
        raise ValueError(f"Refusing to replace symbolic link: {target}")
    if target.absolute() in {path.absolute() for path in (allowed_files or set())}:
        return target
    resolved_parent = target.parent.resolve()
    for allowed_root in allowed_roots:
        try:
            resolved_parent.relative_to(allowed_root.resolve())
            return target
        except ValueError:
            continue
    raise ValueError(f"Deployment target escapes managed roots: {target}")


def _strip_managed_block(text: str) -> str:
    pattern = re.compile(
        rf"(?:^|\n){re.escape(MANAGED_BLOCK_START)}\n.*?\n{re.escape(MANAGED_BLOCK_END)}(?:\n|$)",
        re.DOTALL,
    )
    return pattern.sub("\n", text).strip("\n")


def _mods_txt_content(path: Path, mod_ids: list[str]) -> bytes:
    existing = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    unmanaged = _strip_managed_block(existing)
    managed_lines = [MANAGED_BLOCK_START, *(f"{mod_id} : 1" for mod_id in mod_ids), MANAGED_BLOCK_END]
    sections = [section for section in (unmanaged, "\n".join(managed_lines)) if section]
    return ("\n".join(sections) + "\n").encode("utf-8")


def _managed_roots(config: ModConfig) -> list[Path]:
    return [
        config.server_root / "Pal" / "Content" / "Paks" / "~mods",
        config.server_root / "Pal" / "Content" / "Paks" / "LogicMods",
        config.ue4ss_mods_root,
    ]


def _managed_core_files(config: ModConfig) -> set[Path]:
    return {
        config.ue4ss_deploy_root / "libUE4SS.so",
        config.ue4ss_deploy_root / "UE4SS-settings.ini",
        config.ue4ss_deploy_root / "MemberVariableLayout.ini",
    }


def _payload_files(record: ModRecord, suffixes: set[str] | None = None) -> list[Path]:
    payloads: list[Path] = []
    for relative in record.files:
        if relative == "mod.json":
            continue
        source = record.source / relative
        if suffixes is not None and source.suffix.lower() not in suffixes:
            continue
        payloads.append(source)
    return payloads


def build_plan(config: ModConfig, result: ScanResult) -> tuple[list[DeploymentFile], bool]:
    plan: list[DeploymentFile] = []
    ue4ss_mod_entries: list[str] = []
    blueprint_names: list[str] = []
    ordered = [mod for mod in result.mods if mod.deployable]

    for order, record in enumerate(ordered, start=1):
        prefix = f"palmodctl-{order:04d}-{record.id}"
        if record.type == "patch":
            target_root = config.server_root / "Pal" / "Content" / "Paks" / "~mods"
            for source in _payload_files(record, {".pak", ".utoc", ".ucas"}):
                plan.append(
                    DeploymentFile(target=target_root / f"{prefix}-{source.name}", source=source)
                )
        elif record.type == "blueprint":
            target_root = (
                config.server_root / "Pal" / "Content" / "Paks" / "LogicMods" / record.id
            )
            for source in _payload_files(record, {".pak", ".utoc", ".ucas"}):
                plan.append(DeploymentFile(target=target_root / source.name, source=source))
                if source.suffix.lower() == ".pak":
                    blueprint_names.append(source.stem)
        elif record.type == "lua":
            target_root = config.ue4ss_mods_root / record.id
            for source in _payload_files(record):
                relative = source.relative_to(record.source)
                if relative.parts and relative.parts[0] == "scripts":
                    relative = Path("Scripts", *relative.parts[1:])
                plan.append(DeploymentFile(target=target_root / relative, source=source))
            ue4ss_mod_entries.append(record.id)
        elif record.type == "cpp":
            target_root = config.ue4ss_mods_root / record.id / "libs"
            for source in _payload_files(record, {".so"}):
                plan.append(DeploymentFile(target=target_root / source.name, source=source))
            ue4ss_mod_entries.append(record.id)

    ue4ss_required = bool(ue4ss_mod_entries or blueprint_names or config.ue4ss_test_mode)
    if ue4ss_required:
        for filename in ("libUE4SS.so", "UE4SS-settings.ini", "MemberVariableLayout.ini"):
            plan.append(
                DeploymentFile(
                    target=config.ue4ss_deploy_root / filename,
                    source=config.ue4ss_bundle_root / filename,
                )
            )

        shared_source = config.ue4ss_bundle_root / "Mods" / "shared"
        if shared_source.is_dir():
            for source in sorted(path for path in shared_source.rglob("*") if path.is_file()):
                plan.append(
                    DeploymentFile(
                        target=config.ue4ss_mods_root / "shared" / source.relative_to(shared_source),
                        source=source,
                    )
                )

    if blueprint_names:
        for builtin in ("BPML_GenericFunctions", "BPModLoaderMod"):
            builtin_source = config.ue4ss_bundle_root / "Mods" / builtin
            if not builtin_source.is_dir():
                raise ValueError(f"Blueprint loader component is missing: {builtin_source}")
            for source in sorted(path for path in builtin_source.rglob("*") if path.is_file()):
                relative = source.relative_to(builtin_source)
                if builtin == "BPModLoaderMod" and relative.as_posix() == "load_order.txt":
                    continue
                plan.append(
                    DeploymentFile(
                        target=config.ue4ss_mods_root / builtin / relative,
                        source=source,
                    )
                )
        plan.append(
            DeploymentFile(
                target=config.ue4ss_mods_root / "BPModLoaderMod" / "load_order.txt",
                content=("\n".join(blueprint_names) + "\n").encode("utf-8"),
            )
        )
        ue4ss_mod_entries[0:0] = ["BPML_GenericFunctions", "BPModLoaderMod"]

    if ue4ss_mod_entries:
        mods_txt = config.ue4ss_mods_root / "mods.txt"
        plan.append(
            DeploymentFile(
                target=mods_txt,
                content=_mods_txt_content(mods_txt, ue4ss_mod_entries),
                managed_block=True,
            )
        )

    seen: set[Path] = set()
    allowed_roots = _managed_roots(config)
    allowed_files = _managed_core_files(config)
    for item in plan:
        _safe_target(item.target, allowed_roots, allowed_files)
        if item.target in seen:
            raise ValueError(f"Deployment collision: {item.target}")
        seen.add(item.target)
    return plan, ue4ss_required


class Deployer:
    def __init__(self, config: ModConfig):
        self.config = config
        self.backups = BackupManager(config)

    def _previous_inventory(self) -> dict:
        data = read_json(self.config.inventory_path, {})
        return data if isinstance(data, dict) else {}

    def _inventory_document(
        self,
        result: ScanResult,
        files: list[Path],
        ue4ss_required: bool,
        status: str,
        managed_text: list[Path] | None = None,
    ) -> dict:
        return {
            "schema": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "inventory_hash": result.inventory_hash,
            "status": status,
            "ue4ss_required": ue4ss_required,
            "mods": [mod.to_dict() for mod in result.mods],
            "deployment": {
                "files": [str(path) for path in files],
                "managed_text": [str(path) for path in (managed_text or [])],
            },
        }

    def _remove_managed_text(self, path: Path) -> None:
        _safe_target(path, _managed_roots(self.config), _managed_core_files(self.config))
        if not path.is_file():
            return
        current = path.read_text(encoding="utf-8", errors="replace")
        cleaned = _strip_managed_block(current)
        if cleaned:
            temp = path.with_name(f".{path.name}.clean.{os.getpid()}")
            temp.write_text(cleaned + "\n", encoding="utf-8", newline="\n")
            temp.chmod(0o644)
            os.replace(temp, path)
        else:
            path.unlink()

    def clean(self, status: str = "clean") -> list[Path]:
        previous = self._previous_inventory()
        deployment = previous.get("deployment", {}) if isinstance(previous, dict) else {}
        paths = deployment.get("files", []) if isinstance(deployment, dict) else []
        managed_text = deployment.get("managed_text", []) if isinstance(deployment, dict) else []
        removed: list[Path] = []

        for raw_path in paths:
            path = Path(raw_path)
            _safe_target(path, _managed_roots(self.config), _managed_core_files(self.config))
            if path.is_file() and not path.is_symlink():
                path.unlink()
                removed.append(path)
        for raw_path in managed_text:
            self._remove_managed_text(Path(raw_path))

        if previous:
            previous["status"] = status
            previous["updated_at"] = datetime.now(timezone.utc).isoformat()
            previous["deployment"] = {"files": [], "managed_text": []}
            atomic_write_json(self.config.inventory_path, previous)
        return removed

    def _quarantine_invalid(self, result: ScanResult) -> None:
        for record in result.mods:
            if record.errors:
                set_quarantine(
                    self.config.quarantine_path,
                    record.id,
                    "; ".join(record.errors),
                )

    def _effective_inventory_hash(self, result: ScanResult) -> str:
        payload = {
            "source_inventory_hash": result.inventory_hash,
            "ue4ss_test_mode": self.config.ue4ss_test_mode,
            "strict_version_check": self.config.strict_version_check,
            "server_side_only": self.config.server_side_only,
            "unknown_server_side_policy": self.config.unknown_server_side_policy,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _transaction(
        self,
        plan: list[DeploymentFile],
        previous_paths: list[Path],
        write_state: Callable[[], None],
    ) -> list[Path]:
        transaction_id = uuid.uuid4().hex
        staging = self.config.state_root / "staging" / transaction_id
        payload_root = staging / "payload"
        rollback_root = staging / "rollback"
        payload_root.mkdir(parents=True, mode=0o755)
        rollback_root.mkdir(parents=True, mode=0o755)
        allowed = _managed_roots(self.config)
        allowed_files = _managed_core_files(self.config)
        committed: list[Path] = []
        backed_up: dict[Path, Path] = {}

        try:
            for index, item in enumerate(plan):
                staged = payload_root / f"{index:06d}"
                if item.source is not None:
                    shutil.copy2(item.source, staged)
                elif item.content is not None:
                    staged.write_bytes(item.content)
                else:
                    raise ValueError(f"Deployment item has no payload: {item.target}")
                staged.chmod(0o644)

            all_targets = {item.target for item in plan} | set(previous_paths)
            for index, target in enumerate(sorted(all_targets, key=str)):
                _safe_target(target, allowed, allowed_files)
                if target.is_file() and not target.is_symlink():
                    backup = rollback_root / f"{index:06d}"
                    shutil.copy2(target, backup)
                    backed_up[target] = backup

            for index, item in enumerate(plan):
                item.target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                temporary = item.target.with_name(f".{item.target.name}.tmp.{transaction_id}")
                shutil.copy2(payload_root / f"{index:06d}", temporary)
                temporary.chmod(0o644)
                os.replace(temporary, item.target)
                committed.append(item.target)

            new_paths = {item.target for item in plan}
            for obsolete in set(previous_paths) - new_paths:
                _safe_target(obsolete, allowed, allowed_files)
                if obsolete.is_file() and not obsolete.is_symlink():
                    obsolete.unlink()

            # State is part of the same rollback boundary as deployed files.
            write_state()

            return committed
        except Exception:
            for target in committed:
                if target in backed_up:
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    shutil.copy2(backed_up[target], target)
                elif target.exists() and not target.is_symlink():
                    target.unlink()
            for target, backup in backed_up.items():
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    shutil.copy2(backup, target)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def deploy(self) -> dict:
        self.config.initialize_directories()
        if self.config.safe_mode:
            log.warn("MOD SAFE MODE ACTIVE")
            log.warn("All mod deployment disabled. Files preserved.")
            removed = self.clean(status="safe-mode")
            return {"status": "safe-mode", "removed": [str(path) for path in removed]}
        if not self.config.enabled:
            removed = self.clean(status="mods-disabled")
            return {"status": "mods-disabled", "removed": [str(path) for path in removed]}

        result = validate(self.config)
        result.inventory_hash = self._effective_inventory_hash(result)
        self._quarantine_invalid(result)
        if result.errors and self.config.fail_on_error:
            raise ValueError("Mod validation failed: " + " | ".join(result.errors))
        for message in result.errors:
            log.warn(f"Skipped invalid mod: {message}")
        for message in result.warnings:
            log.warn(message)

        if result.ue4ss_required or self.config.ue4ss_test_mode:
            ue4ss = inspect_bundle(self.config)
            for warning in ue4ss.warnings:
                log.warn(f"UE4SS: {warning}")
            if not ue4ss.available:
                message = "UE4SS preflight failed: " + " | ".join(ue4ss.errors)
                if self.config.fail_on_error:
                    raise ValueError(message)
                log.warn(message)
                for mod in result.mods:
                    if mod.type in {"blueprint", "lua", "cpp"}:
                        mod.enabled = False
                result.inventory_hash = inventory_hash(result.mods)
                result.inventory_hash = self._effective_inventory_hash(result)

        previous = self._previous_inventory()
        previous_deployment = previous.get("deployment", {}) if isinstance(previous, dict) else {}
        previous_paths = [
            Path(path)
            for path in previous_deployment.get("files", [])
            if isinstance(path, str)
        ] if isinstance(previous_deployment, dict) else []

        plan, ue4ss_required = build_plan(self.config, result)
        if (
            previous.get("inventory_hash") == result.inventory_hash
            and previous.get("status") == "deployed"
        ):
            return {"status": "unchanged", "inventory_hash": result.inventory_hash}

        backup_path: Path | None = None
        if self.config.backup_on_change and self.backups.needs_backup(result.inventory_hash):
            backup_path = self.backups.create("mod inventory changed", result.inventory_hash)
            log.ok(f"Backup created: {backup_path}")

        managed_text = [item.target for item in plan if item.managed_block]
        copied_files = [item.target for item in plan if not item.managed_block]
        inventory = self._inventory_document(
            result,
            copied_files,
            ue4ss_required,
            "deployed",
            managed_text,
        )
        committed = self._transaction(
            plan,
            previous_paths,
            lambda: atomic_write_json(self.config.inventory_path, inventory),
        )
        for order, mod in enumerate((m for m in result.mods if m.deployable), start=1):
            log.info(f"Load order {order:04d}: priority={mod.priority} id={mod.id} type={mod.type}")
        return {
            "status": "deployed",
            "inventory_hash": result.inventory_hash,
            "files": [str(path) for path in committed],
            "backup": str(backup_path) if backup_path else None,
            "ue4ss_required": ue4ss_required,
        }

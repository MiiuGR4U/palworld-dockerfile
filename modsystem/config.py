"""Configuration and persistent path policy for palmodctl."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


MOD_TYPES = ("patch", "blueprint", "lua", "cpp")


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"true", "1", "yes", "on"}


def env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


@dataclass(frozen=True)
class ModConfig:
    server_root: Path
    mods_root: Path
    backup_root: Path
    ue4ss_bundle_root: Path
    ue4ss_deploy_root: Path
    enabled: bool = False
    safe_mode: bool = False
    server_side_only: bool = True
    backup_on_change: bool = True
    fail_on_error: bool = True
    debug: bool = False
    enable_patch: bool = True
    enable_blueprint: bool = False
    enable_lua: bool = False
    enable_cpp: bool = False
    unknown_server_side_policy: str = "warn"
    backup_retention: int = 10
    strict_version_check: bool = False
    ue4ss_test_mode: bool = False

    @classmethod
    def from_env(cls, server_root: Path | None = None) -> "ModConfig":
        root = (server_root or Path(os.getenv("SERVER_DIR", "/home/container"))).resolve()
        mods_root = Path(os.getenv("MODS_ROOT", str(root / "mods"))).resolve()
        backup_root = Path(
            os.getenv("MODS_BACKUP_ROOT", str(root / "backups" / "mod-changes"))
        ).resolve()
        ue4ss_bundle_root = Path(
            os.getenv("PALMOD_UE4SS_BUNDLE", "/opt/palworld-mod-runtime/ue4ss/current")
        ).resolve()
        ue4ss_deploy_root = Path(
            os.getenv(
                "PALMOD_UE4SS_DEPLOY_ROOT",
                str(root),
            )
        ).resolve()
        policy = os.getenv("MODS_UNKNOWN_SERVER_SIDE_POLICY", "warn").strip().lower()
        if policy not in {"warn", "reject"}:
            raise ValueError("MODS_UNKNOWN_SERVER_SIDE_POLICY must be warn or reject")

        return cls(
            server_root=root,
            mods_root=mods_root,
            backup_root=backup_root,
            ue4ss_bundle_root=ue4ss_bundle_root,
            ue4ss_deploy_root=ue4ss_deploy_root,
            enabled=env_bool("MODS_ENABLED", False),
            safe_mode=env_bool("MODS_SAFE_MODE", False),
            server_side_only=env_bool("MODS_SERVER_SIDE_ONLY", True),
            backup_on_change=env_bool("MODS_BACKUP_ON_CHANGE", True),
            fail_on_error=env_bool("MODS_FAIL_ON_ERROR", True),
            debug=env_bool("MODS_DEBUG", False),
            enable_patch=env_bool("ENABLE_PATCH_MODS", True),
            enable_blueprint=env_bool("ENABLE_BLUEPRINT_MODS", False),
            enable_lua=env_bool("ENABLE_LUA_MODS", False),
            enable_cpp=env_bool("ENABLE_CPP_MODS", False),
            unknown_server_side_policy=policy,
            backup_retention=env_int("MODS_BACKUP_RETENTION", 10, minimum=1),
            strict_version_check=env_bool("MODS_STRICT_VERSION_CHECK", False),
            ue4ss_test_mode=env_bool("MODS_UE4SS_TEST_MODE", False),
        )

    @classmethod
    def for_test(cls, server_root: Path, **overrides) -> "ModConfig":
        root = server_root.resolve()
        values = {
            "server_root": root,
            "mods_root": root / "mods",
            "backup_root": root / "backups" / "mod-changes",
            "ue4ss_bundle_root": root / "runtime" / "ue4ss" / "current",
            # Keep the test target distinct from lowercase mods/ on case-insensitive hosts.
            "ue4ss_deploy_root": root / "ue4ss-deploy",
        }
        values.update(overrides)
        return cls(**values)

    @property
    def state_root(self) -> Path:
        return self.mods_root / "state"

    @property
    def inventory_path(self) -> Path:
        return self.state_root / "inventory.json"

    @property
    def overrides_path(self) -> Path:
        return self.state_root / "overrides.json"

    @property
    def quarantine_path(self) -> Path:
        return self.state_root / "quarantine.json"

    @property
    def ue4ss_mods_root(self) -> Path:
        return self.ue4ss_deploy_root / "Mods"

    def type_enabled(self, mod_type: str) -> bool:
        return {
            "patch": self.enable_patch,
            "blueprint": self.enable_blueprint,
            "lua": self.enable_lua,
            "cpp": self.enable_cpp,
        }.get(mod_type, False)

    def initialize_directories(self) -> None:
        for mod_type in MOD_TYPES:
            (self.mods_root / mod_type).mkdir(parents=True, exist_ok=True, mode=0o755)
        for name in (
            "configs",
            "disabled",
            "quarantine",
            "manifests",
            "state",
            "cache",
            "backups",
        ):
            (self.mods_root / name).mkdir(parents=True, exist_ok=True, mode=0o755)
        self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o755)

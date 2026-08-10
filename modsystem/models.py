"""Serializable scan and validation records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TYPE_STATUS = {
    "patch": "SUPPORTED",
    "blueprint": "EXPERIMENTAL",
    "lua": "EXPERIMENTAL",
    "cpp": "EXPERIMENTAL",
    "unknown": "UNKNOWN",
}


@dataclass
class ModRecord:
    id: str
    name: str
    type: str
    source: Path
    manifest: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 100
    hash: str = ""
    files: list[str] = field(default_factory=list)
    status: str = "UNKNOWN"
    server_side: bool | None = None
    client_required: bool | None = None
    client_optional: bool | None = None
    requires: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quarantined: bool = False

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def deployable(self) -> bool:
        return self.valid and self.enabled and not self.quarantined

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "source": str(self.source),
            "enabled": self.enabled,
            "priority": self.priority,
            "hash": self.hash,
            "files": self.files,
            "status": self.status,
            "server_side": self.server_side,
            "client_required": self.client_required,
            "client_optional": self.client_optional,
            "requires": self.requires,
            "conflicts": self.conflicts,
            "valid": self.valid,
            "quarantined": self.quarantined,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class ScanResult:
    mods: list[ModRecord]
    inventory_hash: str

    @property
    def errors(self) -> list[str]:
        return [f"{mod.id}: {error}" for mod in self.mods for error in mod.errors]

    @property
    def warnings(self) -> list[str]:
        return [f"{mod.id}: {warning}" for mod in self.mods for warning in mod.warnings]

    @property
    def ue4ss_required(self) -> bool:
        return any(
            mod.deployable and mod.type in {"blueprint", "lua", "cpp"} for mod in self.mods
        )

    def counts(self) -> dict[str, int]:
        counts = {key: 0 for key in ("patch", "blueprint", "lua", "cpp", "unknown")}
        for mod in self.mods:
            counts[mod.type if mod.type in counts else "unknown"] += 1
        counts["rejected"] = sum(1 for mod in self.mods if not mod.valid)
        counts["disabled"] = sum(1 for mod in self.mods if not mod.enabled)
        counts["quarantined"] = sum(1 for mod in self.mods if mod.quarantined)
        return counts

"""Static UE4SS Linux bundle preflight."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .config import ModConfig
from .state import read_json
from .validators import inspect_elf_shared_object


@dataclass
class Ue4ssStatus:
    available: bool
    library: Path | None
    version: str | None
    errors: list[str]
    warnings: list[str]
    tested_palworld_build_id: str | None = None
    current_palworld_build_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "library": str(self.library) if self.library else None,
            "version": self.version,
            "errors": self.errors,
            "warnings": self.warnings,
            "tested_palworld_build_id": self.tested_palworld_build_id,
            "current_palworld_build_id": self.current_palworld_build_id,
        }


def inspect_bundle(config: ModConfig) -> Ue4ssStatus:
    root = config.ue4ss_bundle_root
    library = root / "libUE4SS.so"
    metadata_path = root / "version.json"
    errors: list[str] = []
    warnings: list[str] = []
    version: str | None = None
    tested_build: str | None = None
    current_build: str | None = None

    if not root.is_dir():
        errors.append(f"UE4SS bundle directory is missing: {root}")
    if not library.is_file():
        errors.append(f"libUE4SS.so is missing: {library}")
    else:
        valid, reason = inspect_elf_shared_object(library)
        if not valid:
            errors.append(f"libUE4SS.so preflight failed: {reason}")

    for required_file in ("UE4SS-settings.ini", "MemberVariableLayout.ini"):
        if not (root / required_file).is_file():
            errors.append(f"UE4SS bundle file is missing: {root / required_file}")

    if not metadata_path.is_file():
        errors.append(f"UE4SS version metadata is missing: {metadata_path}")
    else:
        metadata = read_json(metadata_path, {})
        if not isinstance(metadata, dict):
            errors.append("UE4SS version metadata must be a JSON object")
        else:
            version_value = metadata.get("ue4ss_linux")
            if isinstance(version_value, str) and version_value.strip():
                version = version_value.strip()
            else:
                errors.append("version.json does not contain ue4ss_linux")
            if metadata.get("backend") != "linux-fex":
                errors.append("version.json backend must be linux-fex")
            tested_value = metadata.get("last_tested_palworld_build_id")
            if isinstance(tested_value, str) and tested_value.strip():
                tested_build = tested_value.strip()
            else:
                warnings.append("last_tested_palworld_build_id is not recorded")

    manifest = config.server_root / "steamapps" / "appmanifest_2394010.acf"
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'"buildid"\s+"([0-9]+)"', text, re.IGNORECASE)
        if match:
            current_build = match.group(1)
    if current_build and tested_build and tested_build != "unknown" and current_build != tested_build:
        message = (
            f"Palworld build {current_build} differs from loader-tested build {tested_build}"
        )
        if config.strict_version_check:
            errors.append(message)
        else:
            warnings.append(message)
    elif config.strict_version_check and (not current_build or not tested_build or tested_build == "unknown"):
        errors.append(
            "strict version check cannot prove the current Palworld build against loader metadata"
        )

    return Ue4ssStatus(
        available=not errors,
        library=library if library.is_file() else None,
        version=version,
        errors=errors,
        warnings=warnings,
        tested_palworld_build_id=tested_build,
        current_palworld_build_id=current_build,
    )

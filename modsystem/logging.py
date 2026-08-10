"""Small redaction-safe console logger."""

from __future__ import annotations

import os


def _debug_enabled() -> bool:
    return os.getenv("MODS_DEBUG", "false").strip().lower() == "true"


def info(message: str) -> None:
    print(f"[palmodctl] {message}", flush=True)


def ok(message: str) -> None:
    print(f"[palmodctl] [OK] {message}", flush=True)


def warn(message: str) -> None:
    print(f"[palmodctl] [WARN] {message}", flush=True)


def error(message: str) -> None:
    print(f"[palmodctl] [ERROR] {message}", flush=True)


def debug(message: str) -> None:
    if _debug_enabled():
        print(f"[palmodctl] [DEBUG] {message}", flush=True)

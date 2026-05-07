from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_path(relative_path: str | Path) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        return relative
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = Path(meipass).resolve() / relative
            if bundled.exists():
                return bundled
    return app_root() / relative


def writable_path(relative_path: str | Path) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        return relative
    return app_root() / relative

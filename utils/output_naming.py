from __future__ import annotations

from pathlib import Path


def unique_output_path(source_path: str | Path, output_dir: str | Path | None = None, suffix: str = "", extension: str = ".mp4") -> Path:
    source = Path(source_path)
    folder = Path(output_dir) if output_dir is not None else source.parent / "output"
    folder.mkdir(parents=True, exist_ok=True)
    ext = extension if extension.startswith(".") else f".{extension}"
    base = f"{source.stem}{suffix}"
    candidate = folder / f"{base}{ext}"
    if not candidate.exists():
        return candidate
    index = 1
    while True:
        candidate = folder / f"{base}_{index:03d}{ext}"
        if not candidate.exists():
            return candidate
        index += 1

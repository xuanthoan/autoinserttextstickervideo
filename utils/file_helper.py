from __future__ import annotations

from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def is_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def videos_in_folder(path: str | Path) -> list[str]:
    folder = Path(path)
    return [str(item) for item in sorted(folder.iterdir()) if item.is_file() and is_video(item)]


def output_path_for_video(path: str | Path) -> Path:
    source = Path(path)
    return source.parent / "output" / f"{source.stem}_output.mp4"

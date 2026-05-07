from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

from utils.paths import app_root


def _binary_names(name: str) -> list[str]:
    """Return executable names to try on every platform.

    Users often drop the Windows `ffmpeg.exe`/`ffprobe.exe` files next to
    `main.py`; trying both forms also keeps source-tree smoke tests portable.
    """
    names = [name]
    if not name.lower().endswith(".exe"):
        names.insert(0, f"{name}.exe")
    return names


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass).resolve())
    roots.append(app_root())
    roots.append(Path.cwd().resolve())

    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def _candidate_paths(name: str) -> list[Path]:
    candidates: list[Path] = []
    for root in _candidate_roots():
        for binary_name in _binary_names(name):
            candidates.append(root / binary_name)
            candidates.append(root / "bin" / binary_name)
    return candidates


def bundled_binary(name: str, require: bool = False) -> str:
    for candidate in _candidate_paths(name):
        if candidate.exists():
            return str(candidate)

    for binary_name in _binary_names(name):
        found = shutil.which(binary_name)
        if found:
            return found

    if require:
        searched = "\n".join(f"- {path}" for path in _candidate_paths(name))
        raise FileNotFoundError(
            f"Cannot find {name}. Put {name}.exe next to main.py, in bin/, or on PATH.\nSearched:\n{searched}"
        )

    fallback = app_root() / "bin" / _binary_names(name)[0]
    return str(fallback)


def ffmpeg_path(require: bool = False) -> str:
    return bundled_binary("ffmpeg", require=require)


def ffprobe_path(require: bool = False) -> str:
    return bundled_binary("ffprobe", require=require)


def probe_video(path: str) -> dict[str, float | int]:
    command = [
        ffprobe_path(require=True),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    stream = payload.get("streams", [{}])[0]
    duration = stream.get("duration") or payload.get("format", {}).get("duration") or 0
    return {"width": int(stream.get("width", 0)), "height": int(stream.get("height", 0)), "duration": float(duration)}


def extract_preview_frame(video_path: str, seek_seconds: float = 0.05) -> Path:
    target = Path(tempfile.gettempdir()) / f"autoinsert_preview_{abs(hash((video_path, seek_seconds)))}.jpg"
    command = [
        ffmpeg_path(require=True),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-ss",
        f"{seek_seconds:.2f}",
        "-fflags",
        "+genpts",
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-fps_mode",
        "vfr",
        str(target),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
    return target

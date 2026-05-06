from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def bundled_binary(name: str, require: bool = False) -> str:
    exe = f"{name}.exe" if sys.platform.startswith("win") else name
    local = Path(__file__).resolve().parents[1] / "bin" / exe
    if local.exists():
        return str(local)
    found = shutil.which(exe) or shutil.which(name)
    if found:
        return found
    if require:
        raise FileNotFoundError(f"Cannot find {name}. Put it in bin/ or on PATH.")
    return str(local)


def ffmpeg_path() -> str:
    return bundled_binary("ffmpeg")


def ffprobe_path() -> str:
    return bundled_binary("ffprobe", require=True)


def probe_video(path: str) -> dict[str, float | int]:
    command = [
        ffprobe_path(),
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

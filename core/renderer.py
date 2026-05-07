from __future__ import annotations

import logging
import subprocess
import tempfile
from collections.abc import Callable

from core.ffmpeg_builder import FFmpegCommand, build_ffmpeg_command
from core.project_model import Project

LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]
LogCallback = Callable[[str], None]
CancelCallback = Callable[[], bool]


def _format_return_code(code: int) -> str:
    return f"{code} ({code - 2**32})" if code > 2**31 - 1 else str(code)


def _startup_info() -> tuple[int, subprocess.STARTUPINFO | None]:
    if not hasattr(subprocess, "STARTUPINFO"):
        return 0, None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return creationflags, startupinfo


def _parse_progress(line: str, duration: float) -> float | None:
    if duration <= 0:
        return None
    if line.startswith("out_time_ms="):
        try:
            return min(100.0, max(0.0, int(line.partition("=")[2]) / 1_000_000 / duration * 100))
        except ValueError:
            return None
    if line.startswith("out_time="):
        value = line.partition("=")[2]
        try:
            hours, minutes, seconds = value.split(":")
            elapsed = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except ValueError:
            return None
        return min(100.0, max(0.0, elapsed / duration * 100))
    return None


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def render_project(
    project: Project,
    output_path: str,
    on_log: LogCallback | None = None,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> FFmpegCommand:
    text_assets = tempfile.TemporaryDirectory(prefix="autoinsert_text_")
    command = build_ffmpeg_command(project, output_path, require_binaries=True, text_asset_dir=text_assets.name)
    LOGGER.info("Running FFmpeg: %s", command.shell_string())
    if on_log:
        on_log("Running FFmpeg render...")
    creationflags, startupinfo = _startup_info()
    process = subprocess.Popen(
        command.args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )
    assert process.stdout is not None
    last_percent = -1.0
    try:
        for raw_line in process.stdout:
            if should_cancel and should_cancel():
                _terminate_process(process)
                raise RuntimeError("Render cancelled")
            line = raw_line.strip()
            if not line:
                continue
            percent = _parse_progress(line, project.duration)
            if percent is not None:
                if on_progress:
                    on_progress(percent)
                if on_log and (percent >= last_percent + 5 or percent >= 99.9):
                    on_log(f"FFmpeg progress: {percent:.1f}%")
                    last_percent = percent
                continue
            if line.startswith(("frame=", "fps=", "stream_", "total_size=", "out_time_", "dup_frames=", "drop_frames=", "speed=", "progress=")):
                continue
            LOGGER.info(line)
            if on_log:
                on_log(line)
        code = process.wait()
    except Exception:
        _terminate_process(process)
        text_assets.cleanup()
        raise
    if code != 0:
        text_assets.cleanup()
        raise RuntimeError(f"FFmpeg failed with exit code {_format_return_code(code)}")
    if on_progress:
        on_progress(100.0)
    if on_log:
        on_log("FFmpeg render finished.")
    text_assets.cleanup()
    return command

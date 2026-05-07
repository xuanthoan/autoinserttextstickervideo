from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

from core.ffmpeg_builder import FFmpegCommand, build_ffmpeg_command
from core.project_model import Project

LOGGER = logging.getLogger(__name__)


def _format_return_code(code: int) -> str:
    return f"{code} ({code - 2**32})" if code > 2**31 - 1 else str(code)


def render_project(project: Project, output_path: str, on_log: Callable[[str], None] | None = None) -> FFmpegCommand:
    command = build_ffmpeg_command(project, output_path, require_binaries=True)
    LOGGER.info("Running FFmpeg: %s", command.shell_string())
    process = subprocess.Popen(command.args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip()
        LOGGER.info(line)
        if on_log:
            on_log(line)
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"FFmpeg failed with exit code {_format_return_code(code)}")
    return command

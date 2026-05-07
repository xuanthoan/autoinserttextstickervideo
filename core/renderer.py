from __future__ import annotations

import logging
import subprocess
import tempfile
from collections.abc import Callable

from core.ffmpeg_builder import FFmpegCommand, build_ffmpeg_command
from core.project_model import Project

LOGGER = logging.getLogger(__name__)


def _format_return_code(code: int) -> str:
    if code > 2**31 - 1:
        signed = code - 2**32
        return f"{code} ({signed})"
    return str(code)


def render_project(project: Project, output_path: str, on_log: Callable[[str], None] | None = None) -> FFmpegCommand:
    with tempfile.TemporaryDirectory(prefix="text_assets_") as asset_dir:
        command = build_ffmpeg_command(project, output_path, require_binaries=True, text_asset_dir=asset_dir)
        LOGGER.info("Running FFmpeg: %s", command.shell_string())
        process = subprocess.Popen(command.args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert process.stdout is not None
        for line in process.stdout:
            LOGGER.info(line.rstrip())
            if on_log:
                on_log(line.rstrip())
        code = process.wait()
        if code != 0:
            formatted_code = _format_return_code(code)
            raise RuntimeError(f"FFmpeg failed with exit code {formatted_code}. Check the render log for the invalid FFmpeg option/filter line.")
        return command

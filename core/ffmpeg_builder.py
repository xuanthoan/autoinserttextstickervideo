from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from core.motion_engine import alpha_expr, scale_expr, x_expr
from core.project_model import Project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from utils.ffmpeg_helper import ffmpeg_path


@dataclass
class FFmpegCommand:
    args: list[str]
    filter_complex: str

    def shell_string(self) -> str:
        return " ".join(shlex.quote(part) for part in self.args)


def _escape_drawtext(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")


def _quote_filter(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _enable(layer: TextLayer | StickerLayer) -> str:
    return f"between(t,{layer.start_time},{layer.end_time})"


def _fontfile(layer: TextLayer) -> str:
    if layer.font_path:
        return f":fontfile='{_quote_filter(layer.font_path)}'"
    return ""


def _text_filter(layer: TextLayer, source_label: str, index: int, width: int, height: int, duration: float) -> tuple[list[str], str]:
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    xpos = x_expr(layer.start_time, layer.motion_duration, layer.x, layer.motion_preset, layer.easing)
    draw = (
        f"color=c=black@0.0:s={width}x{height}:d={max(duration, layer.end_time, 1)}[txtsrc{index}];"
        f"[txtsrc{index}]drawtext=text='{_escape_drawtext(layer.text)}'"
        f"{_fontfile(layer)}:fontsize={layer.font_size}:fontcolor={layer.color}"
        f":borderw={layer.stroke_width}:bordercolor={layer.stroke_color}"
        f":x=0:y={layer.y}:alpha='{alpha}'"
    )
    if layer.box_enabled:
        draw += f":box=1:boxcolor={layer.box_color}:boxborderw={layer.box_padding}"
    draw += f",format=rgba,rotate={layer.rotation}*PI/180:c=none:ow=iw:oh=ih[txt{index}]"
    out = f"vtxt{index}"
    overlay = f"[{source_label}][txt{index}]overlay=x='{xpos}':y=0:shortest=1:enable='{_enable(layer)}'[{out}]"
    return [draw, overlay], out


def _sticker_filter(layer: StickerLayer, source_label: str, input_index: int, sticker_index: int) -> tuple[list[str], str]:
    scale = scale_expr(layer.start_time, layer.motion_duration, layer.scale, layer.motion_preset, layer.easing)
    xpos = x_expr(layer.start_time, layer.motion_duration, layer.x, layer.motion_preset, layer.easing)
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    sticker = (
        f"[{input_index}:v]loop=loop=-1:size=1:start=0,setpts=PTS-STARTPTS,format=rgba,"
        f"scale=w='iw*{scale}':h='ih*{scale}':eval=frame,"
        f"rotate={layer.rotation}*PI/180:c=none:ow=rotw(iw):oh=roth(ih),"
        f"colorchannelmixer=aa='{alpha}'[stk{sticker_index}]"
    )
    out = f"vstk{sticker_index}"
    overlay = f"[{source_label}][stk{sticker_index}]overlay=x='{xpos}':y={layer.y}:shortest=1:enable='{_enable(layer)}'[{out}]"
    return [sticker, overlay], out


def build_ffmpeg_command(project: Project, output_path: str, require_binaries: bool = False) -> FFmpegCommand:
    if not project.video_path:
        raise ValueError("Project has no input video")
    args = [ffmpeg_path(require=require_binaries), "-y", "-fflags", "+genpts", "-i", project.video_path]
    for layer in project.sticker_layers:
        if not layer.file_path:
            continue
        args.extend(["-loop", "1", "-framerate", "30", "-i", layer.file_path])

    filters: list[str] = ["[0:v]setpts=PTS-STARTPTS[base]"]
    current = "base"
    for index, layer in enumerate(project.text_layers, start=1):
        parts, current = _text_filter(layer, current, index, project.width, project.height, project.duration)
        filters.extend(parts)

    sticker_input = 1
    for sticker_index, layer in enumerate(project.sticker_layers, start=1):
        if not layer.file_path:
            continue
        parts, current = _sticker_filter(layer, current, sticker_input, sticker_index)
        filters.extend(parts)
        sticker_input += 1

    filters.append(f"[{current}]format=yuv420p[final]")
    filter_complex = ";".join(filters)
    args.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[final]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "veryfast",
            "-c:a",
            "copy",
            "-vsync",
            "2",
            "-movflags",
            "+faststart",
            str(Path(output_path)),
        ]
    )
    return FFmpegCommand(args=args, filter_complex=filter_complex)

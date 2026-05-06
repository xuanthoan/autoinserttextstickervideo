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



def _box_color_parts(value: str) -> tuple[str, float]:
    if "@" not in value:
        return value, 1.0
    color, alpha = value.split("@", 1)
    try:
        return color, max(0.0, min(1.0, float(alpha)))
    except ValueError:
        return color, 1.0


def _approx_text_size(layer: TextLayer) -> tuple[int, int]:
    lines = layer.text.splitlines() or [layer.text]
    longest = max((len(line) for line in lines), default=1)
    text_width = max(1, round(longest * layer.font_size * 0.62))
    text_height = max(1, round(len(lines) * layer.font_size * 1.25))
    stroke = layer.stroke_width * 2
    return text_width + stroke, text_height + stroke


def _rounded_box_alpha_expr(x: int, y: int, width: int, height: int, radius: int, alpha: str, box_alpha: float) -> str:
    right = x + width
    bottom = y + height
    radius = max(1, min(radius, width // 2, height // 2))
    left_inner = x + radius
    right_inner = right - radius
    top_inner = y + radius
    bottom_inner = bottom - radius
    cond = (
        f"between(X\\,{left_inner}\\,{right_inner})*between(Y\\,{y}\\,{bottom})"
        f"+between(X\\,{x}\\,{right})*between(Y\\,{top_inner}\\,{bottom_inner})"
        f"+lte(pow(X-{left_inner}\\,2)+pow(Y-{top_inner}\\,2)\\,{radius * radius})"
        f"+lte(pow(X-{right_inner}\\,2)+pow(Y-{top_inner}\\,2)\\,{radius * radius})"
        f"+lte(pow(X-{left_inner}\\,2)+pow(Y-{bottom_inner}\\,2)\\,{radius * radius})"
        f"+lte(pow(X-{right_inner}\\,2)+pow(Y-{bottom_inner}\\,2)\\,{radius * radius})"
    )
    return f"if({cond}\\,255*{box_alpha}*({alpha})\\,0)"

def _fontfile(layer: TextLayer) -> str:
    if layer.font_path:
        return f":fontfile='{_quote_filter(layer.font_path)}'"
    return ""


def _text_filter(layer: TextLayer, source_label: str, index: int, width: int, height: int, duration: float) -> tuple[list[str], str]:
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    filter_duration = max(duration, layer.end_time, 1)
    text_x = 0
    overlay_target_x = layer.x
    parts: list[str] = []

    if layer.box_enabled:
        padding = layer.effective_box_padding()
        text_width, text_height = _approx_text_size(layer)
        box_width = text_width + padding * 2
        box_height = text_height + padding * 2
        radius = layer.effective_box_radius()
        box_color, box_alpha = _box_color_parts(layer.box_color)
        box_alpha_expr = _rounded_box_alpha_expr(0, round(layer.y), box_width, box_height, radius, alpha, box_alpha)
        text_x = padding
        overlay_target_x = layer.x - padding
        parts.append(
            f"color=c={box_color}:s={width}x{height}:d={filter_duration},format=rgba,"
            f"geq=a='{box_alpha_expr}'[txtbox{index}]"
        )

    xpos = x_expr(layer.start_time, layer.motion_duration, overlay_target_x, layer.motion_preset, layer.easing)
    draw = (
        f"color=c=black@0.0:s={width}x{height}:d={filter_duration}[txtsrc{index}];"
        f"[txtsrc{index}]drawtext=text='{_escape_drawtext(layer.text)}'"
        f"{_fontfile(layer)}:fontsize={layer.font_size}:fontcolor={layer.color}"
        f":borderw={layer.stroke_width}:bordercolor={layer.stroke_color}"
        f":x={text_x}:y={layer.y + (layer.effective_box_padding() if layer.box_enabled else 0)}:alpha='{alpha}',format=rgba[txtfg{index}]"
    )
    parts.append(draw)
    if layer.box_enabled:
        parts.append(f"[txtbox{index}][txtfg{index}]overlay=shortest=1,rotate={layer.rotation}*PI/180:c=none:ow=iw:oh=ih[txt{index}]")
    else:
        parts.append(f"[txtfg{index}]rotate={layer.rotation}*PI/180:c=none:ow=iw:oh=ih[txt{index}]")
    out = f"vtxt{index}"
    overlay = f"[{source_label}][txt{index}]overlay=x='{xpos}':y=0:shortest=1:enable='{_enable(layer)}'[{out}]"
    parts.append(overlay)
    return parts, out


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

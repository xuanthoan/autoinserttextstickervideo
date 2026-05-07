from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from core.motion_engine import alpha_expr, scale_expr, x_expr, y_expr
from core.project_model import Project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from core.text_template_engine import TextTemplateEngine
from utils.ffmpeg_helper import ffmpeg_path
from utils.paths import resource_path


@dataclass
class FFmpegCommand:
    args: list[str]
    filter_complex: str

    def shell_string(self) -> str:
        return " ".join(shlex.quote(part) for part in self.args)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%").replace("\n", "\\n")


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _color(value: str) -> str:
    if "@" in value:
        base, alpha = value.split("@", 1)
        return f"{_color(base)}@{alpha}"
    return f"0x{value[1:]}" if value.startswith("#") else value


def _enable(layer: TextLayer | StickerLayer) -> str:
    return f"between(t,{layer.start_time},{layer.end_time})"


def _font(layer: TextLayer) -> str:
    if layer.font_path:
        return f":fontfile='{_quote(layer.font_path)}'"
    return f":font='{_quote(layer.font_family)}'"


def _text_filter(layer: TextLayer, source: str, index: int, project: Project) -> tuple[list[str], str]:
    engine = TextTemplateEngine.load(resource_path("templates/text_templates.json"))
    template = engine.get(layer.template_id)
    layout = engine.layout(layer, project.width, project.height, template)
    layer.color = template.text_color
    layer.box_color = template.background_color
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    x = x_expr(layer.start_time, layer.motion_duration, layout.x, layer.motion_preset, layer.easing)
    y = y_expr(layer.start_time, layer.motion_duration, layout.y, layer.motion_preset, layer.easing)
    text = _escape(layout.text)
    borderw = layer.stroke_width if layer.stroke_enabled else 0
    draw = (
        f"[{source}]drawtext=text='{text}'{_font(layer)}:fontsize={layout.font_size}:fontcolor={_color(template.text_color)}"
        f":borderw={borderw}:bordercolor={_color(layer.stroke_color)}"
        f":line_spacing={layout.line_spacing}:x='{x}':y='{y}':alpha='{alpha}'"
        f":box=1:boxcolor={_color(template.background_color)}:boxborderw={layout.hpad}"
        f":enable='{_enable(layer)}'[vtxt{index}]"
    )
    return [draw], f"vtxt{index}"


def _sticker_filter(layer: StickerLayer, source: str, input_index: int, sticker_index: int) -> tuple[list[str], str]:
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    x = x_expr(layer.start_time, layer.motion_duration, layer.x, layer.motion_preset, layer.easing)
    y = y_expr(layer.start_time, layer.motion_duration, layer.y, layer.motion_preset, layer.easing)
    scale = scale_expr(layer.start_time, layer.motion_duration, layer.scale, layer.motion_preset, layer.easing)
    prep = (
        f"[{input_index}:v]loop=loop=-1:size=1:start=0,setpts=PTS-STARTPTS,format=rgba,"
        f"scale=w='iw*{scale}':h='ih*{scale}':eval=frame,"
        f"rotate={layer.rotation}*PI/180:c=none:ow=rotw(iw):oh=roth(ih),"
        f"colorchannelmixer=aa='{alpha}'[stk{sticker_index}]"
    )
    out = f"vstk{sticker_index}"
    overlay = f"[{source}][stk{sticker_index}]overlay=x='{x}':y='{y}':shortest=1:enable='{_enable(layer)}'[{out}]"
    return [prep, overlay], out


def build_ffmpeg_command(project: Project, output_path: str, require_binaries: bool = False, text_asset_dir: str | Path | None = None) -> FFmpegCommand:
    del text_asset_dir
    if not project.video_path:
        raise ValueError("Project has no input video")
    args = [
        ffmpeg_path(require=require_binaries),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-stats_period",
        "0.5",
        "-fflags",
        "+genpts",
        "-i",
        project.video_path,
    ]
    for layer in project.sticker_layers:
        if layer.file_path:
            args.extend(["-loop", "1", "-framerate", "30", "-i", layer.file_path])
    filters = ["[0:v]setpts=PTS-STARTPTS[base]"]
    current = "base"
    for idx, layer in enumerate(project.text_layers, start=1):
        parts, current = _text_filter(layer, current, idx, project)
        filters.extend(parts)
    input_index = 1
    for idx, layer in enumerate(project.sticker_layers, start=1):
        if not layer.file_path:
            continue
        parts, current = _sticker_filter(layer, current, input_index, idx)
        filters.extend(parts)
        input_index += 1
    filters.append(f"[{current}]format=yuv420p[final]")
    args.extend([
        "-filter_complex", ";".join(filters),
        "-progress", "pipe:1", "-nostats",
        "-map", "[final]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "192k", "-vsync", "2", "-movflags", "+faststart",
        str(Path(output_path)),
    ])
    return FFmpegCommand(args, ";".join(filters))

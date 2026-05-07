from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import tempfile

from core.motion_engine import alpha_expr, scale_expr, x_expr, y_expr
from core.project_model import Project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from core.text_template_engine import TextLayout, TextTemplateEngine
from utils.ffmpeg_helper import ffmpeg_path
from utils.paths import resource_path


@dataclass
class FFmpegCommand:
    args: list[str]
    filter_complex: str

    def shell_string(self) -> str:
        return " ".join(shlex.quote(part) for part in self.args)


def _enable(layer: TextLayer | StickerLayer) -> str:
    return f"between(t,{layer.start_time},{layer.end_time})"


def _asset_margin(layout) -> int:  # type: ignore[no-untyped-def]
    return max(4, layout.stroke_width * 2 + layout.shadow_blur)


def _text_asset_filter(layer: TextLayer, layout: TextLayout, source: str, input_index: int, text_index: int) -> tuple[list[str], str]:
    margin = _asset_margin(layout)
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    scale = scale_expr(layer.start_time, layer.motion_duration, 1.0, layer.motion_preset, layer.easing)
    x = x_expr(layer.start_time, layer.motion_duration, layout.x - margin, layer.motion_preset, layer.easing)
    y = y_expr(layer.start_time, layer.motion_duration, layout.y - margin, layer.motion_preset, layer.easing)
    prep = (
        f"[{input_index}:v]format=rgba,scale=w='iw*{scale}':h='ih*{scale}':eval=frame,"
        f"colorchannelmixer=aa='{alpha}'[txt{text_index}]"
    )
    out = f"vtxt{text_index}"
    overlay = f"[{source}][txt{text_index}]overlay=x='{x}':y='{y}':shortest=1:enable='{_enable(layer)}'[{out}]"
    return [prep, overlay], out


def _sticker_filter(layer: StickerLayer, source: str, input_index: int, sticker_index: int) -> tuple[list[str], str]:
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    x = x_expr(layer.start_time, layer.motion_duration, layer.x, layer.motion_preset, layer.easing)
    y = y_expr(layer.start_time, layer.motion_duration, layer.y, layer.motion_preset, layer.easing)
    scale = scale_expr(layer.start_time, layer.motion_duration, layer.scale, layer.motion_preset, layer.easing)
    prep = (
        f"[{input_index}:v]setpts=PTS-STARTPTS,format=rgba,"
        f"scale=w='iw*{scale}':h='ih*{scale}':eval=frame,"
        f"rotate={layer.rotation}*PI/180:c=none:ow=rotw(iw):oh=roth(ih),"
        f"colorchannelmixer=aa='{alpha}'[stk{sticker_index}]"
    )
    out = f"vstk{sticker_index}"
    overlay = f"[{source}][stk{sticker_index}]overlay=x='{x}':y='{y}':shortest=1:enable='{_enable(layer)}'[{out}]"
    return [prep, overlay], out


def build_ffmpeg_command(project: Project, output_path: str, require_binaries: bool = False, text_asset_dir: str | Path | None = None) -> FFmpegCommand:
    if not project.video_path:
        raise ValueError("Project has no input video")
    text_dir = Path(text_asset_dir) if text_asset_dir is not None else Path(tempfile.gettempdir()) / "autoinsert_text_assets"
    text_dir.mkdir(parents=True, exist_ok=True)
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
    engine = TextTemplateEngine.load(resource_path("templates/text_templates.json"))
    text_layouts: dict[str, TextLayout] = {}
    text_input_indexes: list[int] = []
    for idx, layer in enumerate(project.text_layers, start=1):
        template = engine.get(layer.template_id)
        layout = engine.layout(layer, project.width, project.height, template)
        layer.color = template.text_color
        layer.box_color = template.background_color
        text_layouts[layer.layer_id] = layout
        asset_path = text_dir / f"text_layer_{idx}_{layer.layer_id}.png"
        from core.text_rasterizer import render_text_layer_image

        render_text_layer_image(layer, layout, asset_path)
        args.extend(["-loop", "1", "-framerate", "30", "-i", str(asset_path)])
        text_input_indexes.append(len(text_input_indexes) + 1)
    sticker_input_indexes: list[int] = []
    for layer in project.sticker_layers:
        if layer.file_path:
            args.extend(["-loop", "1", "-framerate", "30", "-i", layer.file_path])
            sticker_input_indexes.append(len(text_input_indexes) + len(sticker_input_indexes) + 1)
    filters = ["[0:v]setpts=PTS-STARTPTS[base]"]
    current = "base"
    for idx, layer in enumerate(project.text_layers, start=1):
        parts, current = _text_asset_filter(layer, text_layouts[layer.layer_id], current, text_input_indexes[idx - 1], idx)
        filters.extend(parts)
    sticker_number = 1
    sticker_input_iter = iter(sticker_input_indexes)
    for layer in project.sticker_layers:
        if not layer.file_path:
            continue
        input_index = next(sticker_input_iter)
        parts, current = _sticker_filter(layer, current, input_index, sticker_number)
        filters.extend(parts)
        sticker_number += 1
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

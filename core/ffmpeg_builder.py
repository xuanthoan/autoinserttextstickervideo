from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from core.motion_engine import alpha_expr, scale_expr, x_expr
from core.project_model import Project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from core.text_template_engine import TextRenderAsset, TextTemplateEngine
from utils.ffmpeg_helper import ffmpeg_path


@dataclass
class FFmpegCommand:
    args: list[str]
    filter_complex: str

    def shell_string(self) -> str:
        return " ".join(shlex.quote(part) for part in self.args)


def _escape_drawtext(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%").replace("\n", "\\n")


def _quote_filter(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _ffmpeg_color(value: str) -> str:
    if "@" in value:
        color, alpha = value.split("@", 1)
        return f"{_ffmpeg_color(color)}@{alpha}"
    if value.startswith("#") and len(value) in {4, 7, 9}:
        return f"0x{value[1:]}"
    return value


def _enable(layer: TextLayer | StickerLayer) -> str:
    return f"between(t,{layer.start_time},{layer.end_time})"


def _fontfile(layer: TextLayer) -> str:
    if layer.font_path:
        return f":fontfile='{_quote_filter(layer.font_path)}'"
    return ""


def _font_family(layer: TextLayer) -> str:
    if layer.font_path:
        return ""
    return f":font='{_quote_filter(layer.font_family)}'"


def _text_drawtext_fallback(layer: TextLayer, source_label: str, index: int, width: int, height: int, duration: float) -> tuple[list[str], str]:
    """Stable no-PySide fallback. Rounded export uses rendered PNG assets."""
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    padding = layer.effective_box_padding() if layer.box_enabled else 0
    xpos = x_expr(layer.start_time, layer.motion_duration, layer.x - padding, layer.motion_preset, layer.easing)
    y = layer.y + padding if layer.box_enabled else layer.y
    draw = (
        f"color=c=black@0.0:s={width}x{height}:d={max(duration, layer.end_time, 1)}[txtsrc{index}];"
        f"[txtsrc{index}]drawtext=text='{_escape_drawtext(layer.text.upper() if layer.auto_uppercase else layer.text)}'"
        f"{_fontfile(layer)}{_font_family(layer)}:fontsize={layer.font_size}:fontcolor={_ffmpeg_color(layer.color)}"
        f":borderw={(layer.stroke_width if layer.stroke_enabled else 0)}:bordercolor={_ffmpeg_color(layer.stroke_color)}"
        f":x={padding}:y={y}:alpha='{alpha}'"
    )
    if layer.box_enabled:
        draw += f":box=1:boxcolor={_ffmpeg_color(layer.box_color)}:boxborderw={padding}"
    draw += f",format=rgba,rotate={layer.rotation}*PI/180:c=none:ow=iw:oh=ih[txt{index}]"
    out = f"vtxt{index}"
    overlay = f"[{source_label}][txt{index}]overlay=x='{xpos}':y=0:shortest=1:enable='{_enable(layer)}'[{out}]"
    return [draw, overlay], out


def _text_asset_filter(layer: TextLayer, asset: TextRenderAsset, source_label: str, input_index: int, text_index: int) -> tuple[list[str], str]:
    scale = scale_expr(layer.start_time, layer.motion_duration, 1.0, layer.motion_preset, layer.easing)
    xpos = x_expr(layer.start_time, layer.motion_duration, asset.x, layer.motion_preset, layer.easing)
    alpha = alpha_expr(layer.start_time, layer.motion_duration, layer.opacity, layer.motion_preset, layer.easing)
    text = (
        f"[{input_index}:v]loop=loop=-1:size=1:start=0,setpts=PTS-STARTPTS,format=rgba,"
        f"scale=w='iw*{scale}':h='ih*{scale}':eval=frame,"
        f"rotate={layer.rotation}*PI/180:c=none:ow=rotw(iw):oh=roth(ih),"
        f"colorchannelmixer=aa='{alpha}'[txt{text_index}]"
    )
    out = f"vtxt{text_index}"
    overlay = f"[{source_label}][txt{text_index}]overlay=x='{xpos}':y={asset.y}:shortest=1:enable='{_enable(layer)}'[{out}]"
    return [text, overlay], out


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


def _render_text_assets(project: Project, text_asset_dir: str | Path | None) -> list[TextRenderAsset | None]:
    if text_asset_dir is None:
        return [None for _ in project.text_layers]
    engine = TextTemplateEngine.load(Path("templates/text_templates.json"))
    assets: list[TextRenderAsset | None] = []
    for index, layer in enumerate(project.text_layers, start=1):
        path = Path(text_asset_dir) / f"text_layer_{index}_{layer.layer_id}.png"
        assets.append(engine.render_png(layer, project.width, project.height, path))
    return assets


def build_ffmpeg_command(project: Project, output_path: str, require_binaries: bool = False, text_asset_dir: str | Path | None = None) -> FFmpegCommand:
    if not project.video_path:
        raise ValueError("Project has no input video")
    args = [ffmpeg_path(require=require_binaries), "-y", "-fflags", "+genpts", "-i", project.video_path]
    text_assets = _render_text_assets(project, text_asset_dir)
    for asset in text_assets:
        if asset is not None:
            args.extend(["-loop", "1", "-framerate", "30", "-i", str(asset.path)])
    for layer in project.sticker_layers:
        if not layer.file_path:
            continue
        args.extend(["-loop", "1", "-framerate", "30", "-i", layer.file_path])

    filters: list[str] = ["[0:v]setpts=PTS-STARTPTS[base]"]
    current = "base"
    input_index = 1
    for index, (layer, asset) in enumerate(zip(project.text_layers, text_assets, strict=False), start=1):
        if asset is None:
            parts, current = _text_drawtext_fallback(layer, current, index, project.width, project.height, project.duration)
        else:
            parts, current = _text_asset_filter(layer, asset, current, input_index, index)
            input_index += 1
        filters.extend(parts)

    for sticker_index, layer in enumerate(project.sticker_layers, start=1):
        if not layer.file_path:
            continue
        parts, current = _sticker_filter(layer, current, input_index, sticker_index)
        filters.extend(parts)
        input_index += 1

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

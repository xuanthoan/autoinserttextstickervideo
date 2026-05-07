from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontMetricsF

from core.text_layer import TextLayer
from core.text_template_engine import TextLayout


@dataclass(frozen=True)
class TextLineDraw:
    text: str
    x: float
    baseline: float
    width: float


@dataclass(frozen=True)
class TextDrawPlan:
    lines: list[TextLineDraw]
    block_top: float
    block_height: float
    line_advance: float


def build_text_draw_plan(layer: TextLayer, layout: TextLayout, font: QFont, origin_x: float = 0.0, origin_y: float = 0.0) -> TextDrawPlan:
    metrics = QFontMetricsF(font)
    line_advance = max(metrics.lineSpacing(), metrics.ascent() + metrics.descent()) + layout.line_spacing
    text_block_height = max(0.0, len(layout.lines) * (line_advance - layout.line_spacing) + max(0, len(layout.lines) - 1) * layout.line_spacing)
    content_height = layout.box_height if layer.box_enabled else text_block_height
    block_top = origin_y + max(0.0, (content_height - text_block_height) / 2.0)
    baseline = block_top + metrics.ascent()
    draw_lines: list[TextLineDraw] = []
    for line in layout.lines:
        line_width = metrics.horizontalAdvance(line)
        x = origin_x + ((layout.box_width - line_width) / 2.0 if layer.box_enabled else 0.0)
        draw_lines.append(TextLineDraw(line, x, baseline, line_width))
        baseline += line_advance
    return TextDrawPlan(draw_lines, block_top, text_block_height, line_advance)

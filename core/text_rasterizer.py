from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen

from core.text_layer import TextLayer
from core.text_draw_plan import build_text_draw_plan
from core.text_template_engine import TextLayout


def _color(value: str, fallback: str = "black") -> QColor:
    if "@" not in value:
        color = QColor(value)
        return color if color.isValid() else QColor(fallback)
    name, alpha = value.split("@", 1)
    color = QColor(name)
    if not color.isValid():
        color = QColor(fallback)
    try:
        color.setAlphaF(max(0.0, min(1.0, float(alpha))))
    except ValueError:
        color.setAlphaF(1.0)
    return color


def render_text_layer_image(layer: TextLayer, layout: TextLayout, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    margin = max(4, layout.stroke_width * 2 + layout.shadow_blur)
    image = QImage(layout.box_width + margin * 2, layout.box_height + margin * 2, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    font = QFont(layout.template.font_family, layout.font_size)
    font.setWeight(QFont.Weight.ExtraBold if layout.template.font_weight >= 800 else QFont.Weight.Bold)

    painter = QPainter(image)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    if layer.box_enabled:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_color(layout.template.background_color, "black")))
        painter.drawRoundedRect(margin, margin, layout.box_width, layout.box_height, layout.radius, layout.radius)

    painter.setFont(font)
    plan = build_text_draw_plan(layer, layout, font, origin_x=margin, origin_y=margin)
    for draw_line in plan.lines:
        path_item = QPainterPath()
        path_item.addText(draw_line.x, draw_line.baseline, font, draw_line.text)
        if layer.stroke_enabled and layout.stroke_width > 0:
            painter.setPen(QPen(_color(layer.stroke_color, "black"), layout.stroke_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path_item)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_color(layout.template.text_color, "white")))
        painter.drawPath(path_item)
    painter.end()
    image.save(str(target), "PNG")
    return target

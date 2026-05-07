from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen

from core.text_layer import TextLayer
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
    metrics = QFontMetricsF(font)
    baseline = margin + (layout.vpad + metrics.ascent() if layer.box_enabled else metrics.ascent())
    for line in layout.lines:
        line_width = metrics.horizontalAdvance(line)
        x = margin + ((layout.box_width - line_width) / 2 if layer.box_enabled else 0)
        path_item = QPainterPath()
        path_item.addText(x, baseline, font, line)
        if layer.stroke_enabled and layout.stroke_width > 0:
            painter.setPen(QPen(_color(layer.stroke_color, "black"), layout.stroke_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path_item)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_color(layout.template.text_color, "white")))
        painter.drawPath(path_item)
        baseline += metrics.height() + layout.line_spacing
    painter.end()
    image.save(str(target), "PNG")
    return target

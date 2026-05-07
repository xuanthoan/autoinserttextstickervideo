from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QStyleOptionGraphicsItem, QWidget

from core.motion_engine import state_at
from core.project_model import Project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from core.text_template_engine import TextLayout, TextTemplateEngine

SNAP_THRESHOLD = 10


def _preview_color(value: str, fallback: str = "black") -> QColor:
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


class LayerTextItem(QGraphicsTextItem):
    def __init__(self, layer: TextLayer, on_move: Callable[[str, float, float], None], current_time: float, video_width: int, video_height: int, template_engine: TextTemplateEngine) -> None:
        super().__init__(layer.text)
        self.layout_data: TextLayout = template_engine.layout(layer, video_width, video_height)
        motion = state_at(layer.motion_preset, current_time, layer.start_time, layer.motion_duration, self.layout_data.x, self.layout_data.y, layer.opacity, layer.easing)
        self.layer = layer
        self.on_move = on_move
        self.setDefaultTextColor(_preview_color(layer.color, "white"))
        self.setPlainText(self.layout_data.text)
        font = QFont(self.layout_data.font_family, self.layout_data.font_size)
        font.setWeight(QFont.Weight.ExtraBold if self.layout_data.font_weight >= 800 else QFont.Weight.Bold)
        self.setFont(font)
        self.setOpacity(motion.alpha)
        self.setRotation(layer.rotation)
        self.setScale(motion.scale)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(motion.x if motion.x is not None else self.layout_data.x, motion.y if motion.y is not None else self.layout_data.y)
        self.setZValue(20)

    def _text_rect(self) -> QRectF:
        return QRectF(0, 0, self.layout_data.text_width, self.layout_data.text_height)

    def boundingRect(self) -> QRectF:
        if self.layer.box_enabled:
            return QRectF(0, 0, self.layout_data.box_width, self.layout_data.box_height)
        stroke = self.layer.stroke_width
        return self._text_rect().adjusted(-stroke, -stroke, stroke, stroke)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        del option, widget
        painter.save()
        if self.layer.box_enabled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(_preview_color(self.layer.box_color, "black")))
            painter.drawRoundedRect(self.boundingRect(), self.layout_data.border_radius, self.layout_data.border_radius)
        metrics = QFontMetricsF(self.font())
        baseline = self.layout_data.vertical_padding + metrics.ascent() if self.layer.box_enabled else metrics.ascent()
        for line in self.layout_data.lines:
            line_width = metrics.horizontalAdvance(line)
            x = (self.layout_data.box_width - line_width) / 2 if self.layer.box_enabled else 0
            path = QPainterPath()
            path.addText(x, baseline, self.font(), line)
            if self.layer.stroke_enabled and self.layer.stroke_width > 0:
                painter.setPen(QPen(_preview_color(self.layer.stroke_color, "black"), self.layer.stroke_width * 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(_preview_color(self.layer.color, "white")))
            painter.drawPath(path)
            baseline += metrics.height() + self.layout_data.line_spacing
        painter.restore()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        pos = self.pos()
        self.on_move(self.layer.layer_id, pos.x(), pos.y())
        super().mouseReleaseEvent(event)


class LayerStickerItem(QGraphicsPixmapItem):
    def __init__(self, layer: StickerLayer, on_move: Callable[[str, float, float], None], current_time: float) -> None:
        pixmap = QPixmap(layer.file_path) if layer.file_path and Path(layer.file_path).exists() else QPixmap(160, 100)
        if pixmap.isNull():
            pixmap = QPixmap(160, 100)
        if layer.file_path == "" or pixmap.size().width() == 160 and pixmap.size().height() == 100:
            pixmap.fill(QColor("#ffcc00"))
        motion = state_at(layer.motion_preset, current_time, layer.start_time, layer.motion_duration, layer.x, layer.y, layer.opacity, layer.easing)
        super().__init__(pixmap)
        self.layer = layer
        self.on_move = on_move
        self.setOpacity(motion.alpha)
        self.setScale(layer.scale * motion.scale)
        self.setRotation(layer.rotation)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(motion.x if motion.x is not None else self.layout_data.x, motion.y if motion.y is not None else self.layout_data.y)
        self.setZValue(30)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        pos = self.pos()
        self.on_move(self.layer.layer_id, pos.x(), pos.y())
        super().mouseReleaseEvent(event)


class PreviewCanvas(QGraphicsView):
    layerMoved = Signal(str, float, float)
    filesDropped = Signal(list)
    videoOutputChanged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setAcceptDrops(True)
        self.project: Project | None = None
        self.current_time = 0.0
        self.video_item: QGraphicsVideoItem | None = None
        self.video_backdrop: QGraphicsRectItem | None = None
        self.overlay_items: list[LayerTextItem | LayerStickerItem] = []
        self.template_engine = TextTemplateEngine.load("templates/text_templates.json")
        self.center_v = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_h = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_v.hide()
        self.center_h.hide()

    def set_project(self, project: Project) -> None:
        self.project = project
        self.current_time = 0.0
        self.refresh()

    def set_time(self, seconds: float) -> None:
        self.current_time = seconds
        self.refresh_overlays()

    def refresh(self) -> None:
        self.scene.clear()
        self.overlay_items = []
        if self.project is None:
            return
        self.video_backdrop = self.scene.addRect(0, 0, self.project.width, self.project.height, QPen(QColor("#555")), QBrush(QColor("#111")))
        self.video_backdrop.setZValue(-20)
        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(QSizeF(self.project.width, self.project.height))
        self.video_item.setZValue(-10)
        self.scene.addItem(self.video_item)
        self.videoOutputChanged.emit(self.video_item)
        self.center_v = self.scene.addLine(self.project.width / 2, 0, self.project.width / 2, self.project.height, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_h = self.scene.addLine(0, self.project.height / 2, self.project.width, self.project.height / 2, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_v.setZValue(100)
        self.center_h.setZValue(100)
        self.center_v.hide()
        self.center_h.hide()
        self.refresh_overlays()
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def refresh_overlays(self) -> None:
        if self.project is None:
            return
        for item in self.overlay_items:
            self.scene.removeItem(item)
        self.overlay_items = []
        for layer in self.project.text_layers:
            if layer.start_time <= self.current_time <= layer.end_time:
                item = LayerTextItem(layer, self._snap_and_emit, self.current_time, self.project.width, self.project.height, self.template_engine)
                self.overlay_items.append(item)
                self.scene.addItem(item)
        for layer in self.project.sticker_layers:
            if layer.start_time <= self.current_time <= layer.end_time:
                item = LayerStickerItem(layer, self._snap_and_emit, self.current_time)
                self.overlay_items.append(item)
                self.scene.addItem(item)

    def _snap_and_emit(self, layer_id: str, x: float, y: float) -> None:
        if self.project is None:
            return
        snapped_x, snapped_y = x, y
        show_v = abs(x - self.project.width / 2) <= SNAP_THRESHOLD
        show_h = abs(y - self.project.height / 2) <= SNAP_THRESHOLD
        if show_v:
            snapped_x = self.project.width / 2
        if show_h:
            snapped_y = self.project.height / 2
        self.center_v.setVisible(show_v)
        self.center_h.setVisible(show_h)
        self.layerMoved.emit(layer_id, snapped_x, snapped_y)
        self.refresh()

    def dragEnterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        self.filesDropped.emit(paths)
        event.acceptProposedAction()

    def placeholder_frame(self) -> QImage:
        if self.project is None:
            return QImage()
        image = QImage(self.project.width, self.project.height, QImage.Format.Format_RGB32)
        image.fill(QColor("#111"))
        return image

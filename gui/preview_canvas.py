from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QStyleOptionGraphicsItem, QWidget

from core.motion_engine import state_at
from core.project_model import Project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from core.text_template_engine import TextLayout, TextTemplateEngine, safe_area
from utils.ffmpeg_helper import extract_preview_frame
from utils.paths import resource_path

SNAP_THRESHOLD = 10
GUIDE_COLOR = QColor(90, 210, 255, 160)
SAFE_OVERLAY_COLOR = QColor(0, 0, 0, 85)
SAFE_BORDER_COLOR = QColor(255, 255, 255, 90)


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


class DraggableOverlayMixin:
    layer: TextLayer | StickerLayer
    on_move: Callable[[str, float, float], None]
    on_drag: Callable[[QGraphicsItem, float, float], tuple[float, float, bool, bool]]
    on_release: Callable[[], None]

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # type: ignore[no-untyped-def]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            point = value
            x, y, show_v, show_h = self.on_drag(self, point.x(), point.y())
            self.scene().update()
            from PySide6.QtCore import QPointF

            return QPointF(x, y)
        return super().itemChange(change, value)  # type: ignore[misc]

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        pos = self.pos()
        self.on_move(self.layer.layer_id, pos.x(), pos.y())
        self.on_release()
        super().mouseReleaseEvent(event)  # type: ignore[misc]


class LayerTextItem(DraggableOverlayMixin, QGraphicsTextItem):
    def __init__(
        self,
        layer: TextLayer,
        on_move: Callable[[str, float, float], None],
        on_drag: Callable[[QGraphicsItem, float, float], tuple[float, float, bool, bool]],
        on_release: Callable[[], None],
        current_time: float,
        video_width: int,
        video_height: int,
        template_engine: TextTemplateEngine,
    ) -> None:
        super().__init__(layer.text)
        self.layout_data: TextLayout = template_engine.layout(layer, video_width, video_height)
        motion = state_at(layer.motion_preset, current_time, layer.start_time, layer.motion_duration, self.layout_data.x, self.layout_data.y, layer.opacity, layer.easing)
        self.layer = layer
        self.on_move = on_move
        self.on_drag = on_drag
        self.on_release = on_release
        self.setDefaultTextColor(_preview_color(layer.color, "white"))
        self.setPlainText(self.layout_data.text)
        font = QFont(self.layout_data.template.font_family, self.layout_data.font_size)
        font.setWeight(QFont.Weight.ExtraBold if self.layout_data.template.font_weight >= 800 else QFont.Weight.Bold)
        self.setFont(font)
        self.setOpacity(motion.alpha)
        self.setRotation(layer.rotation)
        self.setScale(motion.scale)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(motion.x, motion.y)
        self.setZValue(20)

    def _text_rect(self) -> QRectF:
        return QRectF(0, 0, self.layout_data.text_width, self.layout_data.text_height)

    def boundingRect(self) -> QRectF:
        if self.layer.box_enabled:
            return QRectF(0, 0, self.layout_data.box_width, self.layout_data.box_height)
        stroke = self.layout_data.stroke_width if self.layer.stroke_enabled else 0
        return self._text_rect().adjusted(-stroke, -stroke, stroke, stroke)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        del option, widget
        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        if self.layer.box_enabled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(_preview_color(self.layout_data.template.background_color, "black")))
            painter.drawRoundedRect(self.boundingRect(), self.layout_data.radius, self.layout_data.radius)
        metrics = QFontMetricsF(self.font())
        baseline = self.layout_data.vpad + metrics.ascent() if self.layer.box_enabled else metrics.ascent()
        for line in self.layout_data.lines:
            line_width = metrics.horizontalAdvance(line)
            x = (self.layout_data.box_width - line_width) / 2 if self.layer.box_enabled else 0
            path = QPainterPath()
            path.addText(x, baseline, self.font(), line)
            if self.layer.stroke_enabled and self.layout_data.stroke_width > 0:
                painter.setPen(QPen(_preview_color(self.layer.stroke_color, "black"), self.layout_data.stroke_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(_preview_color(self.layout_data.template.text_color, "white")))
            painter.drawPath(path)
            baseline += metrics.height() + self.layout_data.line_spacing
        painter.restore()


class LayerStickerItem(DraggableOverlayMixin, QGraphicsPixmapItem):
    def __init__(
        self,
        layer: StickerLayer,
        on_move: Callable[[str, float, float], None],
        on_drag: Callable[[QGraphicsItem, float, float], tuple[float, float, bool, bool]],
        on_release: Callable[[], None],
        current_time: float,
    ) -> None:
        pixmap = QPixmap(layer.file_path) if layer.file_path and Path(layer.file_path).exists() else QPixmap(160, 100)
        if pixmap.isNull():
            pixmap = QPixmap(160, 100)
        if layer.file_path == "" or (pixmap.size().width() == 160 and pixmap.size().height() == 100):
            pixmap.fill(QColor("#ffcc00"))
        motion = state_at(layer.motion_preset, current_time, layer.start_time, layer.motion_duration, layer.x, layer.y, layer.opacity, layer.easing)
        super().__init__(pixmap)
        self.layer = layer
        self.on_move = on_move
        self.on_drag = on_drag
        self.on_release = on_release
        self.setOpacity(motion.alpha)
        self.setScale(layer.scale * motion.scale)
        self.setRotation(layer.rotation)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(motion.x, motion.y)
        self.setZValue(30)


class PreviewCanvas(QGraphicsView):
    layerMoved = Signal(str, float, float)
    filesDropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setAcceptDrops(True)
        self.project: Project | None = None
        self.current_time = 0.0
        self.video_item: QGraphicsPixmapItem | None = None
        self.video_backdrop: QGraphicsRectItem | None = None
        self.safe_items: list[QGraphicsRectItem] = []
        self.overlay_items: list[LayerTextItem | LayerStickerItem] = []
        self.template_engine = TextTemplateEngine.load(resource_path("templates/text_templates.json"))
        self.preview_pixmap = QPixmap()
        self.center_v = self.scene.addLine(0, 0, 0, 0, QPen(GUIDE_COLOR, 1.5, Qt.PenStyle.SolidLine))
        self.center_h = self.scene.addLine(0, 0, 0, 0, QPen(GUIDE_COLOR, 1.5, Qt.PenStyle.SolidLine))
        self.center_v.hide()
        self.center_h.hide()

    def set_project(self, project: Project) -> None:
        self.project = project
        self.current_time = 0.0
        self.refresh()

    def load_video_frame(self, video_path: str) -> None:
        try:
            frame_path = extract_preview_frame(video_path, seek_seconds=0.05)
            pixmap = QPixmap(str(frame_path))
            if not pixmap.isNull():
                self.preview_pixmap = pixmap
        except Exception:  # noqa: BLE001
            self.preview_pixmap = QPixmap()
        self.refresh()

    def set_time(self, seconds: float) -> None:
        self.current_time = seconds
        self.refresh_overlays()

    def _safe_rect(self) -> QRectF:
        if self.project is None:
            return QRectF()
        area = safe_area(self.project.width, self.project.height)
        return QRectF(area.left, area.top, self.project.width - area.left - area.right, self.project.height - area.top - area.bottom)

    def refresh(self) -> None:
        self.scene.clear()
        self.safe_items = []
        self.overlay_items = []
        if self.project is None:
            return
        self.scene.setSceneRect(0, 0, self.project.width, self.project.height)
        self.video_backdrop = self.scene.addRect(0, 0, self.project.width, self.project.height, QPen(QColor("#555")), QBrush(QColor("#111")))
        self.video_backdrop.setZValue(-30)
        pixmap = self.preview_pixmap
        if pixmap.isNull():
            pixmap = QPixmap(self.project.width, self.project.height)
            pixmap.fill(QColor("#181818"))
        self.video_item = self.scene.addPixmap(pixmap.scaled(self.project.width, self.project.height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.video_item.setZValue(-20)
        self._draw_safe_area()
        guide_pen = QPen(GUIDE_COLOR, 1.5, Qt.PenStyle.SolidLine)
        guide_pen.setCosmetic(True)
        self.center_v = self.scene.addLine(self.project.width / 2, 0, self.project.width / 2, self.project.height, guide_pen)
        self.center_h = self.scene.addLine(0, self.project.height / 2, self.project.width, self.project.height / 2, guide_pen)
        self.center_v.setZValue(100)
        self.center_h.setZValue(100)
        self.center_v.hide()
        self.center_h.hide()
        self.refresh_overlays()
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_safe_area(self) -> None:
        if self.project is None:
            return
        rect = self._safe_rect()
        w, h = self.project.width, self.project.height
        overlay_pen = QPen(Qt.PenStyle.NoPen)
        for item in [
            self.scene.addRect(0, 0, w, rect.top(), overlay_pen, QBrush(SAFE_OVERLAY_COLOR)),
            self.scene.addRect(0, rect.bottom(), w, h - rect.bottom(), overlay_pen, QBrush(SAFE_OVERLAY_COLOR)),
            self.scene.addRect(0, rect.top(), rect.left(), rect.height(), overlay_pen, QBrush(SAFE_OVERLAY_COLOR)),
            self.scene.addRect(rect.right(), rect.top(), w - rect.right(), rect.height(), overlay_pen, QBrush(SAFE_OVERLAY_COLOR)),
            self.scene.addRect(rect, QPen(SAFE_BORDER_COLOR, 1, Qt.PenStyle.DashLine)),
        ]:
            item.setZValue(5)
            self.safe_items.append(item)

    def refresh_overlays(self) -> None:
        if self.project is None:
            return
        for item in self.overlay_items:
            self.scene.removeItem(item)
        self.overlay_items = []
        for layer in self.project.text_layers:
            if layer.start_time <= self.current_time <= layer.end_time:
                item = LayerTextItem(layer, self._emit_move, self._snap_clamp_drag, self._hide_guides, self.current_time, self.project.width, self.project.height, self.template_engine)
                self.overlay_items.append(item)
                self.scene.addItem(item)
        for layer in self.project.sticker_layers:
            if layer.start_time <= self.current_time <= layer.end_time:
                item = LayerStickerItem(layer, self._emit_move, self._snap_clamp_drag, self._hide_guides, self.current_time)
                self.overlay_items.append(item)
                self.scene.addItem(item)

    def _snap_clamp_drag(self, item: QGraphicsItem, x: float, y: float) -> tuple[float, float, bool, bool]:
        if self.project is None:
            return x, y, False, False
        rect = item.boundingRect()
        scale = abs(item.scale()) or 1.0
        width = rect.width() * scale
        height = rect.height() * scale
        safe = self._safe_rect()
        center_x = x + width / 2
        center_y = y + height / 2
        show_v = abs(center_x - self.project.width / 2) <= SNAP_THRESHOLD
        show_h = abs(center_y - self.project.height / 2) <= SNAP_THRESHOLD
        if show_v:
            x = self.project.width / 2 - width / 2
        if show_h:
            y = self.project.height / 2 - height / 2
        x = min(max(x, safe.left()), max(safe.left(), safe.right() - width))
        y = min(max(y, safe.top()), max(safe.top(), safe.bottom() - height))
        self.center_v.setVisible(show_v)
        self.center_h.setVisible(show_h)
        return x, y, show_v, show_h

    def _emit_move(self, layer_id: str, x: float, y: float) -> None:
        if self.project is None:
            return
        self.layerMoved.emit(layer_id, x, y)

    def _hide_guides(self) -> None:
        self.center_v.hide()
        self.center_h.hide()

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

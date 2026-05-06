from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView

from core.project_model import Project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer

SNAP_THRESHOLD = 10


class LayerTextItem(QGraphicsTextItem):
    def __init__(self, layer: TextLayer, on_move: Callable[[str, float, float], None]) -> None:
        super().__init__(layer.text)
        self.layer = layer
        self.on_move = on_move
        self.setDefaultTextColor(QColor(layer.color.split("@")[0]))
        self.setFont(QFont("Arial", layer.font_size))
        self.setOpacity(layer.opacity)
        self.setRotation(layer.rotation)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(layer.x, layer.y)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        pos = self.pos()
        self.on_move(self.layer.layer_id, pos.x(), pos.y())
        super().mouseReleaseEvent(event)


class LayerStickerItem(QGraphicsPixmapItem):
    def __init__(self, layer: StickerLayer, on_move: Callable[[str, float, float], None]) -> None:
        pixmap = QPixmap(layer.file_path) if layer.file_path and Path(layer.file_path).exists() else QPixmap(160, 100)
        if pixmap.isNull():
            pixmap = QPixmap(160, 100)
        if layer.file_path == "" or pixmap.size().width() == 160 and pixmap.size().height() == 100:
            pixmap.fill(QColor("#ffcc00"))
        super().__init__(pixmap)
        self.layer = layer
        self.on_move = on_move
        self.setOpacity(layer.opacity)
        self.setScale(layer.scale)
        self.setRotation(layer.rotation)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(layer.x, layer.y)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        pos = self.pos()
        self.on_move(self.layer.layer_id, pos.x(), pos.y())
        super().mouseReleaseEvent(event)


class PreviewCanvas(QGraphicsView):
    layerMoved = Signal(str, float, float)
    filesDropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setAcceptDrops(True)
        self.project: Project | None = None
        self.video_item: QGraphicsRectItem | None = None
        self.center_v = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_h = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_v.hide()
        self.center_h.hide()

    def set_project(self, project: Project) -> None:
        self.project = project
        self.refresh()

    def refresh(self) -> None:
        self.scene.clear()
        if self.project is None:
            return
        self.video_item = self.scene.addRect(0, 0, self.project.width, self.project.height, QPen(QColor("#555")), QBrush(QColor("#111")))
        for layer in self.project.text_layers:
            self.scene.addItem(LayerTextItem(layer, self._snap_and_emit))
        for layer in self.project.sticker_layers:
            self.scene.addItem(LayerStickerItem(layer, self._snap_and_emit))
        self.center_v = self.scene.addLine(self.project.width / 2, 0, self.project.width / 2, self.project.height, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_h = self.scene.addLine(0, self.project.height / 2, self.project.width, self.project.height / 2, QPen(QColor("#00d1ff"), 1, Qt.PenStyle.DashLine))
        self.center_v.hide()
        self.center_h.hide()
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

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

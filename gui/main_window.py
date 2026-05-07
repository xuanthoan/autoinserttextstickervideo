from __future__ import annotations

import logging
import time
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QAbstractItemView,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.project_model import Project
from core.renderer import render_project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from core.text_template_engine import TextTemplate, TextTemplateEngine
from gui.batch_worker import BatchRenderWorker
from gui.preview_canvas import PreviewCanvas
from gui.timeline_panel import TimelinePanel
from utils.ffmpeg_helper import probe_video

LOGGER = logging.getLogger(__name__)
TEMPLATE_PATH = Path("templates/text_templates.json")
MOTION_PRESETS = ["none", "fade_in", "fade_out", "slide_left", "slide_right", "slide_up", "slide_down", "zoom_in", "zoom_out", "bounce", "pop"]
EASINGS = ["linear", "ease-in", "ease-out", "ease-in-out"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Insert Text Sticker Video")
        self.project = Project()
        self.video_queue: list[str] = []
        self.batch_thread: QThread | None = None
        self.batch_worker: BatchRenderWorker | None = None
        self.batch_started_at = 0.0
        self.selected_layer_id: str | None = None
        self.canvas = PreviewCanvas()
        self.timeline = TimelinePanel()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(33)
        self.preview_started_at = 0.0
        self.preview_start_time = 0.0
        self.setCentralWidget(self.canvas)
        self._build_toolbar()
        self._build_docks()
        self._connect_signals()
        self.template_engine = TextTemplateEngine.load(TEMPLATE_PATH)
        self._load_templates()
        self._refresh_all()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)
        actions = [
            ("Open Video", self.open_video),
            ("Add Videos", self.add_videos_to_queue),
            ("Import Folder", self.import_video_folder),
            ("Play", self.play_video),
            ("Pause", self.pause_video),
            ("Stop", self.stop_video),
            ("Add Text", self.add_text),
            ("Add Sticker", self.add_sticker),
            ("Save Project", self.save_project),
            ("Load Project", self.load_project),
            ("Export MP4", self.export_video),
            ("Render Batch", self.render_batch),
        ]
        for label, callback in actions:
            action = toolbar.addAction(label)
            action.triggered.connect(callback)

    def _build_docks(self) -> None:
        timeline_dock = QDockWidget("Timeline", self)
        timeline_dock.setWidget(self.timeline)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, timeline_dock)

        inspector_dock = QDockWidget("Edit Panel", self)
        self.inspector = QWidget()
        self.form = QFormLayout(self.inspector)
        self.layer_label = QLabel("No layer selected")
        self.text_input = QLineEdit()
        self.font_path = QLineEdit()
        self.font_size = QSpinBox()
        self.font_size.setRange(1, 400)
        self.stroke_enabled = QCheckBox()
        self.stroke_width = QSpinBox()
        self.stroke_width.setRange(0, 50)
        self.box_enabled = QCheckBox()
        self.box_padding = QSpinBox()
        self.box_padding.setRange(0, 200)
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0.0, 1.0)
        self.opacity.setSingleStep(0.05)
        self.x_value = QDoubleSpinBox()
        self.y_value = QDoubleSpinBox()
        self.scale_value = QDoubleSpinBox()
        self.scale_value.setRange(0.01, 20.0)
        self.scale_value.setSingleStep(0.05)
        self.rotation = QDoubleSpinBox()
        self.rotation.setRange(-360.0, 360.0)
        self.motion = QComboBox()
        self.motion.addItems(MOTION_PRESETS)
        self.motion_duration = QDoubleSpinBox()
        self.motion_duration.setRange(0.0, 60.0)
        self.motion_duration.setSingleStep(0.1)
        self.easing = QComboBox()
        self.easing.addItems(EASINGS)
        self.template_combo = QComboBox()
        self.save_template_button = QPushButton("Save Text Template")
        for spin in (self.x_value, self.y_value):
            spin.setRange(-10000.0, 10000.0)
        for label, widget in [
            ("Layer", self.layer_label),
            ("Text", self.text_input),
            ("Font path", self.font_path),
            ("Font size", self.font_size),
            ("Stroke", self.stroke_enabled),
            ("Stroke width", self.stroke_width),
            ("Background", self.box_enabled),
            ("Min background padding", self.box_padding),
            ("Opacity", self.opacity),
            ("X", self.x_value),
            ("Y", self.y_value),
            ("Sticker scale", self.scale_value),
            ("Rotation", self.rotation),
            ("Motion", self.motion),
            ("Motion duration", self.motion_duration),
            ("Easing", self.easing),
            ("Text template", self.template_combo),
            ("", self.save_template_button),
        ]:
            self.form.addRow(label, widget)
        inspector_dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, inspector_dock)

        self._build_batch_dock()
        self._build_template_dock()

        log_dock = QDockWidget("Render Log", self)
        log_dock.setWidget(self.log_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)


    def _build_batch_dock(self) -> None:
        batch_dock = QDockWidget("Batch Queue", self)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.video_queue_widget = QListWidget()
        self.video_queue_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.video_queue_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.video_queue_widget.itemDoubleClicked.connect(lambda item: self.load_video_from_queue(item.data(Qt.ItemDataRole.UserRole)))
        controls = QHBoxLayout()
        for label, callback in [
            ("Add", self.add_videos_to_queue),
            ("Remove", self.remove_selected_videos),
            ("Clear", self.clear_video_queue),
            ("Render All", self.render_batch),
            ("Cancel", self.cancel_batch),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            controls.addWidget(button)
        self.video_progress = QProgressBar()
        self.video_progress.setFormat("Current video: %p%")
        self.batch_progress = QProgressBar()
        self.batch_progress.setFormat("Batch: %v/%m")
        self.batch_eta_label = QLabel("Elapsed: 00:00 | ETA: --:--")
        layout.addWidget(QLabel("Drag videos here or use Add. Drag rows to reorder."))
        layout.addWidget(self.video_queue_widget)
        layout.addLayout(controls)
        layout.addWidget(self.video_progress)
        layout.addWidget(self.batch_progress)
        layout.addWidget(self.batch_eta_label)
        batch_dock.setWidget(panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, batch_dock)

    def _build_template_dock(self) -> None:
        template_dock = QDockWidget("Text Templates", self)
        panel = QWidget()
        self.template_layout = QVBoxLayout(panel)
        self.template_list = QListWidget()
        self.template_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.template_list.model().rowsMoved.connect(self.persist_template_order)
        self.template_layout.addWidget(QLabel("Enable templates for random batch assignment."))
        self.template_layout.addWidget(self.template_list)
        template_dock.setWidget(panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, template_dock)

    def refresh_template_panel(self) -> None:
        if not hasattr(self, "template_list"):
            return
        self.template_list.clear()
        for template in self.template_engine.templates:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            preview = QLabel("   ")
            preview.setStyleSheet(f"background-color: {template.background_color}; color: {template.text_color}; border-radius: 8px; padding: 8px; font-weight: 800;")
            enabled = QCheckBox()
            enabled.setChecked(template.enabled)
            enabled.toggled.connect(lambda checked, tid=template.template_id: self.set_template_enabled(tid, checked))
            name = QLabel(template.name)
            duplicate = QPushButton("Duplicate")
            duplicate.clicked.connect(lambda checked=False, tid=template.template_id: self.duplicate_template(tid))
            reset = QPushButton("Reset")
            reset.clicked.connect(lambda checked=False, tid=template.template_id: self.reset_template(tid))
            row_layout.addWidget(preview)
            row_layout.addWidget(enabled)
            row_layout.addWidget(name, 1)
            row_layout.addWidget(duplicate)
            row_layout.addWidget(reset)
            item.setSizeHint(row.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, row)

    def set_template_enabled(self, template_id: str, enabled: bool) -> None:
        self.template_engine.set_template_enabled(template_id, enabled)
        self.template_engine.save(TEMPLATE_PATH)
        self._load_templates()

    def duplicate_template(self, template_id: str) -> None:
        name, ok = QInputDialog.getText(self, "Duplicate template", "New template name")
        if not ok or not name:
            return
        self.template_engine.duplicate_template(template_id, name)
        self.template_engine.save(TEMPLATE_PATH)
        self._load_templates()

    def reset_template(self, template_id: str) -> None:
        defaults = TextTemplateEngine().templates
        for default in defaults:
            if default.template_id == template_id:
                self.template_engine.templates = [default if item.template_id == template_id else item for item in self.template_engine.templates]
                self.template_engine.save(TEMPLATE_PATH)
                self._load_templates()
                return

    def persist_template_order(self) -> None:
        if not hasattr(self, "template_list"):
            return
        ids = [self.template_list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.template_list.count())]
        self.template_engine.reorder_templates(ids)
        self.template_engine.save(TEMPLATE_PATH)
        self._load_templates()

    def _connect_signals(self) -> None:
        self.canvas.layerMoved.connect(self.move_layer)
        self.canvas.filesDropped.connect(self.handle_files_dropped)
        self.preview_timer.timeout.connect(self.advance_preview_time)
        self.timeline.layerTimingChanged.connect(self.change_timing)
        self.timeline.layerSelected.connect(self.select_layer)
        self.text_input.editingFinished.connect(self.apply_inspector)
        self.font_path.editingFinished.connect(self.apply_inspector)
        self.font_size.valueChanged.connect(self.apply_inspector)
        self.stroke_enabled.stateChanged.connect(self.apply_inspector)
        self.stroke_width.valueChanged.connect(self.apply_inspector)
        self.box_enabled.stateChanged.connect(self.apply_inspector)
        self.box_padding.valueChanged.connect(self.apply_inspector)
        self.opacity.valueChanged.connect(self.apply_inspector)
        self.x_value.valueChanged.connect(self.apply_inspector)
        self.y_value.valueChanged.connect(self.apply_inspector)
        self.scale_value.valueChanged.connect(self.apply_inspector)
        self.rotation.valueChanged.connect(self.apply_inspector)
        self.motion.currentTextChanged.connect(self.apply_inspector)
        self.motion_duration.valueChanged.connect(self.apply_inspector)
        self.easing.currentTextChanged.connect(self.apply_inspector)
        self.template_combo.currentTextChanged.connect(self.apply_template)
        self.save_template_button.clicked.connect(self.save_current_template)

    def _refresh_all(self) -> None:
        self.canvas.set_project(self.project)
        self.timeline.set_project(self.project)
        self.populate_inspector()

    def _layer_by_id(self, layer_id: str | None):  # type: ignore[no-untyped-def]
        for layer in self.project.all_layers():
            if layer.layer_id == layer_id:
                return layer
        return None


    def import_video_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Import video folder")
        if not folder:
            return
        paths = [str(path) for path in sorted(Path(folder).iterdir()) if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi"}]
        self._add_queue_paths(paths)
        if paths and not self.project.video_path:
            self.load_video_from_queue(paths[0])

    def add_videos_to_queue(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add videos to batch", "", "Video (*.mp4 *.mov *.mkv *.avi)")
        self._add_queue_paths(paths)
        if paths and not self.project.video_path:
            self.load_video_from_queue(paths[0])

    def _add_queue_paths(self, paths: list[str]) -> None:
        video_paths = [str(Path(path)) for path in paths if Path(path).suffix.lower() in {".mp4", ".mov", ".mkv", ".avi"}]
        existing = set(self.video_queue)
        for path in video_paths:
            if path in existing:
                continue
            self.video_queue.append(path)
            if hasattr(self, "video_queue_widget"):
                item = QListWidgetItem(Path(path).name)
                item.setToolTip(path)
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.video_queue_widget.addItem(item)
            existing.add(path)
        self.batch_progress.setMaximum(max(1, len(self.video_queue))) if hasattr(self, "batch_progress") else None

    def _queue_from_widget(self) -> list[str]:
        if not hasattr(self, "video_queue_widget"):
            return list(self.video_queue)
        self.video_queue = [self.video_queue_widget.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.video_queue_widget.count())]
        return list(self.video_queue)

    def remove_selected_videos(self) -> None:
        for item in self.video_queue_widget.selectedItems():
            self.video_queue_widget.takeItem(self.video_queue_widget.row(item))
        self._queue_from_widget()

    def clear_video_queue(self) -> None:
        self.video_queue.clear()
        self.video_queue_widget.clear()
        self.batch_progress.setValue(0)
        self.video_progress.setValue(0)

    def load_video_from_queue(self, path: str) -> None:
        if not path:
            return
        try:
            metadata = probe_video(path)
            self.project.video_path = path
            self.project.width = int(metadata["width"])
            self.project.height = int(metadata["height"])
            self.project.duration = float(metadata["duration"])
            self._set_player_source(path)
            self._refresh_all()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "FFprobe error", str(exc))

    def render_batch(self) -> None:
        queue = self._queue_from_widget()
        if not queue:
            QMessageBox.warning(self, "Empty batch", "Add one or more videos to the batch queue first.")
            return
        if self.batch_thread is not None:
            QMessageBox.information(self, "Batch running", "A batch render is already running.")
            return
        if not self.template_engine.enabled_templates():
            QMessageBox.warning(self, "No templates enabled", "Enable at least one text template before batch rendering.")
            return
        if not self.project.text_layers:
            self.add_text()
        self.log_view.clear()
        self.video_progress.setRange(0, 0)
        self.batch_started_at = time.monotonic()
        self.batch_progress.setRange(0, len(queue))
        self.batch_progress.setValue(0)
        self.batch_thread = QThread(self)
        self.batch_worker = BatchRenderWorker(self.project, queue, self.template_engine)
        self.batch_worker.moveToThread(self.batch_thread)
        self.batch_thread.started.connect(self.batch_worker.run)
        self.batch_worker.logLine.connect(self.log_view.append)
        self.batch_worker.videoStarted.connect(self.on_batch_video_started)
        self.batch_worker.videoFinished.connect(self.on_batch_video_finished)
        self.batch_worker.videoFailed.connect(self.on_batch_video_failed)
        self.batch_worker.overallProgress.connect(self.on_batch_progress)
        self.batch_worker.finished.connect(self.on_batch_finished)
        self.batch_worker.finished.connect(self.batch_thread.quit)
        self.batch_worker.finished.connect(self.batch_worker.deleteLater)
        self.batch_thread.finished.connect(self.batch_thread.deleteLater)
        self.batch_thread.start()

    def cancel_batch(self) -> None:
        if self.batch_worker is not None:
            self.batch_worker.cancel()
            self.log_view.append("Cancel requested; current render will finish before stopping.")

    def on_batch_video_started(self, index: int, total: int, path: str) -> None:
        self.video_progress.setRange(0, 0)
        self.log_view.append(f"Starting {index}/{total}: {Path(path).name}")

    def on_batch_video_finished(self, index: int, total: int, output_path: str) -> None:
        self.video_progress.setRange(0, 100)
        self.video_progress.setValue(100)
        self.log_view.append(f"Finished {index}/{total}: {output_path}")

    def on_batch_video_failed(self, index: int, total: int, path: str, error: str) -> None:
        self.video_progress.setRange(0, 100)
        self.video_progress.setValue(0)
        self.log_view.append(f"Failed {index}/{total}: {path}\n{error}")

    def on_batch_progress(self, done: int, total: int) -> None:
        self.batch_progress.setMaximum(total)
        self.batch_progress.setValue(done)
        elapsed = max(0.0, time.monotonic() - self.batch_started_at)
        eta = 0.0 if done <= 0 else elapsed / done * max(0, total - done)
        self.batch_eta_label.setText(f"Elapsed: {self._fmt_seconds(elapsed)} | ETA: {self._fmt_seconds(eta)}")

    def _fmt_seconds(self, seconds: float) -> str:
        total = round(seconds)
        return f"{total // 60:02d}:{total % 60:02d}"

    def on_batch_finished(self) -> None:
        self.video_progress.setRange(0, 100)
        self.video_progress.setValue(0)
        self.log_view.append("Batch render complete.")
        self.batch_thread = None
        self.batch_worker = None

    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open video", "", "Video (*.mp4 *.mov *.mkv *.avi)")
        if not path:
            return
        try:
            metadata = probe_video(path)
            self.project.video_path = path
            self.project.width = int(metadata["width"])
            self.project.height = int(metadata["height"])
            self.project.duration = float(metadata["duration"])
            self._set_player_source(path)
            self._add_queue_paths([path])
            self._refresh_all()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "FFprobe error", str(exc))

    def add_text(self) -> None:
        layer = self.project.add_text_layer(TextLayer(x=self.project.width / 2 - 150, y=self.project.height / 2, stroke_enabled=False, stroke_width=0))
        self.template_engine.apply_to_layer(layer, self.template_engine.by_id_or_name("orange-white"), permanent=False)
        self.selected_layer_id = layer.layer_id
        self._refresh_all()

    def add_sticker(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose sticker", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        layer = self.project.add_sticker_layer(StickerLayer(file_path=path, x=self.project.width / 2, y=self.project.height / 2))
        self.selected_layer_id = layer.layer_id
        self._refresh_all()

    def handle_files_dropped(self, paths: list[str]) -> None:
        for path in paths:
            suffix = Path(path).suffix.lower()
            if suffix in {".mp4", ".mov", ".mkv", ".avi"}:
                self.project.video_path = path
                try:
                    metadata = probe_video(path)
                    self.project.width = int(metadata["width"])
                    self.project.height = int(metadata["height"])
                    self.project.duration = float(metadata["duration"])
                    self._set_player_source(path)
                    self._add_queue_paths([path])
                except Exception as exc:  # noqa: BLE001
                    self.log_view.append(f"Probe failed: {exc}")
            elif suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                self.project.add_sticker_layer(StickerLayer(file_path=path))
        self._refresh_all()

    def select_layer(self, layer_id: str) -> None:
        self.selected_layer_id = layer_id
        self.populate_inspector()

    def move_layer(self, layer_id: str, x: float, y: float) -> None:
        layer = self._layer_by_id(layer_id)
        if layer is None:
            return
        layer.x = x
        layer.y = y
        self.selected_layer_id = layer_id
        self._refresh_all()

    def change_timing(self, layer_id: str, start: float, end: float) -> None:
        layer = self._layer_by_id(layer_id)
        if layer is None:
            return
        layer.start_time = min(start, end)
        layer.end_time = max(start, end)
        self.canvas.refresh_overlays()

    def populate_inspector(self) -> None:
        layer = self._layer_by_id(self.selected_layer_id)
        enabled = layer is not None
        for widget in self.inspector.findChildren(QWidget):
            widget.blockSignals(True)
            widget.setEnabled(enabled)
        if layer is None:
            self.layer_label.setText("No layer selected")
        else:
            self.layer_label.setText(f"{layer.kind}: {layer.layer_id}")
            self.x_value.setValue(layer.x)
            self.y_value.setValue(layer.y)
            self.opacity.setValue(layer.opacity)
            self.rotation.setValue(layer.rotation)
            self.motion.setCurrentText(layer.motion_preset)
            self.motion_duration.setValue(layer.motion_duration)
            self.easing.setCurrentText(layer.easing)
            if isinstance(layer, TextLayer):
                self.text_input.setText(layer.text)
                self.font_path.setText(layer.font_path)
                self.font_size.setValue(layer.font_size)
                self.template_combo.setCurrentText(self.template_engine.by_id_or_name(layer.template_id).name)
                self.stroke_enabled.setChecked(layer.stroke_enabled)
                self.stroke_width.setValue(layer.stroke_width)
                self.box_enabled.setChecked(layer.box_enabled)
                self.box_padding.setValue(layer.box_padding)
                self.scale_value.setValue(1.0)
            if isinstance(layer, StickerLayer):
                self.text_input.setText(Path(layer.file_path).name)
                self.font_path.clear()
                self.scale_value.setValue(layer.scale)
        for widget in self.inspector.findChildren(QWidget):
            widget.blockSignals(False)
            widget.setEnabled(enabled)

    def apply_inspector(self) -> None:
        layer = self._layer_by_id(self.selected_layer_id)
        if layer is None:
            return
        layer.x = self.x_value.value()
        layer.y = self.y_value.value()
        layer.opacity = self.opacity.value()
        layer.rotation = self.rotation.value()
        layer.motion_preset = self.motion.currentText()
        layer.motion_duration = self.motion_duration.value()
        layer.easing = self.easing.currentText()
        if isinstance(layer, TextLayer):
            layer.text = self.text_input.text()
            layer.font_path = self.font_path.text()
            layer.font_size = self.font_size.value()
            layer.stroke_enabled = self.stroke_enabled.isChecked()
            layer.stroke_width = self.stroke_width.value() if layer.stroke_enabled else 0
            layer.box_enabled = self.box_enabled.isChecked()
            layer.box_padding = self.box_padding.value()
        if isinstance(layer, StickerLayer):
            layer.scale = self.scale_value.value()
        self.canvas.refresh_overlays()
        self.timeline.refresh()

    def _set_player_source(self, path: str) -> None:
        del path
        self.stop_video()

    def play_video(self) -> None:
        if not self.project.video_path:
            QMessageBox.warning(self, "Missing video", "Open a source video first.")
            return
        self.preview_start_time = self.canvas.current_time
        self.preview_started_at = time.monotonic()
        self.preview_timer.start()

    def pause_video(self) -> None:
        self.preview_timer.stop()

    def stop_video(self) -> None:
        self.preview_timer.stop()
        self.canvas.set_time(0.0)

    def advance_preview_time(self) -> None:
        duration = max(self.project.duration, 0.1)
        elapsed = time.monotonic() - self.preview_started_at
        current = (self.preview_start_time + elapsed) % duration
        self.canvas.set_time(current)

    def _load_templates(self) -> None:
        TEMPLATE_PATH.parent.mkdir(exist_ok=True)
        self.template_engine = TextTemplateEngine.load(TEMPLATE_PATH)
        self.canvas.template_engine = self.template_engine
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("")
        self.template_combo.addItems([template.name for template in self.template_engine.enabled_templates()])
        self.template_combo.blockSignals(False)
        self.refresh_template_panel()

    def apply_template(self, name: str) -> None:
        layer = self._layer_by_id(self.selected_layer_id)
        if not name or not isinstance(layer, TextLayer):
            return
        template = self.template_engine.by_id_or_name(name)
        self.template_engine.apply_to_layer(layer, template, permanent=False)
        self._refresh_all()

    def save_current_template(self) -> None:
        layer = self._layer_by_id(self.selected_layer_id)
        if not isinstance(layer, TextLayer):
            return
        name, ok = QInputDialog.getText(self, "Template name", "Name")
        if not ok or not name:
            return
        template_id = name.lower().replace(" ", "-")
        template = TextTemplate(
            template_id=template_id,
            name=name,
            text_color=layer.color,
            background_color=layer.box_color,
            font_family=layer.font_family,
            font_weight=layer.font_weight,
            border_radius_multiplier=0.35,
            horizontal_padding_multiplier=0.8,
            vertical_padding_multiplier=0.45,
            line_spacing_multiplier=0.25,
            shadow_blur_multiplier=0.15,
            enabled=True,
            auto_uppercase=layer.auto_uppercase,
        )
        self.template_engine.templates = [item for item in self.template_engine.templates if item.template_id != template_id]
        self.template_engine.templates.append(template)
        self.template_engine.save(TEMPLATE_PATH)
        self._load_templates()

    def save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save project", "project.json", "JSON (*.json)")
        if path:
            self.project.save(path)

    def load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load project", "", "JSON (*.json)")
        if path:
            self.project = Project.load(path)
            self.selected_layer_id = None
            if self.project.video_path:
                self._set_player_source(self.project.video_path)
            self._refresh_all()

    def export_video(self) -> None:
        if not self.project.video_path:
            QMessageBox.warning(self, "Missing video", "Open a source video first.")
            return
        input_path = Path(self.project.video_path)
        output_dir = input_path.parent / "output"
        output_dir.mkdir(exist_ok=True)
        path = output_dir / f"{input_path.stem}_output.mp4"
        self.log_view.clear()
        self.log_view.append(f"Exporting to: {path}")
        try:
            command = render_project(self.project, str(path), self.log_view.append)
            self.log_view.append(command.shell_string())
            QMessageBox.information(self, "Export complete", str(path))
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Export failed")
            QMessageBox.critical(self, "Export failed", str(exc))

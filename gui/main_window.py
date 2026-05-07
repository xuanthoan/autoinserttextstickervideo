from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolBar,
    QWidget,
)

from core.project_model import Project
from core.renderer import render_project
from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer
from core.text_template_engine import TextTemplate, TextTemplateEngine
from gui.preview_canvas import PreviewCanvas
from gui.timeline_panel import TimelinePanel
from utils.ffmpeg_helper import probe_video

LOGGER = logging.getLogger(__name__)
TEMPLATE_PATH = Path("templates/text_templates.json")
MOTION_PRESETS = ["none", "fade", "slide", "zoom", "bounce"]
EASINGS = ["linear", "ease-in", "ease-out", "ease-in-out"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Insert Text Sticker Video")
        self.project = Project()
        self.selected_layer_id: str | None = None
        self.canvas = PreviewCanvas()
        self.timeline = TimelinePanel()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
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
            ("Play", self.play_video),
            ("Pause", self.pause_video),
            ("Stop", self.stop_video),
            ("Add Text", self.add_text),
            ("Add Sticker", self.add_sticker),
            ("Save Project", self.save_project),
            ("Load Project", self.load_project),
            ("Export MP4", self.export_video),
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
        self.color_button = QPushButton("Choose")
        self.stroke_color = QLineEdit("black")
        self.stroke_color_button = QPushButton("Choose stroke")
        self.stroke_width = QSpinBox()
        self.stroke_width.setRange(0, 50)
        self.box_enabled = QCheckBox()
        self.box_color = QLineEdit("black@0.5")
        self.box_color_button = QPushButton("Choose background")
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
            ("Text color", self.color_button),
            ("Stroke color", self.stroke_color),
            ("", self.stroke_color_button),
            ("Stroke width", self.stroke_width),
            ("Background", self.box_enabled),
            ("Background color", self.box_color),
            ("", self.box_color_button),
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

        log_dock = QDockWidget("Render Log", self)
        log_dock.setWidget(self.log_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)

    def _connect_signals(self) -> None:
        self.canvas.layerMoved.connect(self.move_layer)
        self.canvas.filesDropped.connect(self.handle_files_dropped)
        self.canvas.videoOutputChanged.connect(self.player.setVideoOutput)
        self.player.positionChanged.connect(self.update_preview_time)
        self.timeline.layerTimingChanged.connect(self.change_timing)
        self.timeline.layerSelected.connect(self.select_layer)
        self.text_input.editingFinished.connect(self.apply_inspector)
        self.font_path.editingFinished.connect(self.apply_inspector)
        self.font_size.valueChanged.connect(self.apply_inspector)
        self.stroke_color.editingFinished.connect(self.apply_inspector)
        self.stroke_color_button.clicked.connect(self.choose_stroke_color)
        self.stroke_width.valueChanged.connect(self.apply_inspector)
        self.box_enabled.stateChanged.connect(self.apply_inspector)
        self.box_color.editingFinished.connect(self.apply_inspector)
        self.box_color_button.clicked.connect(self.choose_box_color)
        self.box_padding.valueChanged.connect(self.apply_inspector)
        self.opacity.valueChanged.connect(self.apply_inspector)
        self.x_value.valueChanged.connect(self.apply_inspector)
        self.y_value.valueChanged.connect(self.apply_inspector)
        self.scale_value.valueChanged.connect(self.apply_inspector)
        self.rotation.valueChanged.connect(self.apply_inspector)
        self.motion.currentTextChanged.connect(self.apply_inspector)
        self.motion_duration.valueChanged.connect(self.apply_inspector)
        self.easing.currentTextChanged.connect(self.apply_inspector)
        self.color_button.clicked.connect(self.choose_text_color)
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
            self._refresh_all()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "FFprobe error", str(exc))

    def add_text(self) -> None:
        layer = self.project.add_text_layer(TextLayer(x=self.project.width / 2 - 150, y=self.project.height / 2))
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
                self.stroke_color.setText(layer.stroke_color)
                self.stroke_width.setValue(layer.stroke_width)
                self.box_enabled.setChecked(layer.box_enabled)
                self.box_color.setText(layer.box_color)
                self.box_padding.setValue(layer.box_padding)
                self.color_button.setStyleSheet(f"background-color: {layer.color}")
                self.stroke_color_button.setStyleSheet(f"background-color: {layer.stroke_color}")
                self.box_color_button.setStyleSheet(f"background-color: {layer.box_color.split('@', 1)[0]}")
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
            layer.stroke_color = self.stroke_color.text()
            layer.stroke_width = self.stroke_width.value()
            layer.box_enabled = self.box_enabled.isChecked()
            layer.box_color = self.box_color.text()
            layer.box_padding = self.box_padding.value()
        if isinstance(layer, StickerLayer):
            layer.scale = self.scale_value.value()
        self.canvas.refresh_overlays()
        self.timeline.refresh()

    def choose_text_color(self) -> None:
        layer = self._layer_by_id(self.selected_layer_id)
        if not isinstance(layer, TextLayer):
            return
        color = QColorDialog.getColor()
        if color.isValid():
            layer.color = color.name()
            self.color_button.setStyleSheet(f"background-color: {layer.color}")
            self.canvas.refresh_overlays()


    def choose_stroke_color(self) -> None:
        layer = self._layer_by_id(self.selected_layer_id)
        if not isinstance(layer, TextLayer):
            return
        color = QColorDialog.getColor()
        if color.isValid():
            layer.stroke_color = color.name()
            self.stroke_color.setText(layer.stroke_color)
            self.stroke_color_button.setStyleSheet(f"background-color: {layer.stroke_color}")
            self.canvas.refresh_overlays()

    def choose_box_color(self) -> None:
        layer = self._layer_by_id(self.selected_layer_id)
        if not isinstance(layer, TextLayer):
            return
        color = QColorDialog.getColor()
        if color.isValid():
            alpha = 0.5
            if "@" in layer.box_color:
                try:
                    alpha = float(layer.box_color.split("@", 1)[1])
                except ValueError:
                    alpha = 0.5
            layer.box_color = f"{color.name()}@{alpha}"
            self.box_color.setText(layer.box_color)
            self.box_color_button.setStyleSheet(f"background-color: {color.name()}")
            self.canvas.refresh_overlays()

    def _set_player_source(self, path: str) -> None:
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(path))
        if self.canvas.video_item is not None:
            self.player.setVideoOutput(self.canvas.video_item)

    def play_video(self) -> None:
        if not self.project.video_path:
            QMessageBox.warning(self, "Missing video", "Open a source video first.")
            return
        self.player.play()

    def pause_video(self) -> None:
        self.player.pause()

    def stop_video(self) -> None:
        self.player.stop()
        self.canvas.set_time(0.0)

    def update_preview_time(self, position_ms: int) -> None:
        self.canvas.set_time(position_ms / 1000.0)

    def _load_templates(self) -> None:
        TEMPLATE_PATH.parent.mkdir(exist_ok=True)
        self.template_engine = TextTemplateEngine.load(TEMPLATE_PATH)
        self.canvas.template_engine = self.template_engine
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("")
        self.template_combo.addItems([template.name for template in self.template_engine.enabled_templates()])
        self.template_combo.blockSignals(False)

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

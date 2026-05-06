from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QGridLayout, QLabel, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget

from core.project_model import Project

SLIDER_STEPS = 1000


class TimelinePanel(QWidget):
    layerTimingChanged = Signal(str, float, float)
    layerSelected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.rows = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.content)
        self.rows.addWidget(QLabel("Timeline"))
        self.rows.addWidget(self.scroll)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.refresh()

    def _slider_to_time(self, value: int) -> float:
        duration = max(self.project.duration if self.project else 0.0, 1.0)
        return duration * value / SLIDER_STEPS

    def _time_to_slider(self, value: float) -> int:
        duration = max(self.project.duration if self.project else 0.0, 1.0)
        return max(0, min(SLIDER_STEPS, round(value / duration * SLIDER_STEPS)))

    def refresh(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if self.project is None:
            return
        self.grid.addWidget(QLabel("Layer"), 0, 0)
        self.grid.addWidget(QLabel("Start"), 0, 1)
        self.grid.addWidget(QLabel("End"), 0, 2)
        self.grid.addWidget(QLabel("Start bar"), 0, 3)
        self.grid.addWidget(QLabel("End bar"), 0, 4)
        for row, layer in enumerate(self.project.all_layers(), start=1):
            button = QPushButton(layer.text[:18] if layer.kind == "text" else "Sticker")
            button.clicked.connect(lambda checked=False, layer_id=layer.layer_id: self.layerSelected.emit(layer_id))
            start = QDoubleSpinBox()
            end = QDoubleSpinBox()
            start_slider = QSlider(Qt.Orientation.Horizontal)
            end_slider = QSlider(Qt.Orientation.Horizontal)
            for spin in (start, end):
                spin.setRange(0.0, max(36000.0, self.project.duration))
                spin.setSingleStep(0.1)
                spin.setDecimals(2)
            for slider in (start_slider, end_slider):
                slider.setRange(0, SLIDER_STEPS)
            start.setValue(layer.start_time)
            end.setValue(layer.end_time)
            start_slider.setValue(self._time_to_slider(layer.start_time))
            end_slider.setValue(self._time_to_slider(layer.end_time))
            start.valueChanged.connect(lambda value, lid=layer.layer_id, end_spin=end: self.layerTimingChanged.emit(lid, value, end_spin.value()))
            end.valueChanged.connect(lambda value, lid=layer.layer_id, start_spin=start: self.layerTimingChanged.emit(lid, start_spin.value(), value))
            start_slider.valueChanged.connect(lambda value, lid=layer.layer_id, end_spin=end: self.layerTimingChanged.emit(lid, self._slider_to_time(value), end_spin.value()))
            end_slider.valueChanged.connect(lambda value, lid=layer.layer_id, start_spin=start: self.layerTimingChanged.emit(lid, start_spin.value(), self._slider_to_time(value)))
            self.grid.addWidget(button, row, 0)
            self.grid.addWidget(start, row, 1)
            self.grid.addWidget(end, row, 2)
            self.grid.addWidget(start_slider, row, 3)
            self.grid.addWidget(end_slider, row, 4)
        self.grid.setRowStretch(len(self.project.all_layers()) + 1, 1)

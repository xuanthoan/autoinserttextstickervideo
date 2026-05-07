from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from core.text_template_engine import TextTemplate, TextTemplateEngine


class TemplatePanel(QWidget):
    templateToggled = Signal(str, bool)
    duplicateRequested = Signal(str)
    resetRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.list_widget = QListWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)

    def set_templates(self, engine: TextTemplateEngine) -> None:
        self.list_widget.clear()
        for template in engine.templates:
            self.add_template(template)

    def add_template(self, template: TextTemplate) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, template.template_id)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        preview = QLabel("   ")
        preview.setStyleSheet(f"background:{template.background_color}; color:{template.text_color}; border-radius:8px; padding:8px;")
        enabled = QCheckBox()
        enabled.setChecked(template.enabled)
        enabled.toggled.connect(lambda checked, tid=template.template_id: self.templateToggled.emit(tid, checked))
        duplicate = QPushButton("Duplicate")
        duplicate.clicked.connect(lambda checked=False, tid=template.template_id: self.duplicateRequested.emit(tid))
        reset = QPushButton("Reset")
        reset.clicked.connect(lambda checked=False, tid=template.template_id: self.resetRequested.emit(tid))
        row_layout.addWidget(preview)
        row_layout.addWidget(enabled)
        row_layout.addWidget(QLabel(template.name), 1)
        row_layout.addWidget(duplicate)
        row_layout.addWidget(reset)
        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

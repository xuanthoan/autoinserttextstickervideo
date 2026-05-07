from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import random
import re
from pathlib import Path
from typing import Any, Iterable

from core.text_layer import TextLayer

MIN_FONT_SIZE = 18
DEFAULT_FONT_FAMILY = "Montserrat ExtraBold"
FALLBACK_FONT_FAMILY = "Poppins Bold"


@dataclass
class TextTemplate:
    template_id: str
    name: str
    text_color: str
    background_color: str
    font_family: str = DEFAULT_FONT_FAMILY
    fallback_font_family: str = FALLBACK_FONT_FAMILY
    font_weight: int = 800
    border_radius_multiplier: float = 0.35
    horizontal_padding_multiplier: float = 0.8
    vertical_padding_multiplier: float = 0.45
    line_spacing_multiplier: float = 0.25
    shadow_blur_multiplier: float = 0.15
    enabled: bool = True
    auto_uppercase: bool = False
    shadow_enabled: bool = True
    shadow_color: str = "#000000@0.22"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TextTemplate":
        return cls(
            template_id=str(payload.get("templateId") or payload.get("template_id") or payload.get("name", "template").lower().replace(" ", "-")),
            name=str(payload.get("name", "Template")),
            text_color=str(payload.get("textColor") or payload.get("text_color") or payload.get("color", "#FFFFFF")),
            background_color=str(payload.get("backgroundColor") or payload.get("background_color") or payload.get("box_color", "#000000")),
            font_family=str(payload.get("fontFamily") or payload.get("font_family") or DEFAULT_FONT_FAMILY),
            fallback_font_family=str(payload.get("fallbackFontFamily") or payload.get("fallback_font_family") or FALLBACK_FONT_FAMILY),
            font_weight=int(payload.get("fontWeight") or payload.get("font_weight") or 800),
            border_radius_multiplier=float(payload.get("borderRadiusMultiplier") or payload.get("border_radius_multiplier") or 0.35),
            horizontal_padding_multiplier=float(payload.get("horizontalPaddingMultiplier") or payload.get("horizontal_padding_multiplier") or payload.get("paddingMultiplier") or 0.8),
            vertical_padding_multiplier=float(payload.get("verticalPaddingMultiplier") or payload.get("vertical_padding_multiplier") or 0.45),
            line_spacing_multiplier=float(payload.get("lineSpacingMultiplier") or payload.get("line_spacing_multiplier") or 0.25),
            shadow_blur_multiplier=float(payload.get("shadowBlurMultiplier") or payload.get("shadow_blur_multiplier") or 0.15),
            enabled=bool(payload.get("enabled", True)),
            auto_uppercase=bool(payload.get("autoUppercase") or payload.get("auto_uppercase") or False),
            shadow_enabled=bool(payload.get("shadowEnabled", payload.get("shadow_enabled", True))),
            shadow_color=str(payload.get("shadowColor") or payload.get("shadow_color") or "#000000@0.22"),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["templateId"] = data.pop("template_id")
        data["textColor"] = data.pop("text_color")
        data["backgroundColor"] = data.pop("background_color")
        data["fontFamily"] = data.pop("font_family")
        data["fallbackFontFamily"] = data.pop("fallback_font_family")
        data["fontWeight"] = data.pop("font_weight")
        data["borderRadiusMultiplier"] = data.pop("border_radius_multiplier")
        data["horizontalPaddingMultiplier"] = data.pop("horizontal_padding_multiplier")
        data["verticalPaddingMultiplier"] = data.pop("vertical_padding_multiplier")
        data["lineSpacingMultiplier"] = data.pop("line_spacing_multiplier")
        data["shadowBlurMultiplier"] = data.pop("shadow_blur_multiplier")
        data["autoUppercase"] = data.pop("auto_uppercase")
        data["shadowEnabled"] = data.pop("shadow_enabled")
        data["shadowColor"] = data.pop("shadow_color")
        return data


@dataclass(frozen=True)
class SafeArea:
    top: int
    bottom: int
    left: int
    right: int


@dataclass(frozen=True)
class TextLayout:
    text: str
    lines: list[str]
    font_size: int
    horizontal_padding: int
    vertical_padding: int
    border_radius: int
    line_spacing: int
    shadow_blur: int
    max_text_width: int
    text_width: int
    text_height: int
    box_width: int
    box_height: int
    x: int
    y: int
    font_family: str
    font_weight: int


@dataclass(frozen=True)
class TextRenderAsset:
    path: Path
    x: int
    y: int
    width: int
    height: int
    layout: TextLayout


DEFAULT_TEMPLATES: list[TextTemplate] = [
    TextTemplate("orange-white", "Orange White", "#FFFFFF", "#F57C4D"),
    TextTemplate("white-black", "White Black", "#000000", "#FFFFFF"),
    TextTemplate("pink-white", "Pink White", "#FFFFFF", "#FF3FA4"),
    TextTemplate("red-white", "Red White", "#FFFFFF", "#FF4B4B"),
    TextTemplate("yellow-white", "Yellow White", "#FFFFFF", "#EFCB39"),
    TextTemplate("pastel-pink", "Pastel Pink", "#F0537A", "#FFD7DF"),
    TextTemplate("green-white", "Green White", "#FFFFFF", "#8BC34A"),
]


def safe_area(width: int, height: int) -> SafeArea:
    return SafeArea(
        top=round(height * 0.08),
        bottom=round(height * 0.16),
        left=round(width * 0.05),
        right=round(width * 0.05),
    )


def max_text_width(width: int) -> int:
    return round(width * 0.78)


def spacing_for_font(font_size: int, template: TextTemplate) -> tuple[int, int, int, int, int]:
    return (
        round(font_size * template.horizontal_padding_multiplier),
        round(font_size * template.vertical_padding_multiplier),
        round(font_size * template.border_radius_multiplier),
        round(font_size * template.line_spacing_multiplier),
        round(font_size * template.shadow_blur_multiplier),
    )


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _measure_line(line: str, font_size: int) -> int:
    wide_chars = sum(1 for char in line if ord(char) > 127)
    return max(1, round((len(line) + wide_chars * 0.3) * font_size * 0.58))


def _line_height(font_size: int) -> int:
    return round(font_size * 1.05)


def _wrap_text(text: str, font_size: int, max_width: int) -> list[str]:
    source_lines = text.splitlines() or [text]
    wrapped: list[str] = []
    for source_line in source_lines:
        words = _words(source_line)
        if not words:
            wrapped.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _measure_line(candidate, font_size) <= max_width:
                current = candidate
            else:
                wrapped.append(current)
                current = word
        wrapped.append(current)
    if len(wrapped) >= 2 and len(wrapped[-1].split()) == 1 and len(wrapped[-2].split()) > 1:
        previous_words = wrapped[-2].split()
        moved = previous_words.pop()
        candidate_prev = " ".join(previous_words)
        candidate_last = f"{moved} {wrapped[-1]}"
        if candidate_prev and _measure_line(candidate_last, font_size) <= max_width:
            wrapped[-2] = candidate_prev
            wrapped[-1] = candidate_last
    return wrapped


def _fit_text(text: str, requested_font_size: int, max_width: int) -> tuple[int, list[str], int, int]:
    font_size = max(requested_font_size, MIN_FONT_SIZE)
    while font_size >= MIN_FONT_SIZE:
        lines = _wrap_text(text, font_size, max_width)
        text_width = max((_measure_line(line, font_size) for line in lines), default=1)
        line_spacing = round(font_size * 0.25)
        text_height = len(lines) * _line_height(font_size) + max(0, len(lines) - 1) * line_spacing
        if text_width <= max_width:
            return font_size, lines, text_width, text_height
        font_size -= 1
    lines = _wrap_text(text, MIN_FONT_SIZE, max_width)
    text_width = min(max((_measure_line(line, MIN_FONT_SIZE) for line in lines), default=1), max_width)
    text_height = len(lines) * _line_height(MIN_FONT_SIZE) + max(0, len(lines) - 1) * round(MIN_FONT_SIZE * 0.25)
    return MIN_FONT_SIZE, lines, text_width, text_height


class TextTemplateEngine:
    def __init__(self, templates: Iterable[TextTemplate] | None = None) -> None:
        self.templates = list(DEFAULT_TEMPLATES if templates is None else templates)

    @classmethod
    def load(cls, path: str | Path) -> "TextTemplateEngine":
        file_path = Path(path)
        if not file_path.exists():
            engine = cls()
            engine.save(file_path)
            return engine
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        items = payload.get("templates", payload) if isinstance(payload, dict) else payload
        if isinstance(items, dict):
            templates = [TextTemplate.from_dict({"templateId": key, "name": key, **value}) for key, value in items.items()]
        else:
            templates = [TextTemplate.from_dict(item) for item in items]
        return cls(templates)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        payload = {"templates": [template.to_dict() for template in self.templates]}
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def enabled_templates(self) -> list[TextTemplate]:
        return [template for template in self.templates if template.enabled]

    def by_id_or_name(self, value: str | None) -> TextTemplate:
        candidates = self.templates or DEFAULT_TEMPLATES
        if value:
            for template in candidates:
                if template.template_id == value or template.name == value:
                    return template
        enabled = self.enabled_templates()
        return (enabled or candidates)[0]

    def duplicate_template(self, template_id: str, new_name: str) -> TextTemplate:
        original = self.by_id_or_name(template_id)
        duplicate = TextTemplate.from_dict(original.to_dict())
        duplicate.name = new_name
        duplicate.template_id = re.sub(r"[^a-z0-9]+", "-", new_name.lower()).strip("-") or f"{original.template_id}-copy"
        self.templates.append(duplicate)
        return duplicate

    def reset_to_defaults(self) -> None:
        self.templates = list(DEFAULT_TEMPLATES)


    def set_template_enabled(self, template_id: str, enabled: bool) -> None:
        self.by_id_or_name(template_id).enabled = enabled

    def reorder_templates(self, template_ids: list[str]) -> None:
        by_id = {template.template_id: template for template in self.templates}
        ordered = [by_id[template_id] for template_id in template_ids if template_id in by_id]
        ordered.extend(template for template in self.templates if template.template_id not in template_ids)
        self.templates = ordered

    def export_pack(self, path: str | Path, template_ids: list[str] | None = None) -> None:
        selected_ids = set(template_ids or [])
        templates = [template for template in self.templates if not selected_ids or template.template_id in selected_ids]
        Path(path).write_text(json.dumps({"templates": [template.to_dict() for template in templates]}, indent=2), encoding="utf-8")

    def import_pack(self, path: str | Path, replace_existing: bool = False) -> None:
        imported = TextTemplateEngine.load(path).templates
        if replace_existing:
            self.templates = imported
            return
        existing = {template.template_id for template in self.templates}
        self.templates.extend(template for template in imported if template.template_id not in existing)

    def preview_metadata(self, template_id: str) -> dict[str, str]:
        template = self.by_id_or_name(template_id)
        return {
            "templateId": template.template_id,
            "name": template.name,
            "textColor": template.text_color,
            "backgroundColor": template.background_color,
            "fontFamily": template.font_family,
        }

    def assign_templates_to_videos(self, video_paths: list[str], selected_template_ids: list[str]) -> dict[str, TextTemplate]:
        selected = [self.by_id_or_name(template_id) for template_id in selected_template_ids] or self.enabled_templates() or DEFAULT_TEMPLATES
        assignments: dict[str, TextTemplate] = {}
        last_id = ""
        for video_path in video_paths:
            choices = [template for template in selected if template.template_id != last_id] or selected
            template = random.choice(choices)
            assignments[video_path] = template
            last_id = template.template_id
        return assignments

    def layout(self, layer: TextLayer, video_width: int, video_height: int, template: TextTemplate | None = None) -> TextLayout:
        active_template = template or self.by_id_or_name(layer.template_id)
        text = layer.text.upper() if layer.auto_uppercase or active_template.auto_uppercase else layer.text
        area = safe_area(video_width, video_height)
        max_width = max_text_width(video_width)
        requested_font_size = max(layer.font_size, MIN_FONT_SIZE)
        font_size = requested_font_size
        while font_size >= MIN_FONT_SIZE:
            hpad, vpad, radius, line_spacing, shadow_blur = spacing_for_font(font_size, active_template)
            hpad = max(hpad, layer.box_padding)
            vpad = max(vpad, round(layer.box_padding * 0.56))
            available_text_width = max(MIN_FONT_SIZE, max_width - hpad * 2)
            fitted_font_size, lines, text_width, text_height = _fit_text(text, font_size, available_text_width)
            font_size = fitted_font_size
            hpad, vpad, radius, line_spacing, shadow_blur = spacing_for_font(font_size, active_template)
            hpad = max(hpad, layer.box_padding)
            vpad = max(vpad, round(layer.box_padding * 0.56))
            box_width = text_width + hpad * 2
            if box_width <= max_width or font_size <= MIN_FONT_SIZE:
                break
            font_size -= 1
        box_width = min(max_width, text_width + hpad * 2)
        box_height = text_height + vpad * 2
        x = round(layer.x)
        y = round(layer.y)
        min_x = area.left
        max_x = max(area.left, video_width - area.right - box_width)
        min_y = area.top
        max_y = max(area.top, video_height - area.bottom - box_height)
        x = max(min_x, min(max_x, x))
        y = max(min_y, min(max_y, y))
        return TextLayout(
            text=text,
            lines=lines,
            font_size=font_size,
            horizontal_padding=hpad,
            vertical_padding=vpad,
            border_radius=radius,
            line_spacing=line_spacing,
            shadow_blur=shadow_blur,
            max_text_width=max_width,
            text_width=text_width,
            text_height=text_height,
            box_width=box_width,
            box_height=box_height,
            x=x,
            y=y,
            font_family=active_template.font_family,
            font_weight=active_template.font_weight,
        )

    def apply_to_layer(self, layer: TextLayer, template: TextTemplate, permanent: bool = False) -> None:
        layer.template_id = template.template_id
        layer.color = template.text_color
        layer.box_enabled = True
        layer.box_color = template.background_color
        layer.font_family = template.font_family
        layer.font_weight = template.font_weight
        layer.auto_uppercase = layer.auto_uppercase or template.auto_uppercase
        if permanent:
            layer.box_radius = round(layer.font_size * template.border_radius_multiplier)

    def render_png(self, layer: TextLayer, video_width: int, video_height: int, output_path: str | Path, template: TextTemplate | None = None) -> TextRenderAsset:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter, QPainterPath, QPen

        app = QGuiApplication.instance()
        if app is None:
            app = QGuiApplication([])

        active_template = template or self.by_id_or_name(layer.template_id)
        layout = self.layout(layer, video_width, video_height, active_template)
        image_width = layout.box_width + layout.shadow_blur * 2
        image_height = layout.box_height + layout.shadow_blur * 2
        image = QImage(image_width, image_height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        font = QFont(active_template.font_family, layout.font_size)
        families = set(QFontDatabase.families())
        if active_template.font_family not in families:
            font.setFamily(active_template.fallback_font_family)
        font.setWeight(QFont.Weight.ExtraBold if active_template.font_weight >= 800 else QFont.Weight.Bold)
        painter.setFont(font)

        background = _qt_color(active_template.background_color)
        text_color = _qt_color(active_template.text_color)
        shadow = _qt_color(active_template.shadow_color)
        rect_x = layout.shadow_blur
        rect_y = layout.shadow_blur
        if active_template.shadow_enabled and layout.shadow_blur > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            shadow.setAlpha(max(25, shadow.alpha()))
            painter.setBrush(shadow)
            painter.drawRoundedRect(rect_x, rect_y + max(1, layout.shadow_blur // 2), layout.box_width, layout.box_height, layout.border_radius, layout.border_radius)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect_x, rect_y, layout.box_width, layout.box_height, layout.border_radius, layout.border_radius)

        metrics = painter.fontMetrics()
        y = rect_y + layout.vertical_padding + metrics.ascent()
        for line in layout.lines:
            line_width = metrics.horizontalAdvance(line)
            x = rect_x + (layout.box_width - line_width) / 2
            path = QPainterPath()
            path.addText(x, y, font, line)
            if layer.stroke_enabled and layer.stroke_width > 0:
                painter.setPen(QPen(_qt_color(layer.stroke_color), layer.stroke_width * 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(text_color)
            painter.drawPath(path)
            y += metrics.height() + layout.line_spacing
        painter.end()

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path))
        return TextRenderAsset(path=path, x=layout.x - layout.shadow_blur, y=layout.y - layout.shadow_blur, width=image_width, height=image_height, layout=layout)


def _qt_color(value: str):
    from PySide6.QtGui import QColor

    color_text = value
    alpha = 1.0
    if "@" in value:
        color_text, raw_alpha = value.split("@", 1)
        try:
            alpha = max(0.0, min(1.0, float(raw_alpha)))
        except ValueError:
            alpha = 1.0
    color = QColor(color_text)
    if not color.isValid() and color_text.startswith("0x"):
        color = QColor(f"#{color_text[2:]}")
    if not color.isValid():
        color = QColor("#000000")
    color.setAlphaF(alpha)
    return color

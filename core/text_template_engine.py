from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import json
import random
import re
from pathlib import Path
from typing import Any, Iterable

from core.text_layer import TextLayer

REFERENCE_HEIGHT = 1920
MIN_FONT_SIZE = 18
DEFAULT_FONT = "Montserrat ExtraBold"
FALLBACK_FONT = "Poppins Bold"


@dataclass
class TextTemplate:
    template_id: str
    name: str
    text_color: str
    background_color: str
    font_family: str = DEFAULT_FONT
    fallback_font_family: str = FALLBACK_FONT
    font_weight: int = 800
    enabled: bool = True
    auto_uppercase: bool = False
    border_radius_multiplier: float = 0.35
    horizontal_padding_multiplier: float = 0.8
    vertical_padding_multiplier: float = 0.45
    line_spacing_multiplier: float = 0.25
    shadow_blur_multiplier: float = 0.15

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextTemplate":
        return cls(
            template_id=str(data.get("templateId") or data.get("template_id")),
            name=str(data.get("name")),
            text_color=str(data.get("textColor") or data.get("text_color")),
            background_color=str(data.get("backgroundColor") or data.get("background_color")),
            font_family=str(data.get("fontFamily") or data.get("font_family") or DEFAULT_FONT),
            fallback_font_family=str(data.get("fallbackFontFamily") or data.get("fallback_font_family") or FALLBACK_FONT),
            font_weight=int(data.get("fontWeight") or data.get("font_weight") or 800),
            enabled=bool(data.get("enabled", True)),
            auto_uppercase=bool(data.get("autoUppercase") or data.get("auto_uppercase") or False),
            border_radius_multiplier=float(data.get("borderRadiusMultiplier") or data.get("border_radius_multiplier") or 0.35),
            horizontal_padding_multiplier=float(data.get("horizontalPaddingMultiplier") or data.get("horizontal_padding_multiplier") or 0.8),
            vertical_padding_multiplier=float(data.get("verticalPaddingMultiplier") or data.get("vertical_padding_multiplier") or 0.45),
            line_spacing_multiplier=float(data.get("lineSpacingMultiplier") or data.get("line_spacing_multiplier") or 0.25),
            shadow_blur_multiplier=float(data.get("shadowBlurMultiplier") or data.get("shadow_blur_multiplier") or 0.15),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            "templateId": payload["template_id"],
            "name": payload["name"],
            "textColor": payload["text_color"],
            "backgroundColor": payload["background_color"],
            "fontFamily": payload["font_family"],
            "fallbackFontFamily": payload["fallback_font_family"],
            "fontWeight": payload["font_weight"],
            "enabled": payload["enabled"],
            "autoUppercase": payload["auto_uppercase"],
            "borderRadiusMultiplier": payload["border_radius_multiplier"],
            "horizontalPaddingMultiplier": payload["horizontal_padding_multiplier"],
            "verticalPaddingMultiplier": payload["vertical_padding_multiplier"],
            "lineSpacingMultiplier": payload["line_spacing_multiplier"],
            "shadowBlurMultiplier": payload["shadow_blur_multiplier"],
        }


DEFAULT_TEMPLATES: list[TextTemplate] = [
    TextTemplate("orange-white", "Orange White", "#FFFFFF", "#F57C4D"),
    TextTemplate("white-black", "White Black", "#000000", "#FFFFFF"),
    TextTemplate("pink-white", "Pink White", "#FFFFFF", "#FF3FA4"),
    TextTemplate("red-white", "Red White", "#FFFFFF", "#FF4B4B"),
    TextTemplate("yellow-white", "Yellow White", "#FFFFFF", "#EFCB39"),
    TextTemplate("pastel-pink", "Pastel Pink", "#F0537A", "#FFD7DF"),
    TextTemplate("green-white", "Green White", "#FFFFFF", "#8BC34A"),
]


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
    text_width: int
    text_height: int
    box_width: int
    box_height: int
    x: int
    y: int
    hpad: int
    vpad: int
    radius: int
    line_spacing: int
    shadow_blur: int
    stroke_width: int
    max_width: int
    template: TextTemplate

    @property
    def horizontal_padding(self) -> int:
        return self.hpad

    @property
    def vertical_padding(self) -> int:
        return self.vpad

    @property
    def border_radius(self) -> int:
        return self.radius


def safe_area(width: int, height: int) -> SafeArea:
    return SafeArea(round(height * 0.08), round(height * 0.16), round(width * 0.05), round(width * 0.05))


def max_text_width(width: int) -> int:
    return round(width * 0.78)


def scale_factor(height: int) -> float:
    return max(0.1, height / REFERENCE_HEIGHT)


def rendered_font_size(base_font_size: int, height: int) -> int:
    return max(MIN_FONT_SIZE, round(base_font_size * scale_factor(height)))


def spacing(font_size: int, template: TextTemplate) -> tuple[int, int, int, int, int, int]:
    radius = min(40, max(6, round(font_size * template.border_radius_multiplier)))
    return (
        round(font_size * template.horizontal_padding_multiplier),
        round(font_size * template.vertical_padding_multiplier),
        radius,
        round(font_size * template.line_spacing_multiplier),
        round(font_size * template.shadow_blur_multiplier),
        max(1, round(font_size * 0.08)),
    )


def _qt_metrics(template: TextTemplate, font_size: int):  # type: ignore[no-untyped-def]
    if importlib.util.find_spec("PySide6") is None:
        return None
    from PySide6.QtGui import QFont, QFontMetricsF

    font = QFont(template.font_family, font_size)
    font.setWeight(QFont.Weight.ExtraBold if template.font_weight >= 800 else QFont.Weight.Bold)
    return QFontMetricsF(font)


def _measure(text: str, font_size: int, template: TextTemplate | None = None) -> int:
    if template is not None:
        metrics = _qt_metrics(template, font_size)
        if metrics is not None:
            return max(1, round(metrics.horizontalAdvance(text)))
    wide = sum(1 for char in text if ord(char) > 127)
    return max(1, round((len(text) + wide * 0.25) * font_size * 0.58))


def _line_height(font_size: int, template: TextTemplate) -> int:
    metrics = _qt_metrics(template, font_size)
    if metrics is not None:
        return max(1, round(metrics.lineSpacing()))
    return round(font_size * 1.05)


def _wrap(text: str, font_size: int, limit: int, template: TextTemplate | None = None) -> list[str]:
    result: list[str] = []
    for raw_line in text.splitlines() or [text]:
        words = re.findall(r"\S+", raw_line)
        if not words:
            result.append("")
            continue
        line = words[0]
        for word in words[1:]:
            test = f"{line} {word}"
            if _measure(test, font_size, template) <= limit:
                line = test
            else:
                result.append(line)
                line = word
        result.append(line)
    if len(result) > 1 and len(result[-1].split()) == 1 and len(result[-2].split()) > 1:
        prev = result[-2].split()
        moved = prev.pop()
        test_last = f"{moved} {result[-1]}"
        if prev and _measure(test_last, font_size, template) <= limit:
            result[-2] = " ".join(prev)
            result[-1] = test_last
    return result


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
        return cls([TextTemplate.from_dict(item) for item in items])

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"templates": [item.to_dict() for item in self.templates]}, indent=2), encoding="utf-8")

    def reset_defaults(self) -> None:
        self.templates = [TextTemplate.from_dict(item.to_dict()) for item in DEFAULT_TEMPLATES]

    def enabled_templates(self) -> list[TextTemplate]:
        return [item for item in self.templates if item.enabled]

    def get(self, template_id_or_name: str | None) -> TextTemplate:
        candidates = self.templates or DEFAULT_TEMPLATES
        if template_id_or_name:
            for item in candidates:
                if item.template_id == template_id_or_name or item.name == template_id_or_name:
                    return item
        return (self.enabled_templates() or candidates)[0]

    def by_id_or_name(self, template_id_or_name: str | None) -> TextTemplate:
        return self.get(template_id_or_name)

    def apply_to_layer(self, layer: TextLayer, template: TextTemplate, permanent: bool = False) -> None:
        layer.template_id = template.template_id
        layer.color = template.text_color
        layer.box_color = template.background_color
        layer.box_enabled = True
        layer.font_family = template.font_family
        layer.fallback_font_family = template.fallback_font_family
        layer.font_weight = template.font_weight
        layer.auto_uppercase = template.auto_uppercase

    def set_enabled(self, template_id: str, enabled: bool) -> None:
        self.get(template_id).enabled = enabled

    def set_template_enabled(self, template_id: str, enabled: bool) -> None:
        self.set_enabled(template_id, enabled)

    def duplicate(self, template_id: str, name: str) -> TextTemplate:
        source = self.get(template_id)
        copy = TextTemplate.from_dict(source.to_dict())
        copy.name = name
        copy.template_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"{source.template_id}-copy"
        self.templates.append(copy)
        return copy

    def duplicate_template(self, template_id: str, name: str) -> TextTemplate:
        return self.duplicate(template_id, name)

    def reset_one(self, template_id: str) -> None:
        defaults = {item.template_id: item for item in DEFAULT_TEMPLATES}
        if template_id in defaults:
            self.templates = [defaults[template_id] if item.template_id == template_id else item for item in self.templates]

    def reorder(self, ids: list[str]) -> None:
        by_id = {item.template_id: item for item in self.templates}
        ordered = [by_id[item_id] for item_id in ids if item_id in by_id]
        ordered.extend(item for item in self.templates if item.template_id not in ids)
        self.templates = ordered

    def reorder_templates(self, ids: list[str]) -> None:
        self.reorder(ids)

    def assign_for_batch(self, videos: list[str]) -> dict[str, TextTemplate]:
        choices = self.enabled_templates() or [self.templates[0]]
        assigned: dict[str, TextTemplate] = {}
        last = ""
        for video in videos:
            pool = [item for item in choices if item.template_id != last] or choices
            item = random.choice(pool)
            assigned[video] = item
            last = item.template_id
        return assigned

    def assign_templates_to_videos(self, videos: list[str], selected_template_ids: list[str] | None = None) -> dict[str, TextTemplate]:
        if selected_template_ids:
            selected = [self.get(template_id) for template_id in selected_template_ids]
            original = self.templates
            self.templates = selected
            try:
                return self.assign_for_batch(videos)
            finally:
                self.templates = original
        return self.assign_for_batch(videos)

    def layout(self, layer: TextLayer, width: int, height: int, template: TextTemplate | None = None) -> TextLayout:
        item = template or self.get(layer.template_id)
        text = layer.text.upper() if (layer.auto_uppercase or item.auto_uppercase) else layer.text
        max_width = max_text_width(width)
        font_size = rendered_font_size(layer.font_size, height)
        min_font_size = max(8, round(MIN_FONT_SIZE * scale_factor(height)))
        scaled_box_padding = round(layer.box_padding * scale_factor(height))
        while font_size >= min_font_size:
            hpad, vpad, radius, line_gap, shadow, stroke_width = spacing(font_size, item)
            hpad = max(hpad, scaled_box_padding)
            vpad = max(vpad, round(scaled_box_padding * 0.56))
            lines = _wrap(text, font_size, max(MIN_FONT_SIZE, max_width - hpad * 2), item)
            text_width = max((_measure(line, font_size, item) for line in lines), default=1)
            line_height = _line_height(font_size, item)
            text_height = len(lines) * line_height + max(0, len(lines) - 1) * line_gap
            box_width = text_width + hpad * 2
            if box_width <= max_width or font_size <= min_font_size:
                break
            font_size -= 1
        area = safe_area(width, height)
        box_width = min(max_width, text_width + hpad * 2)
        box_height = text_height + vpad * 2
        x = min(max(round(layer.x), area.left), max(area.left, width - area.right - box_width))
        y = min(max(round(layer.y), area.top), max(area.top, height - area.bottom - box_height))
        return TextLayout(text, lines, font_size, text_width, text_height, box_width, box_height, x, y, hpad, vpad, radius, line_gap, shadow, stroke_width, max_width, item)

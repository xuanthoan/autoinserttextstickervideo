from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class TextLayer:
    text: str = "YOUR CAPTION"
    start_time: float = 0.0
    end_time: float = 5.0
    x: float = 100.0
    y: float = 100.0
    rotation: float = 0.0
    opacity: float = 1.0
    font_path: str = ""
    font_family: str = "Montserrat ExtraBold"
    fallback_font_family: str = "Poppins Bold"
    font_weight: int = 800
    font_size: int = 54
    template_id: str = "orange-white"
    color: str = "#FFFFFF"
    box_color: str = "#F57C4D"
    auto_uppercase: bool = False
    stroke_enabled: bool = False
    stroke_color: str = "black"
    stroke_width: int = 0
    box_enabled: bool = True
    box_padding: int = 0
    motion_preset: str = "fade_in"
    motion_duration: float = 0.5
    easing: str = "ease-out"
    layer_id: str = field(default_factory=lambda: f"text-{uuid4().hex[:8]}")

    @property
    def kind(self) -> str:
        return "text"

    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)

    def scaled_padding_x(self) -> int:
        return max(self.box_padding, round(self.font_size * 0.8))

    def scaled_padding_y(self) -> int:
        return max(round(self.box_padding * 0.56), round(self.font_size * 0.45))

    def scaled_radius(self) -> int:
        return min(40, max(6, round(self.font_size * 0.35)))

    def scaled_line_spacing(self) -> int:
        return round(self.font_size * 0.25)

    def scaled_shadow_blur(self) -> int:
        return round(self.font_size * 0.15)

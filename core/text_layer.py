from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class TextLayer:
    text: str = "Sample text"
    start_time: float = 0.0
    end_time: float = 5.0
    x: float = 100.0
    y: float = 100.0
    rotation: float = 0.0
    font_path: str = ""
    font_family: str = "Montserrat ExtraBold"
    font_weight: int = 800
    font_size: int = 48
    color: str = "white"
    stroke_enabled: bool = False
    stroke_color: str = "black"
    stroke_width: int = 0
    box_enabled: bool = False
    box_color: str = "black@0.5"
    box_padding: int = 10
    box_radius: int = 0
    template_id: str = "orange-white"
    auto_uppercase: bool = False
    opacity: float = 1.0
    motion_preset: str = "none"
    motion_duration: float = 0.5
    easing: str = "linear"
    layer_id: str = field(default_factory=lambda: f"text-{uuid4().hex[:8]}")

    @property
    def kind(self) -> str:
        return "text"

    def effective_box_padding(self) -> int:
        """Scale background padding with the current font size.

        The inspector value acts as a minimum so existing projects keep their
        spacing, while larger text automatically gets a larger background.
        """
        return max(self.box_padding, round(self.font_size * 0.8))

    def effective_box_radius(self) -> int:
        """Scale corner radius with font/background size unless overridden."""
        if self.box_radius > 0:
            return self.box_radius
        return max(4, round(self.font_size * 0.35))

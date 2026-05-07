from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class StickerLayer:
    file_path: str = ""
    start_time: float = 0.0
    end_time: float = 5.0
    x: float = 100.0
    y: float = 100.0
    scale: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    motion_preset: str = "none"
    motion_duration: float = 0.5
    easing: str = "ease-out"
    layer_id: str = field(default_factory=lambda: f"sticker-{uuid4().hex[:8]}")

    @property
    def kind(self) -> str:
        return "sticker"

    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)

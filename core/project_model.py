from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from core.sticker_layer import StickerLayer
from core.text_layer import TextLayer


@dataclass
class Project:
    video_path: str = ""
    width: int = 1920
    height: int = 1080
    duration: float = 0.0
    text_layers: list[TextLayer] = field(default_factory=list)
    sticker_layers: list[StickerLayer] = field(default_factory=list)

    def all_layers(self) -> list[TextLayer | StickerLayer]:
        return [*self.text_layers, *self.sticker_layers]

    def add_text_layer(self, layer: TextLayer | None = None) -> TextLayer:
        new_layer = layer or TextLayer(end_time=max(5.0, min(self.duration, 5.0) if self.duration else 5.0))
        self.text_layers.append(new_layer)
        return new_layer

    def add_sticker_layer(self, layer: StickerLayer | None = None) -> StickerLayer:
        new_layer = layer or StickerLayer(end_time=max(5.0, min(self.duration, 5.0) if self.duration else 5.0))
        self.sticker_layers.append(new_layer)
        return new_layer

    def remove_layer(self, layer_id: str) -> None:
        self.text_layers = [layer for layer in self.text_layers if layer.layer_id != layer_id]
        self.sticker_layers = [layer for layer in self.sticker_layers if layer.layer_id != layer_id]

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "text_layers": [asdict(layer) for layer in self.text_layers],
            "sticker_layers": [asdict(layer) for layer in self.sticker_layers],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Project":
        project = cls(
            video_path=payload.get("video_path", ""),
            width=int(payload.get("width", 1920)),
            height=int(payload.get("height", 1080)),
            duration=float(payload.get("duration", 0.0)),
        )
        project.text_layers = [TextLayer(**item) for item in payload.get("text_layers", [])]
        project.sticker_layers = [StickerLayer(**item) for item in payload.get("sticker_layers", [])]
        return project

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

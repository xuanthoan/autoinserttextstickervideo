from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.project_model import Project
from core.renderer import render_project
from core.text_template_engine import TextTemplateEngine
from utils.ffmpeg_helper import probe_video


@dataclass(frozen=True)
class BatchResult:
    video_path: str
    output_path: str
    success: bool
    error: str = ""


class BatchRenderer:
    def __init__(self, template_engine: TextTemplateEngine) -> None:
        self.template_engine = template_engine
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def render(self, base_project: Project, videos: list[str], on_log: Callable[[str], None] | None = None) -> list[BatchResult]:
        assignments = self.template_engine.assign_for_batch(videos)
        results: list[BatchResult] = []
        for video in videos:
            if self.cancelled:
                break
            try:
                project = deepcopy(base_project)
                metadata = probe_video(video)
                project.video_path = video
                project.width = int(metadata["width"])
                project.height = int(metadata["height"])
                project.duration = float(metadata["duration"])
                template = assignments[video]
                for layer in project.text_layers:
                    self.template_engine.apply_to_layer(layer, template)
                source = Path(video)
                output_dir = source.parent / "output"
                output_dir.mkdir(exist_ok=True)
                output = output_dir / f"{source.stem}_output.mp4"
                if on_log:
                    on_log(f"Rendering {source.name} with {template.name}")
                render_project(project, str(output), on_log)
                results.append(BatchResult(video, str(output), True))
            except Exception as exc:  # noqa: BLE001
                results.append(BatchResult(video, "", False, str(exc)))
        return results

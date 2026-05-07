from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.project_model import Project
from core.renderer import render_project
from core.text_template_engine import TextTemplateEngine
from utils.ffmpeg_helper import probe_video


class BatchRenderWorker(QObject):
    videoStarted = Signal(int, int, str)
    videoFinished = Signal(int, int, str)
    videoFailed = Signal(int, int, str, str)
    overallProgress = Signal(int, int)
    logLine = Signal(str)
    finished = Signal()

    def __init__(self, base_project: Project, video_paths: list[str], template_engine: TextTemplateEngine) -> None:
        super().__init__()
        self.base_project = deepcopy(base_project)
        self.video_paths = list(video_paths)
        self.template_engine = template_engine
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        total = len(self.video_paths)
        assignments = self.template_engine.assign_templates_to_videos(
            self.video_paths,
            [template.template_id for template in self.template_engine.enabled_templates()],
        )
        for index, video_path in enumerate(self.video_paths, start=1):
            if self.cancel_requested:
                self.logLine.emit("Batch render cancelled.")
                break
            self.videoStarted.emit(index, total, video_path)
            try:
                project = deepcopy(self.base_project)
                metadata = probe_video(video_path)
                project.video_path = video_path
                project.width = int(metadata["width"])
                project.height = int(metadata["height"])
                project.duration = float(metadata["duration"])
                template = assignments[video_path]
                for layer in project.text_layers:
                    self.template_engine.apply_to_layer(layer, template, permanent=False)
                input_path = Path(video_path)
                output_dir = input_path.parent / "output"
                output_dir.mkdir(exist_ok=True)
                output_path = output_dir / f"{input_path.stem}_output.mp4"
                self.logLine.emit(f"[{index}/{total}] {input_path.name} → {output_path.name} ({template.name})")
                render_project(project, str(output_path), self.logLine.emit)
                self.videoFinished.emit(index, total, str(output_path))
            except Exception as exc:  # noqa: BLE001
                self.videoFailed.emit(index, total, video_path, str(exc))
                self.logLine.emit(f"Failed {video_path}: {exc}")
            self.overallProgress.emit(index, total)
        self.finished.emit()

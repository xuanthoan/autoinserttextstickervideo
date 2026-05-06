# Auto Insert Text Sticker Video

Python 3.11+ desktop editor for adding animated text and sticker overlays to video without resizing the source. The GUI is built with PySide6, while all video processing is delegated to FFmpeg/FFprobe subprocesses.

## Features

- QGraphicsView preview canvas with live QMediaPlayer video playback, draggable text/sticker overlays, and timeline-aware motion preview.
- Snap-to-center guidelines with a 10 px threshold.
- Timeline panel for per-layer start and end times.
- Inspector for text, font, visual text/stroke/background color picking, auto-scaling rounded background padding, opacity, sticker scale, rotation, easing, and motion presets.
- JSON text templates in `templates/text_templates.json`.
- FFmpeg `filter_complex` export pipeline with timestamp reset, drawtext, sticker loop inputs, overlay chaining, motion expressions, `overlay=shortest=1`, `-fflags +genpts`, and `-vsync 2`.
- Export automatically writes to an `output/` sub-folder beside the input video using the input video name, e.g. `input/output/my_video_output.mp4`.

## Requirements

```bash
python -m pip install -r requirements.txt
```

Install FFmpeg and FFprobe on `PATH`, place bundled binaries in `bin/`, or drop `ffmpeg.exe` and `ffprobe.exe` directly next to `main.py` for Windows/source-tree runs.

## Run

```bash
python main.py
```

## Build

```bash
pyinstaller --onedir --windowed main.py
```

A PyInstaller spec is also provided:

```bash
pyinstaller autoinserttextstickervideo.spec
```

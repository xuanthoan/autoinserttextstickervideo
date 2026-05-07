# Auto Insert Text Sticker Video

Python 3.11+ desktop editor for adding animated text and sticker overlays to video without resizing the source. The GUI is built with PySide6, while all video processing is delegated to FFmpeg/FFprobe subprocesses.

## Features

- QGraphicsView preview canvas with live QMediaPlayer video playback, draggable text/sticker overlays, and timeline-aware motion preview.
- True sequential batch rendering with a multi-video queue, drag/drop additions, reorder/remove/clear controls, and per-video/overall progress.
- Snap-to-center guidelines with a 10 px threshold.
- Timeline panel for per-layer start and end times.
- Inspector for text, font size, template selection, safe optional stroke controls, auto-scaling rounded background padding, opacity, sticker scale, rotation, easing, and motion presets. Free text/background color pickers are intentionally removed for standardized templates.
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


## Text template engine

The reusable template engine in `core/text_template_engine.py` provides TikTok/Reels/Shorts-style rounded caption presets. It uses Montserrat ExtraBold by default with Poppins Bold fallback, center alignment, optional uppercase, safe-area clamping, max-width wrapping (`videoWidth * 0.78`), minimum font-size protection, and proportional spacing formulas:

- `horizontalPadding = fontSize * 0.8`
- `verticalPadding = fontSize * 0.45`
- `borderRadius = fontSize * 0.35`
- `lineSpacing = fontSize * 0.25`
- `shadowBlur = fontSize * 0.15`

Exactly seven built-in templates are stored in `templates/text_templates.json`; users enable templates from the template panel, duplicate/reset/reorder them, and batch rendering assigns enabled templates with non-consecutive randomization when multiple templates are active. During export, text layers are rendered as high-quality transparent rounded PNG assets and FFmpeg only overlays those assets, which avoids invalid `drawtext/geq` filter failures such as exit code `4294967274`.

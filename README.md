# Auto Insert Text Sticker Video

A lightweight Python 3.11+ desktop app for TikTok/Reels/Shorts mass-production overlays. The UI is PySide6, preview is simulated with `QGraphicsView`, and every final video render is orchestrated through FFmpeg/FFprobe subprocesses with `filter_complex`.

## Features

- Single-video, multi-video, folder, and drag/drop import for `.mp4`, `.mov`, `.avi`, and `.mkv`.
- Sequential batch queue with reorder/remove/clear, cancel, retry failed item once, skip failed item, per-video progress, overall progress, elapsed time, and ETA.
- Template-driven workflow with exactly seven built-in caption templates and no free text/background color pickers during normal editing.
- Template panel with preview swatch, name, enable/disable toggle, duplicate, reset, and drag reorder.
- Realtime lightweight preview using `QGraphicsView`/`QGraphicsScene`, draggable overlays, selection, center snapping guides, and motion simulation.
- Timeline layer controls for start/end/duration trimming.
- Text and sticker layers with opacity, rotation, timeline, and motion presets.
- FFmpeg export uses `-fflags +genpts`, `setpts=PTS-STARTPTS`, `overlay=shortest=1`, H.264 `-crf 18`, `-preset veryfast`, and AAC audio.

## Built-in caption templates

1. Orange White — `#FFFFFF` on `#F57C4D`
2. White Black — `#000000` on `#FFFFFF`
3. Pink White — `#FFFFFF` on `#FF3FA4`
4. Red White — `#FFFFFF` on `#FF4B4B`
5. Yellow White — `#FFFFFF` on `#EFCB39`
6. Pastel Pink — `#F0537A` on `#FFD7DF`
7. Green White — `#FFFFFF` on `#8BC34A`

Template #1 is assigned automatically when a new text layer is created. If one template is enabled, all batch videos use it. If multiple templates are enabled, the batch renderer randomizes per video and avoids repeating the same template consecutively when possible.

## Social caption layout rules

- Font: Montserrat ExtraBold, fallback Poppins Bold.
- `horizontalPadding = fontSize * 0.8`
- `verticalPadding = fontSize * 0.45`
- `borderRadius = fontSize * 0.35`
- `lineSpacing = fontSize * 0.25`
- `shadowBlur = fontSize * 0.15`
- Safe area: top `8%`, bottom `16%`, left/right `5%`.
- Max text width: `videoWidth * 0.78`.
- Minimum font size: `18`.

## Requirements

```bash
python -m pip install -r requirements.txt
```

Install FFmpeg and FFprobe on `PATH`, place binaries in `bin/`, or put `ffmpeg.exe` and `ffprobe.exe` next to `main.py`.

## Run

```bash
python main.py
```

## Build

```bash
pyinstaller --onedir --windowed main.py
```

The provided `autoinserttextstickervideo.spec` also bundles templates and optional local binaries.

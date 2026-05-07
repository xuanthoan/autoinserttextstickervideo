from __future__ import annotations

import logging

from utils.paths import writable_path


def configure_logging() -> None:
    log_dir = writable_path("logs")
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_dir / "app.log", encoding="utf-8"), logging.StreamHandler()],
    )

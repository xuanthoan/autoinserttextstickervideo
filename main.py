from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
os.chdir(APP_DIR)
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PySide6.QtWidgets import QApplication, QMessageBox

from gui.main_window import MainWindow
from utils.logger import configure_logging
from utils.paths import writable_path


def _write_startup_error(exc: BaseException) -> Path:
    log_dir = writable_path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "startup_error.log"
    log_path.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    return log_path


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    try:
        window = MainWindow()
        window.resize(1280, 820)
        window.show()
        return app.exec()
    except Exception as exc:  # noqa: BLE001
        log_path = _write_startup_error(exc)
        QMessageBox.critical(None, "Startup failed", f"Cannot start the app.\n\n{exc}\n\nDetails were saved to:\n{log_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

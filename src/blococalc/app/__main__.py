"""Ponto de entrada: `python -m blococalc.app`."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from blococalc.app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""Creación y arranque de la aplicación Qt."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from iv_orbit_texture_studio import __version__
from iv_orbit_texture_studio.ui.main_window import APP_TITLE, MainWindow


def configure_logging() -> None:
    """Registro local en consola. Sin telemetría ni envío de datos."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_application(argv: Sequence[str]) -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    app = QApplication(list(argv))
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("IV Orbit")
    return app


def run(argv: Sequence[str] | None = None) -> int:
    """Arranca la interfaz. Un primer argumento opcional es una imagen a abrir."""
    args = list(sys.argv if argv is None else argv)
    configure_logging()
    app = create_application(args)
    window = MainWindow()
    window.show()
    if len(args) > 1:
        window.open_image(Path(args[1]))
    return app.exec()

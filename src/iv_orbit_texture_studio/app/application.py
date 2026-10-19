"""Creación y arranque de la aplicación Qt."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from iv_orbit_texture_studio import __version__
from iv_orbit_texture_studio.ui.main_window import APP_TITLE, MainWindow


def configure_logging() -> None:
    """Registro local en consola. Sin telemetría ni envío de datos."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app_icon() -> QIcon:
    """Genera el icono vectorial de la aplicación en memoria."""
    img = QImage(64, 64, QImage.Format.Format_RGBA8888)
    img.fill(QColor(22, 27, 34, 255))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Cuadrícula de atlas
    painter.setPen(QPen(QColor(48, 54, 61), 2))
    painter.drawRect(6, 6, 52, 52)
    painter.drawLine(32, 6, 32, 58)
    painter.drawLine(6, 32, 58, 32)

    # Cuadrilátero de perspectiva cian
    pen_quad = QPen(QColor(0, 210, 255), 3)
    painter.setPen(pen_quad)
    pts = [(14, 16), (50, 11), (46, 49), (12, 45)]
    for i in range(4):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % 4]
        painter.drawLine(x1, y1, x2, y2)

    # Vértices amarillos
    painter.setPen(QPen(QColor(20, 24, 32), 2))
    painter.setBrush(QColor(255, 210, 0))
    for x, y in pts:
        painter.drawEllipse(x - 4, y - 4, 8, 8)

    painter.end()
    return QIcon(QPixmap.fromImage(img))


def create_application(argv: Sequence[str]) -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    app = QApplication(list(argv))
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("IV Orbit")
    app.setWindowIcon(create_app_icon())
    return app


def run(argv: Sequence[str] | None = None) -> int:
    """Arranca la interfaz. Un primer argumento opcional es una imagen o proyecto a abrir."""
    args = list(sys.argv if argv is None else argv)
    configure_logging()
    app = create_application(args)
    window = MainWindow()
    window.setWindowIcon(app.windowIcon())
    window.show()
    if len(args) > 1:
        target = Path(args[1])
        if target.suffix.lower() == ".ivtex":
            window.open_project(target)
        else:
            window.open_image(target)
    return app.exec()

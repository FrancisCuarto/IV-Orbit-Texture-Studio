"""Herramienta de preparación de texturas y mosaico en el lienzo.

Gestiona la visualización del resultado procesado (filtros y seamless) y la superposición
de líneas guía de cuadrícula cuando se activa el modo mosaico (tiling).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen

from iv_orbit_texture_studio.core.document import TexturePrepSettings
from iv_orbit_texture_studio.imaging.transforms import process_texture_pipeline
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Point, Size

if TYPE_CHECKING:
    from iv_orbit_texture_studio.imaging.image_io import LoadedImage

COLOR_GRID_LINE = QColor(0, 210, 255, 120)


class TexturePrepTool(QObject):
    """Herramienta interactiva para preparación de texturas y mosaico."""

    texture_updated = Signal()
    settings_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source_image: LoadedImage | None = None
        self._settings = TexturePrepSettings()
        self._tiled_view: bool = False
        self._cached_processed: np.ndarray | None = None
        self._image_size: Size | None = None

    # ------------------------------------------------------------- propiedades
    @property
    def settings(self) -> TexturePrepSettings:
        return self._settings

    @property
    def is_tiled_view(self) -> bool:
        return self._tiled_view

    @property
    def processed_pixels(self) -> np.ndarray | None:
        return self._cached_processed

    def set_image_size(self, size: Size | None) -> None:
        self._image_size = size

    def set_source_image(self, image: LoadedImage | None) -> None:
        self._source_image = image
        if image is not None:
            self._image_size = Size(float(image.width), float(image.height))
        else:
            self._image_size = None
        self.update_processed()

    def set_settings(self, settings: TexturePrepSettings) -> None:
        self._settings = settings
        self.settings_changed.emit()
        self.update_processed()

    def set_tiled_view(self, enabled: bool) -> None:
        if self._tiled_view != enabled:
            self._tiled_view = enabled
            self.update_processed()

    def update_processed(self) -> None:
        """Aplica la canalización de procesamiento y emite texture_updated."""
        if self._source_image is None:
            self._cached_processed = None
        else:
            self._cached_processed = process_texture_pipeline(
                self._source_image.pixels,
                self._settings,
                tiled=self._tiled_view,
            )
        self.texture_updated.emit()

    # -------------------------------------------------------- eventos de ratón
    def handle_mouse_press(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        return False

    def handle_mouse_move(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        return False

    def handle_mouse_release(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        return False

    def get_cursor(self) -> Qt.CursorShape | None:
        return None

    # ---------------------------------------------------------------- pintura
    def paint_overlay(self, painter: QPainter, mapper: CoordinateMapper) -> None:
        """Dibuja líneas punteadas delimitando las baldosas individuales en modo mosaico."""
        if not self._tiled_view or self._source_image is None or self._image_size is None:
            return

        gx = self._settings.tiling_grid_x
        gy = self._settings.tiling_grid_y
        if gx <= 1 and gy <= 1:
            return

        painter.save()
        pen = QPen(COLOR_GRID_LINE, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)

        total_w = self._image_size.width * gx
        total_h = self._image_size.height * gy
        w_tile = self._image_size.width
        h_tile = self._image_size.height

        # Líneas verticales divisorias
        for i in range(1, gx):
            img_x = i * w_tile
            p_top = mapper.image_to_screen(Point(img_x, 0.0))
            p_bot = mapper.image_to_screen(Point(img_x, total_h))
            painter.drawLine(QPointF(p_top.x, p_top.y), QPointF(p_bot.x, p_bot.y))

        # Líneas horizontales divisorias
        for j in range(1, gy):
            img_y = j * h_tile
            p_left = mapper.image_to_screen(Point(0.0, img_y))
            p_right = mapper.image_to_screen(Point(total_w, img_y))
            painter.drawLine(QPointF(p_left.x, p_left.y), QPointF(p_right.x, p_right.y))

        painter.restore()

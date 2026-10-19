"""Herramienta interactiva para visualización y control de mapas PBR en el lienzo."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter

from iv_orbit_texture_studio.core.document import PbrSettings
from iv_orbit_texture_studio.imaging.pbr import (
    generate_ao_map,
    generate_height_map,
    generate_normal_map,
    generate_roughness_map,
    pack_orm_map,
)
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Size

if TYPE_CHECKING:
    from iv_orbit_texture_studio.imaging.image_io import LoadedImage


class PbrTool(QObject):
    """Herramienta interactiva para mapas de normales y materiales PBR."""

    map_updated = Signal()
    settings_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source_image: LoadedImage | None = None
        self._settings = PbrSettings()
        # Tipos de mapa: "normal", "height", "roughness", "ao", "orm", "diffuse"
        self._active_map_type: str = "normal"
        self._cached_maps: dict[str, np.ndarray] = {}
        self._image_size: Size | None = None

    # ------------------------------------------------------------- propiedades
    @property
    def settings(self) -> PbrSettings:
        return self._settings

    @property
    def active_map_type(self) -> str:
        return self._active_map_type

    @property
    def processed_pixels(self) -> np.ndarray | None:
        """Devuelve los píxeles del mapa actualmente seleccionado para el lienzo."""
        return self.get_active_pixels()

    def get_active_pixels(self) -> np.ndarray | None:
        if self._source_image is None:
            return None
        if self._active_map_type == "diffuse":
            return self._source_image.pixels
        return self._cached_maps.get(self._active_map_type)

    def get_map(self, map_type: str) -> np.ndarray | None:
        if self._source_image is None:
            return None
        if map_type == "diffuse":
            return self._source_image.pixels
        return self._cached_maps.get(map_type)

    def set_image_size(self, size: Size | None) -> None:
        self._image_size = size

    def set_source_image(self, image: LoadedImage | None) -> None:
        self._source_image = image
        if image is not None:
            self._image_size = Size(float(image.width), float(image.height))
        else:
            self._image_size = None
        self.update_all_maps()

    def set_settings(self, settings: PbrSettings) -> None:
        self._settings = settings
        self.settings_changed.emit()
        self.update_all_maps()

    def set_active_map_type(self, map_type: str) -> None:
        if self._active_map_type != map_type:
            self._active_map_type = map_type
            self.map_updated.emit()

    def update_all_maps(self) -> None:
        """Calcula de forma reactiva todos los mapas PBR a partir de la imagen actual."""
        if self._source_image is None:
            self._cached_maps.clear()
            self.map_updated.emit()
            return

        pixels = self._source_image.pixels
        s = self._settings

        # 1. Mapa de Normales
        norm = generate_normal_map(
            pixels,
            strength=s.normal_strength,
            format_opengl=s.format_opengl,
            blur_radius=s.normal_blur,
            invert_x=s.invert_x,
            invert_y=s.invert_y,
        )
        self._cached_maps["normal"] = norm

        # 2. Mapa de Altura
        height = generate_height_map(
            pixels,
            invert=s.height_invert,
            contrast=s.height_contrast,
            brightness=s.height_brightness,
            blur_radius=s.height_blur,
        )
        self._cached_maps["height"] = height

        # 3. Mapa de Rugosidad
        rough = generate_roughness_map(
            pixels,
            base_roughness=s.base_roughness,
            detail_influence=s.roughness_detail,
            invert=s.roughness_invert,
            contrast=s.roughness_contrast,
        )
        self._cached_maps["roughness"] = rough

        # 4. Mapa de Oclusión Ambiental (AO)
        ao = generate_ao_map(
            pixels,
            strength=s.ao_strength,
            blur_radius=s.ao_radius,
            contrast=s.ao_contrast,
        )
        self._cached_maps["ao"] = ao

        # 5. Empaquetado ORM / RMA
        orm = pack_orm_map(
            ao_pixels=ao,
            roughness_pixels=rough,
            metallic_value=s.metallic,
            format_rma=(s.packing_format.upper() == "RMA"),
        )
        self._cached_maps["orm"] = orm

        self.map_updated.emit()

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

    def paint_overlay(self, painter: QPainter, mapper: CoordinateMapper) -> None:
        pass

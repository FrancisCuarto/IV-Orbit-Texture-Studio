"""Conversión entre coordenadas de pantalla (widget) y de imagen.

Este módulo es deliberadamente independiente de Qt para que pueda probarse
sin interfaz gráfica.

Convenciones
------------
* Las coordenadas de imagen se expresan en píxeles de la imagen de origen.
  El píxel ``(i, j)`` (columna, fila) cubre el área ``[i, i+1) x [j, j+1)``;
  por lo tanto su centro está en ``(i + 0.5, j + 0.5)`` y la imagen completa
  ocupa ``[0, ancho) x [0, alto)``.
* Las coordenadas de pantalla se expresan en píxeles lógicos del widget, con
  origen en la esquina superior izquierda.
* La transformación es una escala uniforme más una traslación::

      pantalla = imagen * zoom + desplazamiento
      imagen   = (pantalla - desplazamiento) / zoom
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_MIN_ZOOM = 0.01
DEFAULT_MAX_ZOOM = 64.0


@dataclass(frozen=True, slots=True)
class Point:
    """Punto 2D inmutable en coordenadas de punto flotante."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Size:
    """Dimensiones 2D (ancho y alto) estrictamente positivas."""

    width: float
    height: float

    def __post_init__(self) -> None:
        if not (_is_finite_positive(self.width) and _is_finite_positive(self.height)):
            raise ValueError(f"Dimensiones inválidas: {self.width} x {self.height}")


def _is_finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0


def _require_finite(*values: float) -> None:
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f"Coordenadas no finitas: {values}")


class CoordinateMapper:
    """Mantiene el zoom y el desplazamiento de una vista sobre una imagen."""

    def __init__(
        self,
        min_zoom: float = DEFAULT_MIN_ZOOM,
        max_zoom: float = DEFAULT_MAX_ZOOM,
    ) -> None:
        if not (_is_finite_positive(min_zoom) and _is_finite_positive(max_zoom)):
            raise ValueError("Los límites de zoom deben ser positivos y finitos")
        if min_zoom > max_zoom:
            raise ValueError("min_zoom no puede ser mayor que max_zoom")
        self._min_zoom = min_zoom
        self._max_zoom = max_zoom
        self._zoom = 1.0
        self._offset = Point(0.0, 0.0)

    # ------------------------------------------------------------------ estado
    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def offset(self) -> Point:
        """Posición en pantalla del origen ``(0, 0)`` de la imagen."""
        return self._offset

    @property
    def min_zoom(self) -> float:
        return self._min_zoom

    @property
    def max_zoom(self) -> float:
        return self._max_zoom

    def clamp_zoom(self, zoom: float) -> float:
        if not _is_finite_positive(zoom):
            raise ValueError(f"Zoom inválido: {zoom}")
        return min(max(zoom, self._min_zoom), self._max_zoom)

    # -------------------------------------------------------------- conversión
    def image_to_screen(self, point: Point) -> Point:
        _require_finite(point.x, point.y)
        return Point(
            point.x * self._zoom + self._offset.x,
            point.y * self._zoom + self._offset.y,
        )

    def screen_to_image(self, point: Point) -> Point:
        _require_finite(point.x, point.y)
        return Point(
            (point.x - self._offset.x) / self._zoom,
            (point.y - self._offset.y) / self._zoom,
        )

    def screen_to_pixel(self, point: Point, image_size: Size) -> tuple[int, int] | None:
        """Índices ``(columna, fila)`` del píxel bajo ``point``, o ``None`` si cae fuera."""
        image_point = self.screen_to_image(point)
        column = math.floor(image_point.x)
        row = math.floor(image_point.y)
        if 0 <= column < image_size.width and 0 <= row < image_size.height:
            return column, row
        return None

    def image_rect_on_screen(self, image_size: Size) -> tuple[Point, Point]:
        """Esquinas superior izquierda e inferior derecha de la imagen en pantalla."""
        return (
            self.image_to_screen(Point(0.0, 0.0)),
            self.image_to_screen(Point(image_size.width, image_size.height)),
        )

    # ------------------------------------------------------------- navegación
    def set_zoom(self, zoom: float, anchor: Point) -> None:
        """Cambia el zoom manteniendo fijo en pantalla el punto ``anchor``."""
        new_zoom = self.clamp_zoom(zoom)
        anchor_in_image = self.screen_to_image(anchor)
        self._zoom = new_zoom
        self._offset = Point(
            anchor.x - anchor_in_image.x * new_zoom,
            anchor.y - anchor_in_image.y * new_zoom,
        )

    def zoom_by(self, factor: float, anchor: Point) -> None:
        if not _is_finite_positive(factor):
            raise ValueError(f"Factor de zoom inválido: {factor}")
        self.set_zoom(self._zoom * factor, anchor)

    def pan(self, dx: float, dy: float) -> None:
        """Desplaza la vista ``dx``, ``dy`` píxeles de pantalla."""
        _require_finite(dx, dy)
        self._offset = Point(self._offset.x + dx, self._offset.y + dy)

    def center(self, image_size: Size, viewport: Size) -> None:
        """Centra la imagen en la vista sin modificar el zoom."""
        self._offset = Point(
            (viewport.width - image_size.width * self._zoom) / 2.0,
            (viewport.height - image_size.height * self._zoom) / 2.0,
        )

    def fit(self, image_size: Size, viewport: Size, margin: float = 0.0) -> None:
        """Ajusta la imagen completa a la vista y la centra.

        ``margin`` reserva píxeles de pantalla en cada borde. Si el margen no
        deja espacio útil, se ignora.
        """
        if not math.isfinite(margin) or margin < 0:
            raise ValueError(f"Margen inválido: {margin}")
        available_w = viewport.width - 2 * margin
        available_h = viewport.height - 2 * margin
        if available_w <= 0 or available_h <= 0:
            available_w, available_h = viewport.width, viewport.height
        zoom = min(available_w / image_size.width, available_h / image_size.height)
        self._zoom = self.clamp_zoom(zoom)
        self.center(image_size, viewport)

    def reset(self) -> None:
        self._zoom = 1.0
        self._offset = Point(0.0, 0.0)

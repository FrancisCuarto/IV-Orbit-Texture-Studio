"""Modelo de selección y manipulación de los 4 vértices para Texture Ripper."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from iv_orbit_texture_studio.imaging.perspective import (
    DegenerateQuadError,
    Quad,
    estimate_rectified_dimensions,
    order_points_clockwise,
)
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Point, Size


class SelectionState(StrEnum):
    EMPTY = "empty"
    COLLECTING = "collecting"
    COMPLETE = "complete"


VERTEX_LABELS: tuple[str, ...] = ("1: TL", "2: TR", "3: BR", "4: BL")


@dataclass
class SelectionModel:
    """Administra los puntos seleccionados y el estado del cuadrilátero."""

    _points: list[Point]
    _hovered_index: int | None = None
    _dragged_index: int | None = None

    def __init__(self, points: Sequence[Point] | None = None) -> None:
        self._points = list(points) if points is not None else []
        self._hovered_index = None
        self._dragged_index = None

    # ------------------------------------------------------------------ estado
    @property
    def points(self) -> tuple[Point, ...]:
        return tuple(self._points)

    @property
    def count(self) -> int:
        return len(self._points)

    @property
    def state(self) -> SelectionState:
        if len(self._points) == 0:
            return SelectionState.EMPTY
        if len(self._points) < 4:
            return SelectionState.COLLECTING
        return SelectionState.COMPLETE

    @property
    def hovered_index(self) -> int | None:
        return self._hovered_index

    @hovered_index.setter
    def hovered_index(self, idx: int | None) -> None:
        self._hovered_index = idx

    @property
    def dragged_index(self) -> int | None:
        return self._dragged_index

    @dragged_index.setter
    def dragged_index(self, idx: int | None) -> None:
        self._dragged_index = idx

    # ------------------------------------------------------------- operaciones
    def clear(self) -> None:
        """Reinicia la selección."""
        self._points.clear()
        self._hovered_index = None
        self._dragged_index = None

    def add_point(self, point: Point) -> None:
        """Agrega un punto durante el proceso de colección (máximo 4)."""
        if len(self._points) >= 4:
            return
        self._points.append(point)
        if len(self._points) == 4:
            # Reordenar en sentido horario para garantizar convención TL, TR, BR, BL
            try:
                ordered_quad = order_points_clockwise(self._points)
                self._points = list(ordered_quad.points)
            except Exception:
                pass  # Si falla el ordenamiento se mantienen los puntos ingresados

    def set_quad(self, quad: Quad) -> None:
        """Establece directamente un cuadrilátero completo."""
        self._points = list(quad.points)
        self._hovered_index = None
        self._dragged_index = None

    def init_default_rect(self, image_size: Size, margin_ratio: float = 0.15) -> None:
        """Inicializa una selección rectangular centrada en la imagen."""
        w, h = image_size.width, image_size.height
        mx = w * margin_ratio
        my = h * margin_ratio
        quad = Quad(
            p0=Point(mx, my),
            p1=Point(w - mx, my),
            p2=Point(w - mx, h - my),
            p3=Point(mx, h - my),
        )
        self.set_quad(quad)

    def move_vertex(self, index: int, new_point: Point) -> None:
        """Mueve el vértice con el índice especificado a `new_point`."""
        if not (0 <= index < len(self._points)):
            raise IndexError(f"Índice de vértice fuera de rango: {index}")
        self._points[index] = new_point

    # -------------------------------------------------------------- geometría
    def get_quad(self) -> Quad | None:
        """Retorna el Quad si hay 4 puntos, o None."""
        if len(self._points) == 4:
            return Quad(self._points[0], self._points[1], self._points[2], self._points[3])
        return None

    def validate(self) -> str | None:
        """Devuelve un mensaje de error si la selección no es válida, o None si es correcta."""
        if len(self._points) < 4:
            return f"Selección incompleta: faltan {4 - len(self._points)} puntos."
        quad = self.get_quad()
        if quad is None:
            return "No hay cuadrilátero definido."
        try:
            quad.validate()
            return None
        except DegenerateQuadError as exc:
            return str(exc)

    def is_valid(self) -> bool:
        return self.validate() is None

    def estimated_dimensions(self) -> tuple[int, int] | None:
        quad = self.get_quad()
        if quad is not None and self.is_valid():
            try:
                return estimate_rectified_dimensions(quad)
            except Exception:
                return None
        return None

    # ------------------------------------------------------------- hit testing
    def hit_test_vertex(
        self,
        screen_pos: Point,
        mapper: CoordinateMapper,
        radius_screen_px: float = 14.0,
    ) -> int | None:
        """Verifica si `screen_pos` está sobre alguno de los vértices en espacio de pantalla.

        Devuelve el índice del vértice más cercano si está dentro del radio, o None.
        """
        best_idx: int | None = None
        best_dist = float("inf")

        for idx, img_pt in enumerate(self._points):
            scr_pt = mapper.image_to_screen(img_pt)
            dist = math.hypot(screen_pos.x - scr_pt.x, screen_pos.y - scr_pt.y)
            if dist <= radius_screen_px and dist < best_dist:
                best_dist = dist
                best_idx = idx

        return best_idx

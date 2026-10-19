"""Modelo de datos para regiones de sprites, rectángulos y puntos de pivote.

Representa recortes 2D individuales sobre una imagen de origen, sus coordenadas,
sus dimensiones y el ancla/pivote utilizado en motores de videojuegos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class PivotMode(StrEnum):
    """Modos predefinidos para la posición del pivote/ancla de un sprite."""

    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    CENTER_LEFT = "center_left"
    CENTER_RIGHT = "center_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class Pivot:
    """Pivote o ancla de un sprite, expresado en coordenadas normalizadas (0.0 a 1.0).

    (0, 0) es la esquina superior izquierda del sprite.
    (0.5, 0.5) es el centro exacto.
    (0.5, 1.0) es el pie / base inferior (muy usado en personajes de juegos 2D).
    """

    x: float = 0.5
    y: float = 0.5
    mode: PivotMode = PivotMode.CENTER

    def __post_init__(self) -> None:
        if isinstance(self.mode, str):
            try:
                object.__setattr__(self, "mode", PivotMode(self.mode))
            except ValueError:
                object.__setattr__(self, "mode", PivotMode.CUSTOM)

    def pixel_coords(self, width: int, height: int) -> tuple[float, float]:
        """Calcula la coordenada en píxeles relativa a la esquina superior izquierda del sprite."""
        return self.x * width, self.y * height

    @classmethod
    def from_mode(
        cls, mode: PivotMode | str, custom_x: float = 0.5, custom_y: float = 0.5
    ) -> Pivot:
        """Crea un pivote según el modo predefinido."""
        if isinstance(mode, str):
            try:
                mode = PivotMode(mode)
            except ValueError:
                mode = PivotMode.CUSTOM

        coords = {
            PivotMode.TOP_LEFT: (0.0, 0.0),
            PivotMode.TOP_CENTER: (0.5, 0.0),
            PivotMode.TOP_RIGHT: (1.0, 0.0),
            PivotMode.CENTER_LEFT: (0.0, 0.5),
            PivotMode.CENTER: (0.5, 0.5),
            PivotMode.CENTER_RIGHT: (1.0, 0.5),
            PivotMode.BOTTOM_LEFT: (0.0, 1.0),
            PivotMode.BOTTOM_CENTER: (0.5, 1.0),
            PivotMode.BOTTOM_RIGHT: (1.0, 1.0),
        }
        if mode in coords:
            px, py = coords[mode]
            return cls(x=px, y=py, mode=mode)
        return cls(x=custom_x, y=custom_y, mode=PivotMode.CUSTOM)

    def to_dict(self) -> dict[str, Any]:
        mode_val = self.mode.value if isinstance(self.mode, PivotMode) else str(self.mode)
        return {"x": self.x, "y": self.y, "mode": mode_val}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pivot:
        mode_val = data.get("mode", PivotMode.CENTER.value)
        try:
            mode = PivotMode(mode_val)
        except ValueError:
            mode = PivotMode.CENTER
        return cls(
            x=float(data.get("x", 0.5)),
            y=float(data.get("y", 0.5)),
            mode=mode,
        )


@dataclass(frozen=True, slots=True)
class Rect:
    """Rectángulo alineado con los ejes en coordenadas de píxeles enteros."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError(f"El ancho del rectángulo debe ser positivo: {self.width}")
        if self.height <= 0:
            raise ValueError(f"El alto del rectángulo debe ser positivo: {self.height}")

    @property
    def left(self) -> int:
        return self.x

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def top(self) -> int:
        return self.y

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2.0

    @property
    def area(self) -> int:
        return self.width * self.height

    def contains_point(self, px: float, py: float) -> bool:
        """Determina si un punto se encuentra dentro del rectángulo."""
        return self.left <= px < self.right and self.top <= py < self.bottom

    def intersects(self, other: Rect) -> bool:
        """Determina si este rectángulo solapa con otro."""
        return not (
            self.right <= other.left
            or self.left >= other.right
            or self.bottom <= other.top
            or self.top >= other.bottom
        )

    def clamped(self, max_width: int, max_height: int) -> Rect:
        """Ajusta el rectángulo para que no exceda las dimensiones de la imagen."""
        cx = max(0, min(self.x, max_width - 1))
        cy = max(0, min(self.y, max_height - 1))
        cw = max(1, min(self.width, max_width - cx))
        ch = max(1, min(self.height, max_height - cy))
        return Rect(cx, cy, cw, ch)

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rect:
        return cls(
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            width=int(data.get("width", 1)),
            height=int(data.get("height", 1)),
        )


@dataclass
class SpriteRegion:
    """Región de un sprite individual con identificación, nombre, rectángulo y pivote."""

    id: str
    name: str
    rect: Rect
    pivot: Pivot = Pivot()

    @classmethod
    def create(cls, name: str, rect: Rect, pivot: Pivot | None = None) -> SpriteRegion:
        return cls(
            id=uuid.uuid4().hex[:12],
            name=name,
            rect=rect,
            pivot=pivot if pivot is not None else Pivot(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "rect": self.rect.to_dict(),
            "pivot": self.pivot.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpriteRegion:
        return cls(
            id=str(data.get("id", uuid.uuid4().hex[:12])),
            name=str(data.get("name", "sprite")),
            rect=Rect.from_dict(data.get("rect", {})),
            pivot=Pivot.from_dict(data.get("pivot", {})),
        )

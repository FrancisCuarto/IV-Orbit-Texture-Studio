"""Modelo de datos para elementos independientes dentro del atlas de texturas.

Cada elemento del atlas representa una textura o sprite extraído (por ejemplo, mediante
rectificación de perspectiva en Texture Ripper o recorte) que cuenta con sus propios
píxeles RGBA y sus coordenadas (X, Y) de colocación dentro del lienzo del atlas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from iv_orbit_texture_studio.core.region import Pivot, Rect

RgbaArray = NDArray[np.uint8]


@dataclass
class AtlasItem:
    """Representa una textura o sprite individual colocado en el atlas."""

    id: str
    name: str
    pixels: RgbaArray
    x: int = 0
    y: int = 0
    pivot: Pivot = field(default_factory=Pivot)

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)

    @classmethod
    def create(
        cls,
        name: str,
        pixels: RgbaArray,
        x: int = 0,
        y: int = 0,
        pivot: Pivot | None = None,
    ) -> AtlasItem:
        if pixels.ndim != 3 or pixels.shape[2] != 4 or pixels.dtype != np.uint8:
            raise ValueError(
                f"Se esperaba un arreglo RGBA uint8 con forma (H, W, 4), "
                f"recibido: {pixels.dtype} {pixels.shape}"
            )
        return cls(
            id=uuid.uuid4().hex[:12],
            name=name,
            pixels=pixels,
            x=x,
            y=y,
            pivot=pivot if pivot is not None else Pivot(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "pivot": self.pivot.to_dict(),
            "asset_filename": f"assets/items/{self.id}.png",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], pixels: RgbaArray) -> AtlasItem:
        return cls(
            id=str(data.get("id", uuid.uuid4().hex[:12])),
            name=str(data.get("name", "item")),
            pixels=pixels,
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            pivot=Pivot.from_dict(data.get("pivot", {})),
        )

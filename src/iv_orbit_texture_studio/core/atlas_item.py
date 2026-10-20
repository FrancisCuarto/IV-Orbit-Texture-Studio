"""Modelo de datos para elementos independientes dentro del atlas de texturas.

Cada elemento del atlas representa una textura o sprite extraído (por ejemplo, mediante
rectificación de perspectiva en Texture Ripper o recorte) que cuenta con sus propios
píxeles RGBA y sus coordenadas (X, Y) de colocación dentro del lienzo del atlas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import cv2
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
    source_pixels: RgbaArray | None = None

    def __post_init__(self) -> None:
        if self.source_pixels is None:
            self.source_pixels = self.pixels

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])

    @property
    def source_width(self) -> int:
        assert self.source_pixels is not None
        return int(self.source_pixels.shape[1])

    @property
    def source_height(self) -> int:
        assert self.source_pixels is not None
        return int(self.source_pixels.shape[0])

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)

    def resize_pixels(self, new_width: int, new_height: int) -> None:
        """Redimensiona la textura a nuevas dimensiones con interpolación de alta calidad.

        Toma como origen ``source_pixels`` para evitar la degradación acumulativa de
        escalar repetidamente una imagen ya remuestreada.
        """
        w = max(1, int(new_width))
        h = max(1, int(new_height))
        if self.width == w and self.height == h:
            return

        src = self.source_pixels if self.source_pixels is not None else self.pixels
        src_h, src_w = src.shape[:2]

        if w == src_w and h == src_h:
            self.pixels = src
            return

        interp = cv2.INTER_AREA if (w < src_w and h < src_h) else cv2.INTER_LINEAR
        resized = cv2.resize(src, (w, h), interpolation=interp)
        if resized.ndim == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGBA)
        resized_arr: RgbaArray = np.ascontiguousarray(resized, dtype=np.uint8)
        resized_arr.setflags(write=False)
        self.pixels = resized_arr

    def reset_to_source_size(self) -> tuple[int, int]:
        """Restaura la textura a su tamaño original sin pérdida de resolución."""
        if self.source_pixels is not None:
            self.pixels = self.source_pixels
        return self.width, self.height

    @classmethod
    def create(
        cls,
        name: str,
        pixels: RgbaArray,
        x: int = 0,
        y: int = 0,
        pivot: Pivot | None = None,
        source_pixels: RgbaArray | None = None,
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
            source_pixels=source_pixels if source_pixels is not None else pixels,
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
            source_pixels=pixels,
        )

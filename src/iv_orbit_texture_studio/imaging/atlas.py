"""Motor de empaquetado 2D de sprites y generación de textura Atlas.

Implementa un algoritmo de empaquetado de rectángulos (MaxRects - Best Short Side Fit)
garantizando cero solapamientos, márgenes anti-sangrado (bleeding padding/spacing),
soporte para dimensiones potencia de dos (POT) y generación de metadatos JSON estándar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from iv_orbit_texture_studio.core.region import Pivot, Rect, SpriteRegion

RgbaArray = NDArray[np.uint8]


class AtlasFitError(Exception):
    """Se lanza cuando los sprites no caben dentro de las dimensiones máximas del atlas."""


@dataclass(frozen=True, slots=True)
class PackedSprite:
    """Información de un sprite colocado dentro del atlas."""

    region_id: str
    name: str
    source_rect: Rect
    atlas_rect: Rect
    pivot: Pivot

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "name": self.name,
            "source_rect": self.source_rect.to_dict(),
            "frame": self.atlas_rect.to_dict(),
            "pivot": self.pivot.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AtlasResult:
    """Resultado final del empaquetado de atlas."""

    image: RgbaArray
    width: int
    height: int
    sprites: tuple[PackedSprite, ...]
    metadata: dict[str, Any]


def next_power_of_two(value: int) -> int:
    """Devuelve la menor potencia de dos mayor o igual que ``value``."""
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


class MaxRectsPacker:
    """Empaquetador de rectángulos 2D basado en el algoritmo MaxRects (BSSF)."""

    def __init__(self, max_width: int, max_height: int) -> None:
        self.max_width = max_width
        self.max_height = max_height
        self.used_rects: list[Rect] = []
        self.free_rects: list[Rect] = [Rect(0, 0, max_width, max_height)]

    def insert(self, width: int, height: int) -> Rect | None:
        """Encuentra la mejor ubicación para un rectángulo de (width, height)."""
        best_rect: Rect | None = None
        best_short_side = float("inf")
        best_long_side = float("inf")

        for free in self.free_rects:
            if free.width >= width and free.height >= height:
                remain_x = free.width - width
                remain_y = free.height - height
                short_side = min(remain_x, remain_y)
                long_side = max(remain_x, remain_y)

                if short_side < best_short_side or (
                    short_side == best_short_side and long_side < best_long_side
                ):
                    best_rect = Rect(free.x, free.y, width, height)
                    best_short_side = short_side
                    best_long_side = long_side

        if best_rect is None:
            return None

        self._split_free_rectangles(best_rect)
        self._prune_free_rectangles()
        self.used_rects.append(best_rect)
        return best_rect

    def _split_free_rectangles(self, placed: Rect) -> None:
        new_free: list[Rect] = []

        for free in self.free_rects:
            if not free.intersects(placed):
                new_free.append(free)
                continue

            # Generar hasta 4 nuevos rectángulos alrededor del colocado
            # 1. Arriba
            if placed.top > free.top:
                new_free.append(Rect(free.x, free.top, free.width, placed.top - free.top))
            # 2. Abajo
            if placed.bottom < free.bottom:
                new_free.append(
                    Rect(free.x, placed.bottom, free.width, free.bottom - placed.bottom)
                )
            # 3. Izquierda
            if placed.left > free.left:
                new_free.append(Rect(free.left, free.y, placed.left - free.left, free.height))
            # 4. Derecha
            if placed.right < free.right:
                new_free.append(Rect(placed.right, free.y, free.right - placed.right, free.height))

        self.free_rects = new_free

    def _prune_free_rectangles(self) -> None:
        # Eliminar rectángulos libres contenidos completamente dentro de otros
        i = 0
        while i < len(self.free_rects):
            j = i + 1
            while j < len(self.free_rects):
                r1 = self.free_rects[i]
                r2 = self.free_rects[j]

                # Si r1 contiene a r2
                if (
                    r1.left <= r2.left
                    and r1.right >= r2.right
                    and r1.top <= r2.top
                    and r1.bottom >= r2.bottom
                ):
                    del self.free_rects[j]
                # Si r2 contiene a r1
                elif (
                    r2.left <= r1.left
                    and r2.right >= r1.right
                    and r2.top <= r1.top
                    and r2.bottom >= r1.bottom
                ):
                    del self.free_rects[i]
                    i -= 1
                    break
                else:
                    j += 1
            i += 1


def pack_sprites_to_atlas(
    sprites_with_pixels: list[tuple[SpriteRegion, RgbaArray]],
    *,
    padding: int = 2,
    spacing: int = 2,
    max_width: int = 4096,
    max_height: int = 4096,
    power_of_two: bool = True,
    square: bool = False,
    atlas_image_name: str = "atlas.png",
) -> AtlasResult:
    """Empaqueta una lista de sprites en un atlas 2D sin solapamientos.

    Args:
        sprites_with_pixels: Lista de pares (SpriteRegion, pixel_array).
        padding: Margen exterior del atlas en píxeles.
        spacing: Separación entre sprites adyacentes para evitar sangrado de textura.
        max_width: Ancho máximo permitido para el atlas.
        max_height: Alto máximo permitido para el atlas.
        power_of_two: Si es True, redondea el tamaño a potencia de dos (e.g. 256, 512, 1024).
        square: Si es True, obliga a que ancho == alto.
        atlas_image_name: Nombre de archivo de la imagen que se grabará en los metadatos JSON.

    Returns:
        AtlasResult con la imagen empaquetada, dimensiones, lista de sprites y metadatos.

    Raises:
        AtlasFitError: Si los sprites no caben dentro de max_width x max_height.
    """
    if not sprites_with_pixels:
        empty_img = np.zeros((32, 32, 4), dtype=np.uint8)
        return AtlasResult(
            image=empty_img,
            width=32,
            height=32,
            sprites=(),
            metadata={
                "meta": {"image": atlas_image_name, "size": {"w": 32, "h": 32}},
                "frames": {},
            },
        )

    # Ordenar por altura decreciente (o dimensión mayor) para optimizar el empaquetado
    sorted_items = sorted(
        sprites_with_pixels,
        key=lambda item: max(item[0].rect.width, item[0].rect.height),
        reverse=True,
    )

    packer = MaxRectsPacker(max_width, max_height)
    placed_info: list[tuple[SpriteRegion, RgbaArray, Rect]] = []

    max_right = 0
    max_bottom = 0

    for region, pixels in sorted_items:
        # Añadir espaciado al ancho/alto para la colocación
        item_w = region.rect.width + spacing
        item_h = region.rect.height + spacing

        placed_rect = packer.insert(item_w, item_h)
        if placed_rect is None:
            raise AtlasFitError(
                f"El sprite '{region.name}' ({region.rect.width}x{region.rect.height} px) "
                f"no cabe en el atlas con límite de {max_width}x{max_height} px."
            )

        # La posición real del sprite no incluye el espaciado
        sprite_atlas_rect = Rect(
            x=placed_rect.x + padding,
            y=placed_rect.y + padding,
            width=region.rect.width,
            height=region.rect.height,
        )
        placed_info.append((region, pixels, sprite_atlas_rect))

        max_right = max(max_right, sprite_atlas_rect.right + padding)
        max_bottom = max(max_bottom, sprite_atlas_rect.bottom + padding)

    # Determinar dimensiones finales del atlas
    final_w = max_right
    final_h = max_bottom

    if power_of_two:
        final_w = next_power_of_two(final_w)
        final_h = next_power_of_two(final_h)

    if square:
        side = max(final_w, final_h)
        if power_of_two:
            side = next_power_of_two(side)
        final_w = side
        final_h = side

    if final_w > max_width or final_h > max_height:
        raise AtlasFitError(
            f"El tamaño final del atlas ({final_w}x{final_h} px) "
            f"excede los límites admitidos ({max_width}x{max_height} px)."
        )

    # Validar que no existan solapamientos entre ninguno de los rectángulos colocados
    for i in range(len(placed_info)):
        for j in range(i + 1, len(placed_info)):
            r1 = placed_info[i][2]
            r2 = placed_info[j][2]
            if r1.intersects(r2):
                raise RuntimeError(
                    f"Error interno: Solapamiento detectado entre '{placed_info[i][0].name}' "
                    f"y '{placed_info[j][0].name}'."
                )

    # Construir la imagen del atlas
    atlas_image = np.zeros((final_h, final_w, 4), dtype=np.uint8)

    packed_sprites: list[PackedSprite] = []
    frames_dict: dict[str, Any] = {}

    for region, pixels, atlas_rect in placed_info:
        # Copiar píxeles del sprite al lienzo del atlas
        atlas_image[
            atlas_rect.y : atlas_rect.bottom,
            atlas_rect.x : atlas_rect.right,
        ] = pixels

        ps = PackedSprite(
            region_id=region.id,
            name=region.name,
            source_rect=region.rect,
            atlas_rect=atlas_rect,
            pivot=region.pivot,
        )
        packed_sprites.append(ps)

        frames_dict[region.name] = {
            "frame": {
                "x": atlas_rect.x,
                "y": atlas_rect.y,
                "w": atlas_rect.width,
                "h": atlas_rect.height,
            },
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {
                "x": 0,
                "y": 0,
                "w": atlas_rect.width,
                "h": atlas_rect.height,
            },
            "sourceSize": {
                "w": atlas_rect.width,
                "h": atlas_rect.height,
            },
            "pivot": {
                "x": round(region.pivot.x, 4),
                "y": round(region.pivot.y, 4),
            },
        }

    metadata = {
        "meta": {
            "app": "IV Orbit Texture Studio",
            "version": "1.0",
            "image": atlas_image_name,
            "format": "RGBA8888",
            "size": {"w": final_w, "h": final_h},
            "scale": 1.0,
        },
        "frames": frames_dict,
    }

    atlas_image.setflags(write=False)
    return AtlasResult(
        image=atlas_image,
        width=final_w,
        height=final_h,
        sprites=tuple(packed_sprites),
        metadata=metadata,
    )

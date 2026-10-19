"""Pipeline de transformación y preparación de texturas.

Combina filtros de color (brillo, contraste, saturación, balance, iluminación)
y generación de costuras continuas (seamless).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from iv_orbit_texture_studio.core.document import TexturePrepSettings
from iv_orbit_texture_studio.imaging.color import (
    adjust_brightness_contrast,
    adjust_color_balance,
    adjust_saturation,
    equalize_illumination,
)
from iv_orbit_texture_studio.imaging.seamless import (
    create_tiled_preview,
    generate_seamless_texture,
)

RgbaArray = NDArray[np.uint8]


def process_texture_pipeline(
    pixels: RgbaArray,
    settings: TexturePrepSettings,
    tiled: bool = False,
) -> RgbaArray:
    """Aplica la secuencia completa de procesamiento y filtros a una textura.

    Orden de ejecución:
    1. Ecualización de iluminación (si > 0).
    2. Ajustes de brillo y contraste (si != 0).
    3. Ajuste de saturación (si != 0).
    4. Balance de color RGB (si alguna ganancia != 1.0).
    5. Generación seamless (si seamless_enabled es True).
    6. Mosaico repetido N x M (si tiled es True).

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        settings: Parámetros de filtros y seamless.
        tiled: Si es True, produce el mosaico N x M según settings.tiling_grid_x/y.

    Returns:
        Nuevo arreglo RGBA uint8 procesado.
    """
    res = np.copy(pixels)

    if settings.equalize_light > 0.0:
        res = equalize_illumination(res, strength=settings.equalize_light)

    if settings.brightness != 0.0 or settings.contrast != 0.0:
        res = adjust_brightness_contrast(
            res, brightness=settings.brightness, contrast=settings.contrast
        )

    if settings.saturation != 0.0:
        res = adjust_saturation(res, saturation=settings.saturation)

    if settings.red_gain != 1.0 or settings.green_gain != 1.0 or settings.blue_gain != 1.0:
        res = adjust_color_balance(
            res,
            red_gain=settings.red_gain,
            green_gain=settings.green_gain,
            blue_gain=settings.blue_gain,
        )

    if settings.seamless_enabled:
        res = generate_seamless_texture(
            res,
            blend_ratio=settings.seamless_blend,
        )

    if tiled:
        res = create_tiled_preview(
            res,
            grid_x=settings.tiling_grid_x,
            grid_y=settings.tiling_grid_y,
        )

    return res

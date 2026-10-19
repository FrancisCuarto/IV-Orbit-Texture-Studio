"""Generación de texturas sin costuras (seamless / tileable) y previsualización en mosaico.

Procesa arreglos NumPy uint8 en formato RGBA (H, W, 4) de manera pura e independiente de Qt.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

RgbaArray = NDArray[np.uint8]


def generate_seamless_texture(
    pixels: RgbaArray,
    blend_ratio: float = 0.20,
    linear: bool = False,
) -> RgbaArray:
    """Genera una textura repetible (seamless) sin costuras visibles en los bordes.

    Aplica un algoritmo de mezcla cruzada separable en dos fases (horizontal y vertical).
    En cada dimensión traslada el borde original al centro mediante desfase toroidal (roll)
    y lo fusiona suavemente con la imagen previa, garantizando matemáticamente que los
    bordes opuestos conecten con continuidad perfecta (adyacencia original).

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        blend_ratio: Fracción del tamaño de la imagen utilizada para la zona de transición
            de mezcla. Típicamente entre 0.05 (5 %) y 0.35 (35 %). Por defecto 0.20 (20 %).
        linear: Si es True, utiliza una rampa de fusión lineal. Si es False (por defecto),
            utiliza una curva cosenoidal suave (smootherstep) para evitar cambios
            bruscos de derivada.

    Returns:
        Nuevo arreglo RGBA uint8 con las costuras eliminadas y bordes 100 % coincidentes.
    """
    h, w = pixels.shape[:2]
    if h < 4 or w < 4:
        return np.copy(pixels)

    blend_ratio = float(np.clip(blend_ratio, 0.02, 0.45))
    bw = max(2, int(round(w * blend_ratio)))
    bh = max(2, int(round(h * blend_ratio)))

    # -------------------------------------------------- Fase 1: Fusión Horizontal
    shift_x = w // 2
    shifted_x = np.roll(pixels, shift=shift_x, axis=1)

    xs = np.arange(w)
    dist_x = np.abs(xs - shift_x).astype(np.float32)
    ramp_x = np.clip(1.0 - (dist_x / bw), 0.0, 1.0)
    if not linear:
        ramp_x = 0.5 * (1.0 - np.cos(np.pi * ramp_x))

    weight_x = ramp_x.reshape(1, w, 1)
    h_seamless = pixels.astype(np.float32) * weight_x + shifted_x.astype(np.float32) * (
        1.0 - weight_x
    )

    # ---------------------------------------------------- Fase 2: Fusión Vertical
    shift_y = h // 2
    shifted_y = np.roll(h_seamless, shift=shift_y, axis=0)

    ys = np.arange(h)
    dist_y = np.abs(ys - shift_y).astype(np.float32)
    ramp_y = np.clip(1.0 - (dist_y / bh), 0.0, 1.0)
    if not linear:
        ramp_y = 0.5 * (1.0 - np.cos(np.pi * ramp_y))

    weight_y = ramp_y.reshape(h, 1, 1)
    v_seamless = h_seamless * weight_y + shifted_y * (1.0 - weight_y)

    return np.clip(v_seamless, 0.0, 255.0).astype(np.uint8)


def create_tiled_preview(
    pixels: RgbaArray,
    grid_x: int = 3,
    grid_y: int = 3,
) -> RgbaArray:
    """Crea una imagen compuesta repitiendo la textura en una cuadrícula N x M.

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        grid_x: Cantidad de repeticiones horizontales (>= 1).
        grid_y: Cantidad de repeticiones verticales (>= 1).

    Returns:
        Nuevo arreglo RGBA uint8 de tamaño (H * grid_y, W * grid_x, 4).
    """
    gx = max(1, grid_x)
    gy = max(1, grid_y)
    return np.tile(pixels, (gy, gx, 1))

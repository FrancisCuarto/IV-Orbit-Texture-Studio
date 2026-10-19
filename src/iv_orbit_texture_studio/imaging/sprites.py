"""Motor de detección y extracción de sprites mediante transparencia (canal alfa).

Funciones independientes de la interfaz que operan sobre arreglos NumPy RGBA.
"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from iv_orbit_texture_studio.core.region import Rect

RgbaArray = NDArray[np.uint8]


def detect_sprites_by_transparency(
    image_pixels: RgbaArray,
    alpha_threshold: int = 10,
    min_area: int = 4,
    padding: int = 0,
) -> list[Rect]:
    """Detecta componentes conexos no transparentes en una imagen RGBA.

    Args:
        image_pixels: Arreglo NumPy con forma (H, W, 4) y tipo uint8.
        alpha_threshold: Valor alfa mínimo (1-255) para considerar un píxel opaco.
        min_area: Área mínima en píxeles para ignorar ruido o puntos aislados.
        padding: Margen adicional en píxeles alrededor de cada sprite detectado.

    Returns:
        Lista de rectángulos detectados ordenados de arriba hacia abajo y de izquierda a derecha.
    """
    if image_pixels.ndim != 3 or image_pixels.shape[2] != 4:
        raise ValueError(
            f"Se esperaba una imagen RGBA con 4 canales, forma recibida: {image_pixels.shape}"
        )

    img_h, img_w = image_pixels.shape[:2]
    alpha_channel = image_pixels[:, :, 3]

    # Máscara binaria de opacidad
    mask = (alpha_channel >= alpha_threshold).astype(np.uint8)

    # Componentes conexos con conectividad 8 (diagonales conectadas)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    raw_rects: list[Rect] = []

    # El índice 0 siempre corresponde al fondo transparente
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area:
            continue

        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])

        if padding > 0:
            px = max(0, x - padding)
            py = max(0, y - padding)
            pw = min(img_w - px, w + (x - px) + padding)
            ph = min(img_h - py, h + (y - py) + padding)
        else:
            px, py, pw, ph = x, y, w, h

        if pw > 0 and ph > 0:
            raw_rects.append(Rect(px, py, pw, ph))

    # Fusionar rectángulos si el padding causó solapamientos
    merged = merge_overlapping_rects(raw_rects)

    # Ordenar lectura natural: líneas horizontales aproximadas, luego X
    # Agrupamos por bandas de 16 px verticales para ordenar filas ordenadas
    merged.sort(key=lambda r: (r.y // 16, r.x))
    return merged


def merge_overlapping_rects(rects: list[Rect]) -> list[Rect]:
    """Combina rectángulos que se solapan en una única caja contenedora."""
    if not rects:
        return []

    result: list[Rect] = []
    pending = list(rects)

    while pending:
        current = pending.pop(0)
        merged_any = False
        remaining: list[Rect] = []

        for other in pending:
            if current.intersects(other):
                # Unir en una caja mayor
                nx = min(current.x, other.x)
                ny = min(current.y, other.y)
                nw = max(current.right, other.right) - nx
                nh = max(current.bottom, other.bottom) - ny
                current = Rect(nx, ny, nw, nh)
                merged_any = True
            else:
                remaining.append(other)

        pending = remaining
        if merged_any:
            # Reinsertar para seguir comprobando solapamientos con las cajas restantes
            pending.insert(0, current)
        else:
            result.append(current)

    return result


def extract_sprite_pixels(image_pixels: RgbaArray, rect: Rect) -> RgbaArray:
    """Extrae el recorte de píxeles correspondiente a un rectángulo de la imagen.

    Retorna un nuevo arreglo NumPy RGBA contiguous y de solo lectura.
    """
    img_h, img_w = image_pixels.shape[:2]
    clamped = rect.clamped(img_w, img_h)

    crop = image_pixels[clamped.y : clamped.bottom, clamped.x : clamped.right]
    result = np.ascontiguousarray(crop)
    result.setflags(write=False)
    return result

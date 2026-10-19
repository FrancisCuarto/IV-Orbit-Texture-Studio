"""Funciones de procesamiento y ajuste de color independientes de la interfaz.

Trabajan sobre arreglos NumPy uint8 de forma (H, W, 4) en orden RGBA.
Todas las funciones retornan un arreglo nuevo sin mutar la entrada.
"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

RgbaArray = NDArray[np.uint8]


def adjust_brightness_contrast(
    pixels: RgbaArray,
    brightness: float = 0.0,
    contrast: float = 0.0,
) -> RgbaArray:
    """Ajusta brillo y contraste sobre los canales RGB, preservando el canal alfa.

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        brightness: Desplazamiento de brillo en el rango [-1.0, 1.0].
            0.0 significa sin cambio; 1.0 satura a blanco; -1.0 a negro.
        contrast: Factor de contraste en el rango [-1.0, 1.0].
            0.0 significa sin cambio; > 0 incrementa el contraste; < 0 lo reduce.

    Returns:
        Nuevo arreglo RGBA uint8 con los ajustes aplicados.
    """
    if brightness == 0.0 and contrast == 0.0:
        return np.copy(pixels)

    # Separar RGB y Alfa
    rgb = pixels[:, :, :3].astype(np.float32)
    alpha = pixels[:, :, 3:]

    # Ajuste de contraste: factor multiplicativo alrededor del punto medio 127.5
    # contrast en [-1.0, 1.0] se mapea a factor alpha_c > 0
    factor = 1.0 + contrast * 3.0 if contrast >= 0.0 else 1.0 + contrast * 0.9

    adjusted = (rgb - 127.5) * factor + 127.5

    # Ajuste de brillo: desplazamiento aditivo
    if brightness != 0.0:
        adjusted += brightness * 255.0

    # Limitar rango a [0, 255]
    adjusted_clamped = np.clip(adjusted, 0.0, 255.0).astype(np.uint8)

    # Recombinar con el canal alfa intacto
    return np.dstack((adjusted_clamped, alpha))


def adjust_saturation(
    pixels: RgbaArray,
    saturation: float = 0.0,
) -> RgbaArray:
    """Ajusta la saturación de color utilizando el espacio de color HSV.

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        saturation: Factor de saturación en el rango [-1.0, 1.0].
            0.0 significa sin cambio; -1.0 es escala de grises completa; > 0 intensifica colores.

    Returns:
        Nuevo arreglo RGBA uint8 con la saturación ajustada.
    """
    if saturation == 0.0:
        return np.copy(pixels)

    rgb = pixels[:, :, :3]
    alpha = pixels[:, :, 3:]

    # Convertir RGB a HSV (OpenCV usa BGR por defecto, así que usamos COLOR_RGB2HSV)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)

    # Escalar canal S (índice 1 en HSV)
    s_factor = 1.0 + saturation * 2.0 if saturation >= 0.0 else 1.0 + saturation

    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * s_factor, 0.0, 255.0)

    # Convertir de vuelta a RGB
    adjusted_rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

    return np.dstack((adjusted_rgb, alpha))


def adjust_color_balance(
    pixels: RgbaArray,
    red_gain: float = 1.0,
    green_gain: float = 1.0,
    blue_gain: float = 1.0,
) -> RgbaArray:
    """Ajusta la ganancia independiente para cada canal de color RGB (temperatura/tinte).

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        red_gain: Multiplicador para el canal rojo (ej. 0.0 a 2.0; 1.0 = sin cambio).
        green_gain: Multiplicador para el canal verde.
        blue_gain: Multiplicador para el canal azul.

    Returns:
        Nuevo arreglo RGBA uint8 ajustado.
    """
    if red_gain == 1.0 and green_gain == 1.0 and blue_gain == 1.0:
        return np.copy(pixels)

    rgb = pixels[:, :, :3].astype(np.float32)
    alpha = pixels[:, :, 3:]

    rgb[:, :, 0] *= max(0.0, red_gain)
    rgb[:, :, 1] *= max(0.0, green_gain)
    rgb[:, :, 2] *= max(0.0, blue_gain)

    clamped_rgb = np.clip(rgb, 0.0, 255.0).astype(np.uint8)
    return np.dstack((clamped_rgb, alpha))


def equalize_illumination(
    pixels: RgbaArray,
    strength: float = 0.5,
) -> RgbaArray:
    """Atenúa gradientes de iluminación desparejos o sombras suaves (flatten illumination).

    Calcula una estimación de la iluminación ambiente de baja frecuencia mediante un
    desenfoque gaussiano de gran radio sobre la luminancia y normaliza los detalles locales.

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        strength: Intensidad de la corrección en el rango [0.0, 1.0].
            0.0 = sin cambio; 1.0 = máxima nivelación de iluminación.

    Returns:
        Nuevo arreglo RGBA uint8 con la iluminación corregida.
    """
    if strength <= 0.0:
        return np.copy(pixels)

    strength = float(np.clip(strength, 0.0, 1.0))
    h, w = pixels.shape[:2]

    # Convertir a espacio de color LAB donde L es luminosidad/iluminación perceptiva
    rgb = pixels[:, :, :3]
    alpha = pixels[:, :, 3:]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    l_channel = lab[:, :, 0]

    # Radio proporcional al tamaño de la imagen para capturar solo las frecuencias muy bajas
    sigma = max(15.0, min(w, h) * 0.2)
    # Kernel impar
    ksize = int(sigma * 4) | 1
    ksize = max(15, min(ksize, min(w, h) // 2 | 1))

    # Iluminación de baja frecuencia (gradiente suave de luz)
    low_freq_light = cv2.GaussianBlur(l_channel, (ksize, ksize), sigma)

    # Nivel medio global
    mean_light = np.mean(l_channel)

    # Componente de alta frecuencia corregido: L_nuevo = L - (low_freq - mean) * strength
    l_corrected = l_channel - (low_freq_light - mean_light) * strength
    lab[:, :, 0] = np.clip(l_corrected, 0.0, 255.0)

    corrected_rgb = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
    return np.dstack((corrected_rgb, alpha))

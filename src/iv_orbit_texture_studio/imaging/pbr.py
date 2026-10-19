"""Motor de generación de mapas PBR (Normal, Height, Roughness, Oclusión Ambiental).

Implementa algoritmos numéricos en OpenCV y NumPy para derivar materiales PBR completos
a partir de texturas difusas / albedo sin dependencias de interfaz gráfica.
"""

from __future__ import annotations

import cv2
import numpy as np

# Tipo de arreglo RGBA estándar (H, W, 4) uint8
RgbaArray = np.ndarray


def rgb_to_luminance(pixels: RgbaArray) -> np.ndarray:
    """Calcula la luminancia relativa en punto flotante [0.0, 1.0].

    Usa los coeficientes fotométricos estándar Rec. 601 / 709 (0.299 R + 0.587 G + 0.114 B).
    """
    rgb = pixels[:, :, :3].astype(np.float32)
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    return lum / 255.0


def generate_height_map(
    pixels: RgbaArray,
    invert: bool = False,
    contrast: float = 1.0,
    brightness: float = 0.0,
    blur_radius: int = 0,
) -> RgbaArray:
    """Genera un mapa de relieve / altura (Height map) a partir de la textura.

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        invert: Si es True, invierte las alturas (lo oscuro se vuelve alto).
        contrast: Factor multiplicativo de contraste (típicamente 0.5 a 3.0).
        brightness: Desplazamiento aditivo de brillo en [-1.0, 1.0].
        blur_radius: Radio en píxeles para suavizado gaussiano previo (0 = sin suavizado).

    Returns:
        Arreglo RGBA uint8 (H, W, 4) con el mapa de altura en escala de grises.
    """
    lum = rgb_to_luminance(pixels)

    if blur_radius > 0:
        ksize = blur_radius * 2 + 1
        lum = cv2.GaussianBlur(lum, (ksize, ksize), 0)

    if invert:
        lum = 1.0 - lum

    # Aplicar contraste alrededor de 0.5 y sumar brillo
    h = (lum - 0.5) * contrast + 0.5 + brightness
    h_clamped = np.round(np.clip(h, 0.0, 1.0) * 255.0).astype(np.uint8)

    alpha = pixels[:, :, 3]
    return np.dstack((h_clamped, h_clamped, h_clamped, alpha))


def generate_normal_map(
    pixels: RgbaArray,
    strength: float = 2.0,
    format_opengl: bool = True,
    blur_radius: int = 0,
    invert_x: bool = False,
    invert_y: bool = False,
) -> RgbaArray:
    """Genera un mapa de normales en espacio tangente a partir de la textura.

    Utiliza el operador Sobel para calcular el gradiente superficial en X e Y,
    normalizando los vectores tridimensionales (Nx, Ny, Nz) en el rango [0, 255].

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        strength: Intensidad del relieve (multiplicador de gradiente, típicamente 0.5 a 10.0).
        format_opengl: True para formato OpenGL (+Y hacia arriba, Blender/Godot);
            False para DirectX (-Y hacia abajo, Unreal Engine/Unity DirectX).
        blur_radius: Suavizado previo para atenuar ruido de alta frecuencia (0 = sin suavizado).
        invert_x: Invierte el eje X (rojo).
        invert_y: Invierte el eje Y adicionalmente al formato seleccionado.

    Returns:
        Arreglo RGBA uint8 (H, W, 4) con el mapa de normales en espacio tangente (RGB).
    """
    lum = rgb_to_luminance(pixels)

    if blur_radius > 0:
        ksize = blur_radius * 2 + 1
        lum = cv2.GaussianBlur(lum, (ksize, ksize), 0)

    # Gradientes espaciales con operador Sobel (ksize=3)
    dx = cv2.Sobel(lum, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(lum, cv2.CV_32F, 0, 1, ksize=3)

    # Orientación de normales en espacio tangente
    # Un aumento en X genera pendiente hacia la derecha (-dx en vector normal hacia afuera)
    nx = -dx * strength
    ny = dy * strength if format_opengl else -dy * strength

    if invert_x:
        nx = -nx
    if invert_y:
        ny = -ny

    nz = np.ones_like(nx, dtype=np.float32)

    # Normalizar cada vector (Nx, Ny, Nz) a longitud unitaria
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    # Evitar división por cero
    length = np.maximum(length, 1e-6)

    nx = nx / length
    ny = ny / length
    nz = nz / length

    # Mapear de [-1.0, 1.0] a [0, 255]
    r = np.round(np.clip(nx * 0.5 + 0.5, 0.0, 1.0) * 255.0).astype(np.uint8)
    g = np.round(np.clip(ny * 0.5 + 0.5, 0.0, 1.0) * 255.0).astype(np.uint8)
    b = np.round(np.clip(nz * 0.5 + 0.5, 0.0, 1.0) * 255.0).astype(np.uint8)
    alpha = pixels[:, :, 3]

    return np.dstack((r, g, b, alpha))


def generate_roughness_map(
    pixels: RgbaArray,
    base_roughness: float = 0.5,
    detail_influence: float = 0.3,
    invert: bool = False,
    contrast: float = 1.0,
) -> RgbaArray:
    """Genera un mapa de rugosidad (Roughness) o suavidad (Glossiness).

    Extrae variaciones de alta frecuencia y las pondera alrededor de un valor base.
    Un valor de 0.0 representa una superficie tipo espejo reflectante; 1.0 mate completa.

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        base_roughness: Valor base central de rugosidad en [0.0, 1.0].
        detail_influence: Cuánto influyen las micro-variaciones de la textura (0.0 a 1.0).
        invert: Si es True, produce un mapa de suavidad (Glossiness = 1 - Roughness).
        contrast: Contraste de las variaciones.

    Returns:
        Arreglo RGBA uint8 (H, W, 4) en escala de grises.
    """
    lum = rgb_to_luminance(pixels)

    # Frecuencia alta = imagen original - imagen suavizada (laplaciano/diferencia gaussiana)
    blurred = cv2.GaussianBlur(lum, (7, 7), 0)
    high_freq = np.abs(lum - blurred) * 2.0

    roughness = base_roughness + (high_freq - 0.1) * detail_influence * contrast
    roughness = np.clip(roughness, 0.0, 1.0)

    if invert:
        roughness = 1.0 - roughness

    val = np.round(roughness * 255.0).astype(np.uint8)
    alpha = pixels[:, :, 3]
    return np.dstack((val, val, val, alpha))


def generate_ao_map(
    pixels: RgbaArray,
    strength: float = 1.5,
    blur_radius: int = 5,
    contrast: float = 1.0,
) -> RgbaArray:
    """Genera un mapa de oclusión ambiental (Ambient Occlusion) aproximado.

    Detecta valles y cavidades profundas analizando la concavidad local de la superficie.

    Args:
        pixels: Arreglo RGBA uint8 (H, W, 4).
        strength: Intensidad de las sombras de contacto en cavidades (0.0 a 3.0).
        blur_radius: Radio del vecindario para evaluar la profundidad local.
        contrast: Contraste de la oclusión.

    Returns:
        Arreglo RGBA uint8 (H, W, 4) en escala de grises.
    """
    lum = rgb_to_luminance(pixels)

    ksize = max(3, blur_radius * 2 + 1)
    blurred = cv2.GaussianBlur(lum, (ksize, ksize), 0)

    # Concavidad: donde el vecindario promedio es más alto que el píxel local
    cavity = np.maximum(0.0, blurred - lum)

    # Oclusión: 1.0 (blanco, sin sombra) en zonas planas/altas, y menor en cavidades
    ao = 1.0 - cavity * strength * contrast
    ao_clamped = np.round(np.clip(ao, 0.0, 1.0) * 255.0).astype(np.uint8)

    alpha = pixels[:, :, 3]
    return np.dstack((ao_clamped, ao_clamped, ao_clamped, alpha))


def pack_orm_map(
    ao_pixels: RgbaArray,
    roughness_pixels: RgbaArray,
    metallic_value: float = 0.0,
    format_rma: bool = False,
) -> RgbaArray:
    """Empaqueta mapas en canales estándar de textura PBR (ORM o RMA).

    Formato ORM (Godot 4, Unreal Engine estándar):
        R: Occlusion (AO)
        G: Roughness
        B: Metallic

    Formato RMA (Unity HDRP / algunos shaders personalizados):
        R: Roughness
        G: Metallic
        B: Occlusion (AO)

    Args:
        ao_pixels: Arreglo RGBA uint8 del mapa de AO.
        roughness_pixels: Arreglo RGBA uint8 del mapa de rugosidad.
        metallic_value: Valor constante metálico en [0.0, 1.0] (por defecto 0.0 = no metálico).
        format_rma: Si es True empaqueta como RMA; si es False empaqueta como ORM.

    Returns:
        Arreglo RGBA uint8 (H, W, 4) empaquetado.
    """
    h, w = ao_pixels.shape[:2]
    ao_channel = ao_pixels[:, :, 0]
    rough_channel = roughness_pixels[:, :, 0]
    metal_channel = np.full(
        (h, w), int(round(np.clip(metallic_value, 0.0, 1.0) * 255.0)), dtype=np.uint8
    )
    alpha = np.full((h, w), 255, dtype=np.uint8)

    if format_rma:
        return np.dstack((rough_channel, metal_channel, ao_channel, alpha))
    return np.dstack((ao_channel, rough_channel, metal_channel, alpha))

"""Pruebas unitarias para la generación de texturas seamless y mosaico."""

import numpy as np

from iv_orbit_texture_studio.imaging.seamless import (
    create_tiled_preview,
    generate_seamless_texture,
)


def test_tiled_preview_shape():
    arr = np.full((50, 60, 4), 128, dtype=np.uint8)
    tiled = create_tiled_preview(arr, grid_x=3, grid_y=2)
    assert tiled.shape == (100, 180, 4)
    # Verificar que el contenido coincide
    assert np.array_equal(tiled[:50, :60], arr)
    assert np.array_equal(tiled[50:, 60:120], arr)


def test_tiled_preview_minimum_grid():
    arr = np.full((10, 10, 4), 255, dtype=np.uint8)
    tiled = create_tiled_preview(arr, grid_x=0, grid_y=-1)
    # Debe limitar a mínimo 1x1
    assert tiled.shape == (10, 10, 4)


def test_generate_seamless_texture_continuity():
    # Crear una imagen con gradiente fuerte horizontal y vertical (altamente discontinua)
    h, w = 100, 100
    grid_y, grid_x = np.mgrid[0:h, 0:w]
    # En la imagen original, los bordes opuestos difieren mucho
    pixels_r = (grid_x * 2.5).astype(np.uint8)
    pixels_g = (grid_y * 2.5).astype(np.uint8)
    pixels_b = np.full((h, w), 100, dtype=np.uint8)
    pixels_a = np.full((h, w), 255, dtype=np.uint8)
    original = np.dstack([pixels_r, pixels_g, pixels_b, pixels_a])

    # En la original, la diferencia entre borde izquierdo y derecho es enorme
    orig_x_diff = np.abs(original[:, 0, 0].astype(int) - original[:, -1, 0].astype(int))
    assert np.mean(orig_x_diff) > 200

    # Generar versión seamless
    seamless = generate_seamless_texture(original, blend_ratio=0.20, linear=False)
    assert seamless.shape == original.shape
    assert seamless.dtype == np.uint8

    # Al crear un mosaico 2x2, la costura entre el mosaico (0,0) y el mosaico (0,1) debe ser suave
    # Es decir, la diferencia entre la última columna de un tile y la primera columna del siguiente
    # debe ser mínima / idéntica a la continuidad interna
    tiled = create_tiled_preview(seamless, grid_x=2, grid_y=2)
    # Columna w-1 vs columna w en el mosaico
    seam_diff_x = np.abs(tiled[:, w - 1, :3].astype(int) - tiled[:, w, :3].astype(int))
    # La diferencia en la costura debe ser muy pequeña (típicamente <= 3 debido
    # a la adyacencia original)
    assert np.mean(seam_diff_x) < 5.0

    # Fila h-1 vs fila h en el mosaico
    seam_diff_y = np.abs(tiled[h - 1, :, :3].astype(int) - tiled[h, :, :3].astype(int))
    assert np.mean(seam_diff_y) < 5.0


def test_generate_seamless_small_image():
    small = np.full((2, 2, 4), 200, dtype=np.uint8)
    res = generate_seamless_texture(small)
    assert np.array_equal(res, small)
    assert res is not small

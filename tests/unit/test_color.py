"""Pruebas unitarias para las transformaciones y ajustes de color."""

import numpy as np

from iv_orbit_texture_studio.imaging.color import (
    adjust_brightness_contrast,
    adjust_color_balance,
    adjust_saturation,
    equalize_illumination,
)


def test_brightness_contrast_neutral():
    arr = np.full((10, 10, 4), [100, 150, 200, 255], dtype=np.uint8)
    res = adjust_brightness_contrast(arr, brightness=0.0, contrast=0.0)
    assert np.array_equal(res, arr)
    assert res is not arr  # nuevo arreglo


def test_brightness_shift():
    arr = np.full((10, 10, 4), [100, 100, 100, 200], dtype=np.uint8)
    # Aumentar brillo
    brighter = adjust_brightness_contrast(arr, brightness=0.2, contrast=0.0)
    assert brighter[0, 0, 0] > 100
    assert brighter[0, 0, 3] == 200  # canal alfa inalterado

    # Disminuir brillo
    darker = adjust_brightness_contrast(arr, brightness=-0.2, contrast=0.0)
    assert darker[0, 0, 0] < 100
    assert darker[0, 0, 3] == 200


def test_contrast_shift():
    # Gradiente de gris de 50 a 200
    arr = np.zeros((1, 2, 4), dtype=np.uint8)
    arr[0, 0] = [50, 50, 50, 255]
    arr[0, 1] = [200, 200, 200, 255]

    high_contrast = adjust_brightness_contrast(arr, brightness=0.0, contrast=0.5)
    # El valor oscuro debe ser más oscuro y el claro más claro
    assert high_contrast[0, 0, 0] < 50
    assert high_contrast[0, 1, 0] > 200


def test_saturation_grayscale():
    # Píxel rojo puro saturado
    arr = np.full((10, 10, 4), [255, 0, 0, 255], dtype=np.uint8)
    gray = adjust_saturation(arr, saturation=-1.0)
    # En escala de grises, R == G == B
    assert abs(int(gray[0, 0, 0]) - int(gray[0, 0, 1])) <= 1
    assert abs(int(gray[0, 0, 1]) - int(gray[0, 0, 2])) <= 1
    assert gray[0, 0, 3] == 255


def test_color_balance():
    arr = np.full((5, 5, 4), [100, 100, 100, 255], dtype=np.uint8)
    tinted = adjust_color_balance(arr, red_gain=1.5, green_gain=1.0, blue_gain=0.5)
    assert tinted[0, 0, 0] == 150
    assert tinted[0, 0, 1] == 100
    assert tinted[0, 0, 2] == 50
    assert tinted[0, 0, 3] == 255


def test_equalize_illumination():
    # Crear imagen con un gradiente de sombra pronunciado horizontal
    h, w = 60, 60
    gradient = np.tile(np.linspace(50, 220, w, dtype=np.uint8), (h, 1))
    arr = np.dstack([gradient, gradient, gradient, np.full((h, w), 255, dtype=np.uint8)])

    equalized = equalize_illumination(arr, strength=0.8)
    assert equalized.shape == arr.shape
    # La diferencia entre el extremo izquierdo y derecho debe ser menor tras aplanar la iluminación
    orig_diff = int(arr[30, -1, 0]) - int(arr[30, 0, 0])
    eq_diff = int(equalized[30, -1, 0]) - int(equalized[30, 0, 0])
    assert eq_diff < orig_diff

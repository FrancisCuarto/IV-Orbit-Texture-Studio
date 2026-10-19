"""Pruebas unitarias para el motor de generación de mapas PBR y normales."""

import numpy as np

from iv_orbit_texture_studio.imaging.pbr import (
    generate_ao_map,
    generate_height_map,
    generate_normal_map,
    generate_roughness_map,
    pack_orm_map,
    rgb_to_luminance,
)


def _make_flat_image(w: int = 32, h: int = 32, val: int = 128) -> np.ndarray:
    return np.full((h, w, 4), [val, val, val, 255], dtype=np.uint8)


def _make_ramp_image(w: int = 32, h: int = 32) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for x in range(w):
        val = int(round((x / (w - 1)) * 255.0))
        arr[:, x] = [val, val, val, 255]
    return arr


def test_rgb_to_luminance():
    black = np.zeros((4, 4, 4), dtype=np.uint8)
    black[:, :, 3] = 255
    lum_black = rgb_to_luminance(black)
    assert np.allclose(lum_black, 0.0)

    white = np.full((4, 4, 4), 255, dtype=np.uint8)
    lum_white = rgb_to_luminance(white)
    assert np.allclose(lum_white, 1.0)


def test_height_map_generation():
    img = _make_ramp_image(32, 32)
    h_map = generate_height_map(img, invert=False)

    assert h_map.shape == (32, 32, 4)
    assert h_map.dtype == np.uint8
    # Comprobar gradiente de izquierda a derecha
    assert h_map[16, 0, 0] < h_map[16, 31, 0]

    # Con invert=True, la izquierda debe ser mayor que la derecha
    h_inv = generate_height_map(img, invert=True)
    assert h_inv[16, 0, 0] > h_inv[16, 31, 0]


def test_normal_map_flat_surface():
    flat = _make_flat_image(32, 32, val=150)
    normal = generate_normal_map(flat, strength=2.0)

    assert normal.shape == (32, 32, 4)
    assert normal.dtype == np.uint8

    # Una superficie plana sin pendiente tiene normal hacia arriba (0, 0, 1),
    # que en espacio tangente RGB se codifica como (128, 128, 255).
    center_pixel = normal[16, 16]
    assert abs(int(center_pixel[0]) - 128) <= 2  # R ~ 128
    assert abs(int(center_pixel[1]) - 128) <= 2  # G ~ 128
    assert center_pixel[2] == 255  # B == 255
    assert center_pixel[3] == 255  # Alfa preservado


def test_normal_map_unit_length():
    img = _make_ramp_image(32, 32)
    normal = generate_normal_map(img, strength=4.0)

    # Convertir canales RGB a vectores [-1.0, 1.0]
    r = normal[:, :, 0].astype(np.float32) / 255.0 * 2.0 - 1.0
    g = normal[:, :, 1].astype(np.float32) / 255.0 * 2.0 - 1.0
    b = normal[:, :, 2].astype(np.float32) / 255.0 * 2.0 - 1.0

    lengths = np.sqrt(r * r + g * g + b * b)
    # Todos los vectores normales deben ser aproximadamente de longitud 1.0
    assert np.all(np.abs(lengths - 1.0) < 0.08)


def test_normal_map_opengl_vs_directx():
    img = _make_ramp_image(32, 32)
    # Rotar para tener pendiente en Y
    img_y = np.transpose(img, (1, 0, 2))

    norm_gl = generate_normal_map(img_y, strength=3.0, format_opengl=True)
    norm_dx = generate_normal_map(img_y, strength=3.0, format_opengl=False)

    # En OpenGL y DirectX, el canal verde (Y) está invertido
    # Mientras que el canal rojo (X) y azul (Z) son idénticos
    assert np.all(norm_gl[:, :, 0] == norm_dx[:, :, 0])
    assert np.all(norm_gl[:, :, 2] == norm_dx[:, :, 2])
    # Comparar canal verde: deben ser reflexiones respecto a 128
    g_gl = norm_gl[16, 16, 1]
    g_dx = norm_dx[16, 16, 1]
    assert abs((int(g_gl) - 128) + (int(g_dx) - 128)) <= 2


def test_roughness_map():
    img = _make_ramp_image(32, 32)
    rough = generate_roughness_map(img, base_roughness=0.6, invert=False)
    assert rough.shape == (32, 32, 4)
    assert rough.dtype == np.uint8

    gloss = generate_roughness_map(img, base_roughness=0.6, invert=True)
    # Al invertir, val_gloss ~ 255 - val_rough
    diff = np.abs((255 - rough[:, :, 0].astype(int)) - gloss[:, :, 0].astype(int))
    assert np.mean(diff) <= 2.0


def test_ao_map():
    flat = _make_flat_image(32, 32, val=200)
    ao_flat = generate_ao_map(flat)
    # En superficie plana no hay oclusión (AO es 255 = blanco)
    assert np.all(ao_flat[:, :, :3] == 255)

    # Crear una imagen con una hendidura oscura en el centro
    crevice_img = _make_flat_image(32, 32, val=200)
    crevice_img[14:18, :] = [50, 50, 50, 255]
    ao_crevice = generate_ao_map(crevice_img, strength=2.0, blur_radius=5)
    # En la hendidura el AO debe ser notablemente menor a 255
    assert np.mean(ao_crevice[15:17, 10:20, 0]) < 220


def test_pack_orm_and_rma():
    ao = _make_flat_image(16, 16, val=210)
    rough = _make_flat_image(16, 16, val=140)

    # ORM: R=AO, G=Roughness, B=Metallic
    orm = pack_orm_map(ao, rough, metallic_value=0.25, format_rma=False)
    assert orm.shape == (16, 16, 4)
    assert orm[0, 0, 0] == 210  # R: AO
    assert orm[0, 0, 1] == 140  # G: Roughness
    assert orm[0, 0, 2] == 64  # B: Metallic (0.25 * 255)
    assert orm[0, 0, 3] == 255

    # RMA: R=Roughness, G=Metallic, B=AO
    rma = pack_orm_map(ao, rough, metallic_value=0.50, format_rma=True)
    assert rma[0, 0, 0] == 140  # R: Roughness
    assert rma[0, 0, 1] == 128  # G: Metallic (0.50 * 255)
    assert rma[0, 0, 2] == 210  # B: AO

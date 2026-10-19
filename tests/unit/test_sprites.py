import numpy as np

from iv_orbit_texture_studio.core.region import Rect
from iv_orbit_texture_studio.imaging.sprites import (
    detect_sprites_by_transparency,
    extract_sprite_pixels,
    merge_overlapping_rects,
)


def _create_transparent_canvas(w: int = 100, h: int = 100) -> np.ndarray:
    return np.zeros((h, w, 4), dtype=np.uint8)


def test_detect_sprites_isolated():
    canvas = _create_transparent_canvas(100, 100)

    # Sprite 1: at (10, 10), size 20x20
    canvas[10:30, 10:30] = [255, 0, 0, 255]

    # Sprite 2: at (50, 10), size 30x15
    canvas[10:25, 50:80] = [0, 255, 0, 255]

    # Sprite 3: at (20, 60), size 40x25
    canvas[60:85, 20:60] = [0, 0, 255, 255]

    rects = detect_sprites_by_transparency(canvas, alpha_threshold=10, min_area=4)
    assert len(rects) == 3

    # Verify positions
    assert Rect(10, 10, 20, 20) in rects
    assert Rect(50, 10, 30, 15) in rects
    assert Rect(20, 60, 40, 25) in rects


def test_detect_sprites_alpha_threshold():
    canvas = _create_transparent_canvas(50, 50)
    # Faint ghost sprite (alpha = 5)
    canvas[10:20, 10:20] = [255, 255, 255, 5]
    # Solid sprite (alpha = 200)
    canvas[30:40, 30:40] = [255, 0, 0, 200]

    rects = detect_sprites_by_transparency(canvas, alpha_threshold=10)
    assert len(rects) == 1
    assert rects[0] == Rect(30, 30, 10, 10)


def test_detect_sprites_min_area_noise_filter():
    canvas = _create_transparent_canvas(50, 50)
    # 2 isolated noisy pixels
    canvas[5, 5] = [255, 255, 255, 255]
    canvas[15, 15] = [255, 255, 255, 255]
    # Real sprite 10x10 = 100 px
    canvas[20:30, 20:30] = [255, 255, 0, 255]

    rects = detect_sprites_by_transparency(canvas, min_area=10)
    assert len(rects) == 1
    assert rects[0] == Rect(20, 20, 10, 10)


def test_detect_sprites_padding():
    canvas = _create_transparent_canvas(50, 50)
    canvas[10:20, 10:20] = [255, 0, 0, 255]

    rects = detect_sprites_by_transparency(canvas, padding=2)
    assert len(rects) == 1
    assert rects[0] == Rect(8, 8, 14, 14)


def test_merge_overlapping_rects():
    r1 = Rect(10, 10, 20, 20)
    r2 = Rect(25, 20, 20, 20)  # overlaps with r1
    r3 = Rect(70, 70, 10, 10)  # isolated

    merged = merge_overlapping_rects([r1, r2, r3])
    assert len(merged) == 2
    assert Rect(70, 70, 10, 10) in merged
    # Combined r1 & r2 spans x: 10..45 (w=35), y: 10..40 (h=30)
    assert Rect(10, 10, 35, 30) in merged


def test_extract_sprite_pixels():
    canvas = _create_transparent_canvas(100, 100)
    canvas[10:30, 10:40] = [120, 150, 180, 255]

    rect = Rect(10, 10, 30, 20)
    crop = extract_sprite_pixels(canvas, rect)

    assert crop.shape == (20, 30, 4)
    assert np.all(crop[:, :, 0] == 120)
    assert np.all(crop[:, :, 1] == 150)
    assert np.all(crop[:, :, 2] == 180)
    assert np.all(crop[:, :, 3] == 255)
    assert not crop.flags.writeable

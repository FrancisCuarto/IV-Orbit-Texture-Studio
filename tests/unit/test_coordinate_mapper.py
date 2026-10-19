import math

import pytest

from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import (
    CoordinateMapper,
    Point,
    Size,
)


def test_point_and_size_validations():
    p = Point(10.5, -20.25)
    assert p.x == 10.5
    assert p.y == -20.25

    s = Size(100.0, 200.0)
    assert s.width == 100.0
    assert s.height == 200.0

    with pytest.raises(ValueError, match="Dimensiones inválidas"):
        Size(0, 100)

    with pytest.raises(ValueError, match="Dimensiones inválidas"):
        Size(100, -5)

    with pytest.raises(ValueError, match="Dimensiones inválidas"):
        Size(float("nan"), 100)


def test_coordinate_mapper_init():
    mapper = CoordinateMapper(min_zoom=0.1, max_zoom=10.0)
    assert mapper.zoom == 1.0
    assert mapper.offset == Point(0.0, 0.0)
    assert mapper.min_zoom == 0.1
    assert mapper.max_zoom == 10.0

    with pytest.raises(ValueError):
        CoordinateMapper(min_zoom=-1)
    with pytest.raises(ValueError):
        CoordinateMapper(min_zoom=5.0, max_zoom=2.0)


def test_roundtrip_conversions():
    mapper = CoordinateMapper()
    mapper.pan(150.0, 75.0)
    mapper.set_zoom(2.5, Point(0.0, 0.0))

    img_pt = Point(42.0, 88.0)
    screen_pt = mapper.image_to_screen(img_pt)
    roundtrip = mapper.screen_to_image(screen_pt)

    assert math.isclose(roundtrip.x, img_pt.x, rel_tol=1e-9)
    assert math.isclose(roundtrip.y, img_pt.y, rel_tol=1e-9)


def test_zoom_around_anchor():
    mapper = CoordinateMapper()
    anchor = Point(300.0, 200.0)

    # Before zoom, get image coordinate under anchor
    orig_img_pt = mapper.screen_to_image(anchor)

    # Zoom in centered at anchor
    mapper.zoom_by(2.0, anchor)
    assert mapper.zoom == 2.0

    # The point under the anchor on screen must remain the same point in image space
    new_img_pt = mapper.screen_to_image(anchor)
    assert math.isclose(orig_img_pt.x, new_img_pt.x, abs_tol=1e-9)
    assert math.isclose(orig_img_pt.y, new_img_pt.y, abs_tol=1e-9)


def test_zoom_clamping():
    mapper = CoordinateMapper(min_zoom=0.5, max_zoom=4.0)
    anchor = Point(0.0, 0.0)

    mapper.set_zoom(10.0, anchor)
    assert mapper.zoom == 4.0

    mapper.set_zoom(0.01, anchor)
    assert mapper.zoom == 0.5


def test_pan():
    mapper = CoordinateMapper()
    mapper.pan(50.0, -30.0)
    assert mapper.offset == Point(50.0, -30.0)

    # Image (0, 0) should be at screen (50, -30)
    assert mapper.image_to_screen(Point(0.0, 0.0)) == Point(50.0, -30.0)


def test_center():
    mapper = CoordinateMapper()
    image_size = Size(200.0, 100.0)
    viewport = Size(800.0, 600.0)

    # At zoom 1.0: centered offset should be ((800 - 200)/2, (600 - 100)/2) = (300, 250)
    mapper.center(image_size, viewport)
    assert mapper.offset == Point(300.0, 250.0)


def test_fit():
    mapper = CoordinateMapper()
    image_size = Size(1000.0, 500.0)  # aspect ratio 2:1
    viewport = Size(500.0, 500.0)

    # Fit without margin: zoom should be min(500/1000, 500/500) = 0.5
    mapper.fit(image_size, viewport, margin=0.0)
    assert mapper.zoom == 0.5
    # Scaled size: 500 x 250. Offset x should be 0, y should be (500 - 250)/2 = 125
    assert mapper.offset.x == 0.0
    assert mapper.offset.y == 125.0


def test_screen_to_pixel():
    mapper = CoordinateMapper()
    image_size = Size(100.0, 100.0)

    # Offset = (0,0), Zoom = 1.0
    assert mapper.screen_to_pixel(Point(0.5, 0.5), image_size) == (0, 0)
    assert mapper.screen_to_pixel(Point(99.9, 99.9), image_size) == (99, 99)

    # Outside boundaries
    assert mapper.screen_to_pixel(Point(-0.1, 50.0), image_size) is None
    assert mapper.screen_to_pixel(Point(100.0, 50.0), image_size) is None
    assert mapper.screen_to_pixel(Point(50.0, 100.1), image_size) is None


def test_image_rect_on_screen():
    mapper = CoordinateMapper()
    mapper.set_zoom(2.0, Point(0.0, 0.0))
    mapper.pan(10.0, 20.0)

    tl, br = mapper.image_rect_on_screen(Size(50.0, 30.0))
    assert tl.x == 10.0
    assert tl.y == 20.0
    assert br.x == 10.0 + 50.0 * 2.0
    assert br.y == 20.0 + 30.0 * 2.0

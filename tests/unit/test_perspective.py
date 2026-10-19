import numpy as np
import pytest

from iv_orbit_texture_studio.imaging.perspective import (
    DegenerateQuadError,
    InterpolationMode,
    Quad,
    estimate_rectified_dimensions,
    order_points_clockwise,
    rectify_perspective,
)
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import Point


def test_quad_properties():
    q = Quad(Point(0, 0), Point(100, 0), Point(100, 50), Point(0, 50))
    assert q.top_left == Point(0, 0)
    assert q.top_right == Point(100, 0)
    assert q.bottom_right == Point(100, 50)
    assert q.bottom_left == Point(0, 50)
    assert q.area() == 5000.0
    assert q.is_convex()

    # with_vertex
    q2 = q.with_vertex(1, Point(120, 10))
    assert q2.top_right == Point(120, 10)
    assert q2.top_left == Point(0, 0)


def test_quad_validation_convex():
    # Valid convex rectangle
    q = Quad(Point(10, 10), Point(90, 15), Point(85, 95), Point(15, 80))
    q.validate()  # Does not raise


def test_quad_validation_concave():
    # Concave quadrilateral (arrow shape, p2 goes inward)
    q = Quad(Point(0, 0), Point(100, 0), Point(50, 40), Point(0, 100))
    assert not q.is_convex()
    with pytest.raises(DegenerateQuadError):
        q.validate()


def test_quad_validation_self_intersecting():
    # Bowtie / crossed lines
    q = Quad(Point(0, 0), Point(100, 100), Point(100, 0), Point(0, 100))
    assert not q.is_convex()
    with pytest.raises(DegenerateQuadError):
        q.validate()


def test_quad_validation_colinear():
    # 3 points on the same line
    q = Quad(Point(0, 0), Point(50, 0), Point(100, 0), Point(0, 50))
    assert not q.is_convex()
    with pytest.raises(DegenerateQuadError):
        q.validate()


def test_quad_validation_duplicates():
    q = Quad(Point(10, 10), Point(10, 10), Point(50, 50), Point(0, 50))
    assert not q.is_convex()
    with pytest.raises(DegenerateQuadError):
        q.validate()


def test_quad_validation_tiny_area():
    q = Quad(Point(0, 0), Point(0.5, 0), Point(0.5, 0.5), Point(0, 0.5))
    assert q.is_convex()
    assert q.area() == 0.25
    with pytest.raises(DegenerateQuadError, match="área.*demasiado pequeña"):
        q.validate()


def test_order_points_clockwise():
    # Points in random order
    pts = [Point(100, 100), Point(0, 0), Point(0, 100), Point(100, 0)]
    quad = order_points_clockwise(pts)
    assert quad.top_left == Point(0, 0)
    assert quad.top_right == Point(100, 0)
    assert quad.bottom_right == Point(100, 100)
    assert quad.bottom_left == Point(0, 100)


def test_estimate_rectified_dimensions():
    # Rectangle 100 x 80
    rect = Quad(Point(0, 0), Point(100, 0), Point(100, 80), Point(0, 80))
    w, h = estimate_rectified_dimensions(rect)
    assert w == 100
    assert h == 80

    # Trapezoid: top width 60, bottom width 100, slanted legs of length sqrt(20^2 + 80^2) ~= 82.46
    trap = Quad(Point(20, 0), Point(80, 0), Point(100, 80), Point(0, 80))
    w, h = estimate_rectified_dimensions(trap)
    assert w == 100
    assert h == 82


def test_rectify_perspective_synthetic():
    # Create synthetic image: 100x100
    # Top-Left quadrant: Red (255, 0, 0, 255)
    # Top-Right quadrant: Green (0, 255, 0, 255)
    # Bottom-Right quadrant: Blue (0, 0, 255, 255)
    # Bottom-Left quadrant: Yellow (255, 255, 0, 255)
    img = np.zeros((100, 100, 4), dtype=np.uint8)
    img[0:50, 0:50] = [255, 0, 0, 255]
    img[0:50, 50:100] = [0, 255, 0, 255]
    img[50:100, 50:100] = [0, 0, 255, 255]
    img[50:100, 0:50] = [255, 255, 0, 255]

    # Select exact boundaries of the image
    quad = Quad(Point(0, 0), Point(99, 0), Point(99, 99), Point(0, 99))

    rectified = rectify_perspective(
        img,
        quad,
        output_width=50,
        output_height=50,
        interpolation=InterpolationMode.NEAREST,
    )

    assert rectified.shape == (50, 50, 4)
    assert rectified.dtype == np.uint8

    # Top-left pixel should be Red
    np.testing.assert_array_equal(rectified[5, 5], [255, 0, 0, 255])
    # Top-right pixel should be Green
    np.testing.assert_array_equal(rectified[5, 45], [0, 255, 0, 255])
    # Bottom-right pixel should be Blue
    np.testing.assert_array_equal(rectified[45, 45], [0, 0, 255, 255])
    # Bottom-left pixel should be Yellow
    np.testing.assert_array_equal(rectified[45, 5], [255, 255, 0, 255])


def test_rectify_perspective_interpolations():
    img = np.zeros((64, 64, 4), dtype=np.uint8)
    img[:, :] = [100, 150, 200, 255]
    quad = Quad(Point(10, 10), Point(50, 12), Point(52, 50), Point(12, 48))

    for mode in InterpolationMode:
        out = rectify_perspective(img, quad, 32, 32, interpolation=mode)
        assert out.shape == (32, 32, 4)
        assert out.dtype == np.uint8


def test_rectify_invalid_params():
    img = np.zeros((32, 32, 4), dtype=np.uint8)
    q = Quad(Point(0, 0), Point(30, 0), Point(30, 30), Point(0, 30))

    with pytest.raises(ValueError):
        rectify_perspective(img, q, output_width=0, output_height=30)

    with pytest.raises(ValueError):
        rectify_perspective(img, q, output_width=30, output_height=-10)

import pytest

from iv_orbit_texture_studio.imaging.perspective import Quad
from iv_orbit_texture_studio.tools.texture_ripper.selection import (
    SelectionModel,
    SelectionState,
)
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import (
    CoordinateMapper,
    Point,
    Size,
)


def test_selection_lifecycle():
    sel = SelectionModel()
    assert sel.state == SelectionState.EMPTY
    assert sel.count == 0
    assert not sel.is_valid()
    assert sel.validate() is not None

    sel.add_point(Point(10, 10))
    assert sel.state == SelectionState.COLLECTING
    assert sel.count == 1

    sel.add_point(Point(100, 10))
    sel.add_point(Point(100, 100))
    assert sel.state == SelectionState.COLLECTING
    assert sel.count == 3

    sel.add_point(Point(10, 100))
    assert sel.state == SelectionState.COMPLETE
    assert sel.count == 4
    assert sel.is_valid()
    assert sel.validate() is None

    quad = sel.get_quad()
    assert isinstance(quad, Quad)
    assert sel.estimated_dimensions() == (90, 90)


def test_selection_default_rect():
    sel = SelectionModel()
    sel.init_default_rect(Size(1000.0, 500.0), margin_ratio=0.1)
    assert sel.state == SelectionState.COMPLETE
    assert sel.is_valid()

    quad = sel.get_quad()
    assert quad.top_left == Point(100.0, 50.0)
    assert quad.top_right == Point(900.0, 50.0)
    assert quad.bottom_right == Point(900.0, 450.0)
    assert quad.bottom_left == Point(100.0, 450.0)


def test_selection_move_vertex():
    sel = SelectionModel()
    sel.init_default_rect(Size(200, 200))
    sel.move_vertex(0, Point(20, 25))
    assert sel.points[0] == Point(20, 25)

    with pytest.raises(IndexError):
        sel.move_vertex(5, Point(0, 0))


def test_hit_test_vertex():
    mapper = CoordinateMapper()
    mapper.set_zoom(2.0, Point(0.0, 0.0))
    mapper.pan(100.0, 50.0)

    sel = SelectionModel(
        [Point(10.0, 20.0), Point(50.0, 20.0), Point(50.0, 60.0), Point(10.0, 60.0)]
    )

    # In screen coordinates:
    # Point 0: (10*2 + 100, 20*2 + 50) = (120, 90)
    hit = sel.hit_test_vertex(Point(122.0, 89.0), mapper, radius_screen_px=10.0)
    assert hit == 0

    # Miss
    hit_miss = sel.hit_test_vertex(Point(200.0, 200.0), mapper, radius_screen_px=10.0)
    assert hit_miss is None

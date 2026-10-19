import pytest

from iv_orbit_texture_studio.core.region import Pivot, PivotMode, Rect, SpriteRegion


def test_rect_properties():
    r = Rect(10, 20, 30, 40)
    assert r.left == 10
    assert r.right == 40
    assert r.top == 20
    assert r.bottom == 60
    assert r.center_x == 25.0
    assert r.center_y == 40.0
    assert r.area == 1200


def test_rect_invalid_dimensions():
    with pytest.raises(ValueError, match="ancho"):
        Rect(0, 0, 0, 10)
    with pytest.raises(ValueError, match="alto"):
        Rect(0, 0, 10, -5)


def test_rect_intersection():
    r1 = Rect(0, 0, 50, 50)
    r2 = Rect(25, 25, 50, 50)
    r3 = Rect(60, 60, 10, 10)
    r4 = Rect(50, 0, 50, 50)  # adjacent edge, not intersecting

    assert r1.intersects(r2)
    assert r2.intersects(r1)
    assert not r1.intersects(r3)
    assert not r1.intersects(r4)


def test_rect_clamped():
    r = Rect(-10, -5, 100, 100)
    clamped = r.clamped(50, 50)
    assert clamped.x == 0
    assert clamped.y == 0
    assert clamped.width == 50
    assert clamped.height == 50


def test_pivot_presets():
    p_center = Pivot.from_mode(PivotMode.CENTER)
    assert p_center.x == 0.5
    assert p_center.y == 0.5
    assert p_center.pixel_coords(100, 200) == (50.0, 100.0)

    p_bottom_center = Pivot.from_mode(PivotMode.BOTTOM_CENTER)
    assert p_bottom_center.x == 0.5
    assert p_bottom_center.y == 1.0
    assert p_bottom_center.pixel_coords(100, 200) == (50.0, 200.0)

    p_custom = Pivot.from_mode(PivotMode.CUSTOM, custom_x=0.25, custom_y=0.75)
    assert p_custom.x == 0.25
    assert p_custom.y == 0.75


def test_sprite_region_serialization():
    rect = Rect(15, 30, 48, 64)
    pivot = Pivot.from_mode(PivotMode.BOTTOM_CENTER)
    sprite = SpriteRegion.create("hero_idle", rect, pivot)

    data = sprite.to_dict()
    assert data["name"] == "hero_idle"
    assert data["rect"] == {"x": 15, "y": 30, "width": 48, "height": 64}
    assert data["pivot"]["mode"] == "bottom_center"

    restored = SpriteRegion.from_dict(data)
    assert restored.id == sprite.id
    assert restored.name == sprite.name
    assert restored.rect == rect
    assert restored.pivot == pivot

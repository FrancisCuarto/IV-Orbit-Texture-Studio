import numpy as np
import pytest

from iv_orbit_texture_studio.core.region import Pivot, PivotMode, Rect, SpriteRegion
from iv_orbit_texture_studio.imaging.atlas import (
    AtlasFitError,
    next_power_of_two,
    pack_sprites_to_atlas,
)


def _make_dummy_sprite(
    name: str, w: int, h: int, color: tuple[int, int, int, int]
) -> tuple[SpriteRegion, np.ndarray]:
    region = SpriteRegion.create(
        name=name,
        rect=Rect(0, 0, w, h),
        pivot=Pivot.from_mode(PivotMode.BOTTOM_CENTER),
    )
    pixels = np.zeros((h, w, 4), dtype=np.uint8)
    pixels[:, :] = color
    return region, pixels


def test_next_power_of_two():
    assert next_power_of_two(1) == 1
    assert next_power_of_two(2) == 2
    assert next_power_of_two(3) == 4
    assert next_power_of_two(33) == 64
    assert next_power_of_two(512) == 512
    assert next_power_of_two(513) == 1024


def test_pack_sprites_no_overlap():
    s1 = _make_dummy_sprite("s1", 32, 32, (255, 0, 0, 255))
    s2 = _make_dummy_sprite("s2", 64, 48, (0, 255, 0, 255))
    s3 = _make_dummy_sprite("s3", 16, 64, (0, 0, 255, 255))
    s4 = _make_dummy_sprite("s4", 48, 16, (255, 255, 0, 255))

    result = pack_sprites_to_atlas(
        [s1, s2, s3, s4],
        padding=4,
        spacing=4,
        power_of_two=True,
    )

    assert result.width >= 64
    assert result.height >= 64
    # Power of two check
    assert (result.width & (result.width - 1)) == 0
    assert (result.height & (result.height - 1)) == 0

    assert len(result.sprites) == 4

    # Rigorous check: no two sprites overlap in atlas!
    for i in range(len(result.sprites)):
        for j in range(i + 1, len(result.sprites)):
            r1 = result.sprites[i].atlas_rect
            r2 = result.sprites[j].atlas_rect
            assert not r1.intersects(r2), (
                f"Solapamiento detectado entre {result.sprites[i].name} y {result.sprites[j].name}"
            )

    # Check pixels were pasted accurately
    for ps in result.sprites:
        crop = result.image[
            ps.atlas_rect.y : ps.atlas_rect.bottom, ps.atlas_rect.x : ps.atlas_rect.right
        ]
        assert crop.shape == (ps.atlas_rect.height, ps.atlas_rect.width, 4)
        # All alpha pixels must be 255
        assert np.all(crop[:, :, 3] == 255)


def test_pack_sprites_metadata():
    s1 = _make_dummy_sprite("hero", 30, 40, (200, 100, 50, 255))
    result = pack_sprites_to_atlas([s1], atlas_image_name="test_atlas.png")

    meta = result.metadata
    assert meta["meta"]["image"] == "test_atlas.png"
    assert "hero" in meta["frames"]
    frame_data = meta["frames"]["hero"]
    assert frame_data["frame"]["w"] == 30
    assert frame_data["frame"]["h"] == 40
    assert frame_data["pivot"]["x"] == 0.5
    assert frame_data["pivot"]["y"] == 1.0


def test_pack_sprites_overflow_raises_error():
    # Giant sprite exceeding max limits
    s_giant = _make_dummy_sprite("giant", 500, 500, (255, 0, 0, 255))
    with pytest.raises(AtlasFitError, match="no cabe en el atlas"):
        pack_sprites_to_atlas([s_giant], max_width=128, max_height=128)


def test_composite_atlas_items_manual():
    from iv_orbit_texture_studio.core.atlas_item import AtlasItem
    from iv_orbit_texture_studio.imaging.atlas import composite_atlas_items

    p1 = np.zeros((30, 30, 4), dtype=np.uint8)
    p1[:, :] = (255, 0, 0, 255)  # Red
    item1 = AtlasItem.create("item1", p1, x=10, y=10)

    p2 = np.zeros((20, 20, 4), dtype=np.uint8)
    p2[:, :] = (0, 255, 0, 255)  # Green
    item2 = AtlasItem.create("item2", p2, x=50, y=50)

    result = composite_atlas_items([item1, item2], width=128, height=128)

    assert result.width == 128
    assert result.height == 128
    assert len(result.sprites) == 2

    # Check red pixel at (15, 15)
    assert np.array_equal(result.image[15, 15], [255, 0, 0, 255])
    # Check green pixel at (55, 55)
    assert np.array_equal(result.image[55, 55], [0, 255, 0, 255])
    # Check background (0, 0) is transparent
    assert result.image[0, 0, 3] == 0


def test_auto_pack_atlas_items():
    from iv_orbit_texture_studio.core.atlas_item import AtlasItem
    from iv_orbit_texture_studio.imaging.atlas import auto_pack_atlas_items

    p1 = np.zeros((32, 32, 4), dtype=np.uint8)
    p1[:, :] = (255, 0, 0, 255)
    item1 = AtlasItem.create("wall", p1, x=0, y=0)

    p2 = np.zeros((32, 32, 4), dtype=np.uint8)
    p2[:, :] = (0, 0, 255, 255)
    item2 = AtlasItem.create("floor", p2, x=0, y=0)

    # Initial positions overlap at (0, 0)
    assert item1.x == 0 and item2.x == 0

    result = auto_pack_atlas_items([item1, item2], padding=2, spacing=2)

    # After auto-pack, item positions are updated and do NOT overlap
    assert not item1.rect.intersects(item2.rect)
    assert result.width >= 32
    assert result.height >= 32

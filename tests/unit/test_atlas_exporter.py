import json
from pathlib import Path

import numpy as np
import pytest

from iv_orbit_texture_studio.core.region import Rect, SpriteRegion
from iv_orbit_texture_studio.exporters.atlas_exporter import export_atlas_and_metadata
from iv_orbit_texture_studio.imaging.atlas import pack_sprites_to_atlas


def test_export_atlas_and_metadata(tmp_path: Path):
    reg = SpriteRegion.create("icon", Rect(0, 0, 16, 16))
    pixels = np.zeros((16, 16, 4), dtype=np.uint8)
    pixels[:, :] = [255, 128, 0, 255]

    result = pack_sprites_to_atlas([(reg, pixels)])

    target_img = tmp_path / "custom_atlas.png"
    target_json = tmp_path / "custom_atlas.json"

    out_img, out_json = export_atlas_and_metadata(result, target_img, target_json)

    assert out_img == target_img
    assert out_json == target_json
    assert out_img.is_file()
    assert out_json.is_file()

    # Verify JSON content
    meta = json.loads(out_json.read_text(encoding="utf-8"))
    assert meta["meta"]["image"] == "custom_atlas.png"
    assert "icon" in meta["frames"]


def test_export_atlas_default_json_name(tmp_path: Path):
    reg = SpriteRegion.create("sprite1", Rect(0, 0, 10, 10))
    pixels = np.zeros((10, 10, 4), dtype=np.uint8)
    result = pack_sprites_to_atlas([(reg, pixels)])

    target_img = tmp_path / "default_name.png"
    out_img, out_json = export_atlas_and_metadata(result, target_img)

    assert out_json == tmp_path / "default_name.json"
    assert out_json.is_file()


def test_export_atlas_no_overwrite(tmp_path: Path):
    reg = SpriteRegion.create("s", Rect(0, 0, 10, 10))
    pixels = np.zeros((10, 10, 4), dtype=np.uint8)
    result = pack_sprites_to_atlas([(reg, pixels)])

    target_img = tmp_path / "exists.png"
    target_img.write_bytes(b"dummy")

    with pytest.raises(FileExistsError):
        export_atlas_and_metadata(result, target_img, overwrite=False)

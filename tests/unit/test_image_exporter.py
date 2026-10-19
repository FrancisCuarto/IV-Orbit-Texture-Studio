import numpy as np
import pytest
from PIL import Image

from iv_orbit_texture_studio.exporters.image_exporter import (
    ExportError,
    ExportOptions,
    export_dialog_filter,
    export_image,
)


def test_export_png(tmp_path):
    pixels = np.zeros((32, 48, 4), dtype=np.uint8)
    pixels[:, :] = [255, 128, 64, 200]

    out_path = tmp_path / "result.png"
    saved = export_image(pixels, out_path)
    assert saved == out_path
    assert out_path.is_file()

    # Re-open and verify
    with Image.open(out_path) as im:
        assert im.size == (48, 32)
        assert im.mode == "RGBA"
        px = im.getpixel((0, 0))
        assert px == (255, 128, 64, 200)


def test_export_jpeg(tmp_path):
    pixels = np.zeros((20, 20, 4), dtype=np.uint8)
    pixels[:, :] = [200, 50, 50, 255]

    out_path = tmp_path / "result.jpg"
    options = ExportOptions(jpeg_quality=90)
    saved = export_image(pixels, out_path, options=options)
    assert saved == out_path
    assert out_path.is_file()

    with Image.open(out_path) as im:
        assert im.size == (20, 20)
        assert im.mode == "RGB"


def test_export_unsupported_ext(tmp_path):
    pixels = np.zeros((10, 10, 4), dtype=np.uint8)
    out_path = tmp_path / "result.xyz"
    with pytest.raises(ExportError, match="Extensión no admitida"):
        export_image(pixels, out_path)


def test_export_no_overwrite(tmp_path):
    pixels = np.zeros((10, 10, 4), dtype=np.uint8)
    out_path = tmp_path / "exists.png"
    out_path.write_bytes(b"dummy")

    with pytest.raises(ExportError, match="ya existe"):
        export_image(pixels, out_path, overwrite=False)


def test_export_dialog_filter():
    f = export_dialog_filter()
    assert "*.png" in f
    assert "*.jpg" in f
    assert "*.webp" in f

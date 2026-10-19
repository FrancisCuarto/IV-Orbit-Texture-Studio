import numpy as np
import pytest
from PIL import Image

from iv_orbit_texture_studio.imaging.image_io import (
    ImageNotFoundError,
    ImageTooLargeError,
    UnsupportedImageError,
    load_image,
    open_dialog_filter,
    validate_dimensions,
)


def test_validate_dimensions():
    assert validate_dimensions(100, 100) is None
    assert validate_dimensions(0, 100) is not None
    assert validate_dimensions(100, -1) is not None
    assert validate_dimensions(40000, 100, max_dimension=32768) is not None
    assert validate_dimensions(2000, 2000, max_pixels=1000) is not None


def test_load_valid_image(tmp_path):
    # Create test image with RGB and alpha
    img_path = tmp_path / "test_img.png"
    pil_img = Image.new("RGBA", (64, 32), color=(255, 0, 128, 200))
    pil_img.save(img_path)

    loaded = load_image(img_path)
    assert loaded.path == img_path
    assert loaded.width == 64
    assert loaded.height == 32
    assert loaded.pixels.shape == (32, 64, 4)
    assert loaded.pixels.dtype == np.uint8
    # Ensure pixels are read-only
    assert not loaded.pixels.flags.writeable
    with pytest.raises(ValueError):
        loaded.pixels[0, 0, 0] = 0

    # Check color values
    np.testing.assert_array_equal(loaded.pixels[0, 0], [255, 0, 128, 200])


def test_load_non_existent_image(tmp_path):
    missing_path = tmp_path / "does_not_exist.png"
    with pytest.raises(ImageNotFoundError):
        load_image(missing_path)


def test_load_corrupt_image(tmp_path):
    corrupt_path = tmp_path / "bad.png"
    corrupt_path.write_bytes(b"not an image file content")
    with pytest.raises(UnsupportedImageError):
        load_image(corrupt_path)


def test_load_image_exceeds_limits(tmp_path):
    img_path = tmp_path / "oversized.png"
    pil_img = Image.new("RGB", (100, 100))
    pil_img.save(img_path)

    with pytest.raises(ImageTooLargeError):
        load_image(img_path, max_dimension=50)


def test_open_dialog_filter():
    f = open_dialog_filter()
    assert "*.png" in f
    assert "*.jpg" in f
    assert "*.webp" in f

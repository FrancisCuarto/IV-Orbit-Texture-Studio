import numpy as np
import pytest
from PySide6.QtGui import QImage

from iv_orbit_texture_studio.ui.qt_image import rgba_array_to_qimage


def test_rgba_array_to_qimage(qapp):
    arr = np.zeros((30, 40, 4), dtype=np.uint8)
    arr[:, :, 0] = 255  # Red
    arr[:, :, 3] = 255  # Alpha

    qimg = rgba_array_to_qimage(arr)
    assert not qimg.isNull()
    assert qimg.width() == 40
    assert qimg.height() == 30
    assert qimg.format() == QImage.Format.Format_RGBA8888


def test_rgba_array_to_qimage_invalid():
    # Wrong dimensions or dtype
    with pytest.raises(ValueError):
        rgba_array_to_qimage(np.zeros((10, 10, 3), dtype=np.uint8))

    with pytest.raises(ValueError):
        rgba_array_to_qimage(np.zeros((10, 10, 4), dtype=np.float32))

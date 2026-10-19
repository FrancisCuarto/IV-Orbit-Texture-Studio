"""Puente entre arreglos NumPy del motor de imágenes y tipos de imagen de Qt."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PySide6.QtGui import QImage


def rgba_array_to_qimage(pixels: NDArray[np.uint8]) -> QImage:
    """Convierte un arreglo ``(alto, ancho, 4)`` RGBA ``uint8`` en una ``QImage``.

    La ``QImage`` devuelta posee su propia copia de los datos, de modo que no
    depende del ciclo de vida del arreglo de origen (que es de solo lectura).
    """
    if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] != 4:
        raise ValueError(
            f"Se esperaba un arreglo RGBA uint8 (alto, ancho, 4); se recibió "
            f"{pixels.dtype} {pixels.shape}"
        )
    height, width = int(pixels.shape[0]), int(pixels.shape[1])
    contiguous = np.ascontiguousarray(pixels)
    view = QImage(
        contiguous.tobytes(),
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    )
    # ``copy()`` desacopla la imagen del búfer temporal de bytes.
    return view.copy()


def qimage_to_rgba_array(image: QImage) -> NDArray[np.uint8]:
    """Convierte una ``QImage`` en un arreglo NumPy RGBA uint8 ``(alto, ancho, 4)``."""
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise ValueError("No se puede convertir una QImage nula o de dimensiones inválidas.")
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = converted.width()
    height = converted.height()
    ptr = converted.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))
    return np.array(arr, copy=True)

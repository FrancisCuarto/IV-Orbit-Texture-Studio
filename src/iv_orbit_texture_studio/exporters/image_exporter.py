"""Exportación de imágenes rectificadas y procesadas a disco.

Independiente de Qt. Usa Pillow para guardar en formatos estándar con
escritura atómica segura.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
from PIL import Image

from iv_orbit_texture_studio.imaging.image_io import RgbaArray


class ExportError(Exception):
    """Error al exportar una imagen."""


@dataclass(frozen=True, slots=True)
class ExportOptions:
    """Parámetros de configuración para exportar una imagen."""

    jpeg_quality: int = 95
    webp_quality: int = 95
    png_compression: int = 6  # 0 a 9
    background_color: tuple[int, int, int] = (255, 255, 255)  # Para formatos sin canal alfa


SUPPORTED_EXPORT_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tga",
)


def export_dialog_filter() -> str:
    """Filtros para diálogos de guardado."""
    return (
        "PNG (*.png);;"
        "JPEG (*.jpg *.jpeg);;"
        "WebP (*.webp);;"
        "BMP (*.bmp);;"
        "Targa (*.tga);;"
        "Todos los archivos (*)"
    )


def export_image(
    pixels: RgbaArray,
    target_path: str | Path,
    options: ExportOptions | None = None,
    overwrite: bool = True,
) -> Path:
    """Guarda un arreglo RGBA uint8 en el archivo especificado usando escritura atómica.

    Parámetros:
        pixels: Arreglo (H, W, 4) uint8 en orden RGBA.
        target_path: Ruta destino donde guardar la imagen.
        options: Opciones de compresión y calidad.
        overwrite: Si es False y el archivo existe, lanza ExportError.

    Retorna:
        Ruta resuelta del archivo guardado.
    """
    if options is None:
        options = ExportOptions()

    if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] != 4:
        raise ValueError(f"Arreglo de píxeles inválido para exportar: {pixels.shape}")

    path = Path(target_path).resolve()
    if not overwrite and path.exists():
        raise ExportError(f"El archivo de destino ya existe y overwrite=False: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXPORT_EXTENSIONS:
        allowed = ", ".join(SUPPORTED_EXPORT_EXTENSIONS)
        raise ExportError(f"Extensión no admitida: {ext}. Formatos permitidos: {allowed}")

    # Crear directorio si no existe
    path.parent.mkdir(parents=True, exist_ok=True)

    pil_img = Image.fromarray(pixels, mode="RGBA")

    # Si el formato no admite alfa (JPEG o BMP en algunos visores), mezclar con color de fondo
    save_kwargs: dict[str, Any] = {}
    if ext in (".jpg", ".jpeg"):
        bg = Image.new("RGB", pil_img.size, options.background_color)
        bg.paste(pil_img, mask=pil_img.split()[3])
        output_img: Image.Image = bg
        save_kwargs["quality"] = options.jpeg_quality
        save_kwargs["optimize"] = True
    elif ext == ".webp":
        output_img = pil_img
        save_kwargs["quality"] = options.webp_quality
    elif ext == ".png":
        output_img = pil_img
        save_kwargs["compress_level"] = options.png_compression
    elif ext == ".bmp":
        # BMP estándar suele ser RGB
        output_img = pil_img.convert("RGB")
    else:
        output_img = pil_img

    # Escritura atómica: en Windows el archivo debe cerrarse antes de que Pillow pueda escribirlo
    tmp_file = NamedTemporaryFile(  # noqa: SIM115
        dir=path.parent,
        prefix=f".{path.stem}_tmp_",
        suffix=ext,
        delete=False,
    )
    tmp_path = Path(tmp_file.name)
    try:
        tmp_file.close()
        output_img.save(tmp_path, **save_kwargs)
        # Reemplazo atómico (en Windows os.replace es atómico desde Python 3.3)
        os.replace(tmp_path, path)
    except Exception as exc:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise ExportError(f"Error al escribir la imagen en disco: {exc}") from exc

    return path

"""Lectura y validación de imágenes, independiente de la interfaz.

Toda imagen cargada se normaliza a un arreglo NumPy ``uint8`` de forma
``(alto, ancho, 4)`` en orden RGBA. El arreglo se marca como de solo lectura
para proteger los datos de origen: las transformaciones futuras deben producir
arreglos nuevos.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError

#: Extensiones ofrecidas en el diálogo de apertura. Pillow puede abrir otras,
#: pero estas son las verificadas para el flujo actual.
SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tga",
    ".tif",
    ".tiff",
    ".webp",
    ".gif",
)

#: Límites provisionales para evitar asignaciones de memoria excesivas.
#: 16384 x 16384 RGBA ≈ 1 GiB. Revisar tras medir consumo real.
DEFAULT_MAX_DIMENSION = 32768
DEFAULT_MAX_PIXELS = 16384 * 16384

RgbaArray = NDArray[np.uint8]


class ImageLoadError(Exception):
    """Error comprensible al intentar abrir una imagen."""

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.path = path


class ImageNotFoundError(ImageLoadError):
    pass


class UnsupportedImageError(ImageLoadError):
    pass


class ImageTooLargeError(ImageLoadError):
    pass


@dataclass(frozen=True, slots=True)
class LoadedImage:
    """Imagen decodificada y normalizada a RGBA de 8 bits."""

    path: Path
    pixels: RgbaArray
    source_format: str | None
    source_mode: str

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])


def validate_dimensions(
    width: int,
    height: int,
    *,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> str | None:
    """Devuelve un mensaje de error si las dimensiones no son admisibles."""
    if width <= 0 or height <= 0:
        return f"Dimensiones inválidas: {width} x {height}"
    if width > max_dimension or height > max_dimension:
        return f"La imagen mide {width} x {height} px; el máximo por lado es {max_dimension} px."
    if width * height > max_pixels:
        return f"La imagen tiene {width * height:,} píxeles; el máximo admitido es {max_pixels:,}."
    return None


def load_image(
    path: str | Path,
    *,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> LoadedImage:
    """Abre ``path`` y devuelve la imagen como RGBA de solo lectura.

    Las dimensiones se validan leyendo solo la cabecera, antes de decodificar.
    Se aplica la orientación EXIF para que la imagen coincida con lo que
    muestran los visores habituales. Para formatos animados se usa el primer
    fotograma.

    Raises:
        ImageNotFoundError: el archivo no existe o no es un archivo regular.
        ImageTooLargeError: las dimensiones superan los límites.
        UnsupportedImageError: el formato no se reconoce o los datos están dañados.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ImageNotFoundError(f"No se encontró el archivo: {file_path}", file_path)

    try:
        with warnings.catch_warnings():
            # Validamos los límites nosotros mismos; evitamos la advertencia
            # genérica de Pillow para que el mensaje sea coherente.
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(file_path) as image:
                error = validate_dimensions(
                    image.width,
                    image.height,
                    max_dimension=max_dimension,
                    max_pixels=max_pixels,
                )
                if error is not None:
                    raise ImageTooLargeError(error, file_path)
                source_format = image.format
                source_mode = image.mode
                image.load()
                oriented = ImageOps.exif_transpose(image)
                rgba = oriented.convert("RGBA")
    except ImageLoadError:
        raise
    except Image.DecompressionBombError as exc:
        raise ImageTooLargeError(str(exc), file_path) from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        # Pillow usa OSError/SyntaxError/ValueError para datos dañados o truncados.
        raise UnsupportedImageError(
            f"No se pudo leer la imagen (formato no compatible o archivo dañado): {exc}",
            file_path,
        ) from exc

    pixels = np.asarray(rgba, dtype=np.uint8)
    if pixels.ndim != 3 or pixels.shape[2] != 4:  # salvaguarda defensiva
        raise UnsupportedImageError("Forma de imagen inesperada tras la conversión.", file_path)
    pixels = np.ascontiguousarray(pixels)
    pixels.setflags(write=False)
    return LoadedImage(
        path=file_path,
        pixels=pixels,
        source_format=source_format,
        source_mode=source_mode,
    )


def open_dialog_filter() -> str:
    """Filtro de extensiones para diálogos de archivo (sin dependencia de Qt)."""
    patterns = " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
    return patterns

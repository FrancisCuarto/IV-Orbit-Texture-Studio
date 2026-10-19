"""Serialización y persistencia de proyectos en formato de contenedor .ivtex.

Un archivo .ivtex es un contenedor ZIP seguro que contiene:
- project.json: metadatos del proyecto, selecciones y parámetros.
- assets/: recursos empaquetados (p. ej., la imagen de origen completa).

Implementa protección contra ZipSlip (path traversal), límites de tamaño contra
zip bombs y guardado atómico mediante archivos temporales con reemplazo atómico.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import uuid
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from iv_orbit_texture_studio.core.atlas_item import AtlasItem
from iv_orbit_texture_studio.core.document import Document
from iv_orbit_texture_studio.imaging.image_io import load_image_from_bytes
from iv_orbit_texture_studio.project_io.migrations import (
    migrate_project_dict,
)

#: Límite máximo de descompresión total para evitar ataques tipo zip-bomb (500 MB).
MAX_TOTAL_UNCOMPRESSED_SIZE_BYTES = 500 * 1024 * 1024
#: Límite máximo de archivos dentro del contenedor .ivtex.
MAX_ARCHIVE_FILE_COUNT = 1000
#: Límite máximo para el archivo project.json (10 MB).
MAX_PROJECT_JSON_SIZE_BYTES = 10 * 1024 * 1024


class ProjectIOError(Exception):
    """Error base de entrada/salida de proyectos."""


class CorruptProjectError(ProjectIOError):
    """El contenedor .ivtex o sus metadatos están corruptos o incompletos."""


class ZipSlipSecurityError(ProjectIOError):
    """Se detectó un intento de path traversal o ruta insegura en el archivo ZIP."""


class MissingSourceImageError(ProjectIOError):
    """No se encontró la imagen de origen ni en el proyecto empaquetado ni en el disco."""


def compute_bytes_sha256(data: bytes) -> str:
    """Calcula el hash SHA-256 de un flujo de bytes."""
    return hashlib.sha256(data).hexdigest()


def _validate_zip_entry_security(filename: str) -> None:
    """Valida que una ruta interna de un ZIP no intente escapar de su raíz (ZipSlip)."""
    # Rechazar barras iniciales o caracteres de unidad de Windows (C:)
    if filename.startswith(("/", "\\")) or ":" in filename:
        raise ZipSlipSecurityError(
            f"Ruta maliciosa o absoluta detectada en el proyecto: {filename!r}"
        )

    parts = PurePosixPath(filename).parts
    if ".." in parts:
        raise ZipSlipSecurityError(
            f"Intento de path traversal ('..') detectado en el proyecto: {filename!r}"
        )


def save_project(
    path: Path | str,
    document: Document,
    image_bytes: bytes | None = None,
    embed_image: bool = True,
) -> None:
    """Guarda un documento en un archivo de proyecto .ivtex de forma atómica.

    Args:
        path: Ruta destino del archivo .ivtex.
        document: Instancia del documento a persistir.
        image_bytes: Bytes en memoria de la imagen de origen (opcional).
        embed_image: Si es True, empaqueta los bytes de la imagen dentro del ZIP.
    """
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Actualizar hashes y metadatos de origen
    if image_bytes is not None:
        document.source.sha256 = compute_bytes_sha256(image_bytes)
        if embed_image:
            document.source.is_embedded = True
            # Conservar extensión original o usar png
            orig_ext = Path(document.source.file_path).suffix.lower()
            if not orig_ext or orig_ext not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga"}:
                orig_ext = ".png"
            document.source.asset_filename = f"assets/source{orig_ext}"

    document.touch_modified()
    payload_dict = document.to_dict()
    json_bytes = json.dumps(payload_dict, indent=2, ensure_ascii=False).encode("utf-8")

    # Escritura atómica: primero escribir en un archivo temporal en la misma carpeta
    temp_name = f".{target_path.stem}_{uuid.uuid4().hex[:8]}.ivtex.tmp"
    temp_path = target_path.parent / temp_name

    try:
        with zipfile.ZipFile(
            temp_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zf:
            # 1. Guardar project.json
            zf.writestr("project.json", json_bytes)

            # 2. Guardar imagen empaquetada si corresponde
            if embed_image and image_bytes is not None:
                zf.writestr(document.source.asset_filename, image_bytes)

            # 3. Guardar elementos del atlas si existen
            for item in document.atlas_items:
                bio = BytesIO()
                im = Image.fromarray(item.pixels, mode="RGBA")
                im.save(bio, format="PNG")
                zf.writestr(f"assets/items/{item.id}.png", bio.getvalue())

        # Reemplazo atómico
        os.replace(temp_path, target_path)
        document.mark_clean(target_path)
    except Exception as exc:
        if temp_path.exists():
            with contextlib.suppress(OSError):
                temp_path.unlink()
        raise ProjectIOError(f"Error al guardar el proyecto en '{target_path}': {exc}") from exc


def load_project(path: Path | str) -> tuple[Document, bytes | None]:
    """Carga y valida un proyecto .ivtex, retornando el documento y los bytes de la imagen.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        CorruptProjectError: Si el archivo no es un ZIP válido o le falta información.
        ZipSlipSecurityError: Si se detectan rutas maliciosas en el contenedor.
        UnsupportedVersionError: Si el formato es más moderno que el soportado.
        MissingSourceImageError: Si la imagen no está en el proyecto ni en el disco.
    """
    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"El archivo de proyecto no existe: '{source_path}'")

    if not zipfile.is_zipfile(source_path):
        raise CorruptProjectError(
            f"El archivo '{source_path.name}' no es un proyecto .ivtex válido."
        )

    total_uncompressed = 0

    try:
        with zipfile.ZipFile(source_path, mode="r") as zf:
            infolist = zf.infolist()

            if len(infolist) > MAX_ARCHIVE_FILE_COUNT:
                raise CorruptProjectError(
                    f"El archivo contiene demasiadas entradas "
                    f"({len(infolist)} > {MAX_ARCHIVE_FILE_COUNT})."
                )

            # Validar seguridad y límites de todas las entradas
            for info in infolist:
                _validate_zip_entry_security(info.filename)
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_SIZE_BYTES:
                    raise CorruptProjectError(
                        "El tamaño descompreso del proyecto excede el límite de seguridad (500 MB)."
                    )

            # Leer project.json
            try:
                json_info = zf.getinfo("project.json")
            except KeyError as err:
                raise CorruptProjectError(
                    "El contenedor .ivtex no contiene 'project.json'."
                ) from err

            if json_info.file_size > MAX_PROJECT_JSON_SIZE_BYTES:
                raise CorruptProjectError("El archivo project.json excede el límite de 10 MB.")

            try:
                raw_json = zf.read("project.json").decode("utf-8")
                raw_dict: dict[str, Any] = json.loads(raw_json)
            except Exception as exc:
                raise CorruptProjectError(f"Error al analizar 'project.json': {exc}") from exc

            # Validar y migrar versión de esquema
            migrated_dict = migrate_project_dict(raw_dict)
            document = Document.from_dict(migrated_dict, file_path=source_path)

            # Cargar imagen de origen
            image_bytes: bytes | None = None
            asset_fn = document.source.asset_filename

            if document.source.is_embedded and asset_fn in zf.namelist():
                image_bytes = zf.read(asset_fn)
            elif document.source.file_path:
                local_path = Path(document.source.file_path)
                if local_path.is_file():
                    try:
                        image_bytes = local_path.read_bytes()
                    except OSError:
                        image_bytes = None

            # Cargar elementos individuales del atlas si existen
            items_raw = migrated_dict.get("atlas_items", [])
            for item_dict in items_raw:
                if not isinstance(item_dict, dict):
                    continue
                item_id = str(item_dict.get("id", ""))
                asset_path = str(item_dict.get("asset_filename", f"assets/items/{item_id}.png"))
                if asset_path in zf.namelist():
                    item_bytes = zf.read(asset_path)
                    item_loaded = load_image_from_bytes(item_bytes, virtual_path=f"{item_id}.png")
                    atlas_item = AtlasItem.from_dict(item_dict, item_loaded.pixels)
                    document.atlas_items.append(atlas_item)

            # Si se esperaba una imagen pero no se encontró en ninguna parte
            if image_bytes is None and (document.source.is_embedded or document.source.file_path):
                raise MissingSourceImageError(
                    f"No se pudo cargar la imagen de origen '{document.source.file_path}' "
                    "ni desde los recursos del proyecto ni desde el disco local."
                )

            document.mark_clean(source_path)
            return document, image_bytes

    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise CorruptProjectError(f"Archivo .ivtex dañado o ilegible: {exc}") from exc

"""Exportador de texturas atlas y metadatos JSON para motores de juegos.

Escribe de forma atómica tanto la imagen combinada del atlas como su archivo
de metadatos JSON asociado.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

from iv_orbit_texture_studio.exporters.image_exporter import export_image
from iv_orbit_texture_studio.imaging.atlas import AtlasResult


class AtlasExportError(Exception):
    """Error al guardar el atlas o sus metadatos."""


def export_atlas_and_metadata(
    atlas_result: AtlasResult,
    target_image_path: Path | str,
    target_json_path: Path | str | None = None,
    overwrite: bool = True,
) -> tuple[Path, Path]:
    """Exporta de forma atómica la imagen del atlas y su archivo de metadatos JSON.

    Args:
        atlas_result: Resultado del empaquetado devuelto por pack_sprites_to_atlas.
        target_image_path: Ruta destino de la imagen del atlas (ej. my_atlas.png).
        target_json_path: Ruta destino del JSON (si es None, usa el mismo nombre
            con extensión .json).
        overwrite: Si es False y algún archivo existe, lanza FileExistsError.

    Returns:
        Tupla con (ruta_imagen_exportada, ruta_json_exportada).
    """
    img_path = Path(target_image_path).resolve()
    if target_json_path is not None:
        json_path = Path(target_json_path).resolve()
    else:
        json_path = img_path.with_suffix(".json")

    img_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    if not overwrite:
        if img_path.exists():
            raise FileExistsError(f"El archivo de imagen del atlas ya existe: '{img_path}'")
        if json_path.exists():
            raise FileExistsError(f"El archivo de metadatos JSON ya existe: '{json_path}'")

    # 1. Actualizar el nombre de imagen en los metadatos para que coincida con el nombre real
    meta_copy = dict(atlas_result.metadata)
    if "meta" in meta_copy and isinstance(meta_copy["meta"], dict):
        meta_inner = dict(meta_copy["meta"])
        meta_inner["image"] = img_path.name
        meta_copy["meta"] = meta_inner

    # 2. Exportar imagen atómicamente
    export_image(atlas_result.image, img_path, overwrite=overwrite)

    # 3. Exportar JSON atómicamente
    json_bytes = json.dumps(meta_copy, indent=2, ensure_ascii=False).encode("utf-8")
    temp_json = json_path.parent / f".{json_path.name}.tmp"

    try:
        temp_json.write_bytes(json_bytes)
        os.replace(temp_json, json_path)
    except Exception as exc:
        if temp_json.exists():
            with contextlib.suppress(OSError):
                temp_json.unlink()
        raise AtlasExportError(
            f"Error al escribir los metadatos JSON en '{json_path}': {exc}"
        ) from exc

    return img_path, json_path

"""Sistema de migraciones de versiones para proyectos .ivtex."""

from __future__ import annotations

from typing import Any

CURRENT_FORMAT_VERSION = 1


class UnsupportedVersionError(Exception):
    """Se lanza si el proyecto fue creado por una versión más reciente no soportada."""


def migrate_project_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Valida y migra el diccionario del proyecto a la versión más reciente."""
    version = data.get("format_version")
    if not isinstance(version, int):
        raise ValueError("El archivo de proyecto no especifica un 'format_version' entero válido.")

    if version > CURRENT_FORMAT_VERSION:
        raise UnsupportedVersionError(
            f"El proyecto tiene la versión {version}, pero esta aplicación solo "
            f"soporta hasta la versión {CURRENT_FORMAT_VERSION}. "
            "Por favor, actualizá la aplicación."
        )

    # Si en el futuro agregamos format_version 2, 3, etc.,
    # aquí aplicamos las migraciones secuenciales:
    # if version == 1:
    #     data = _migrate_v1_to_v2(data)
    #     version = 2

    return data

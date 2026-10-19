"""Modelo de datos del documento / proyecto de IV Orbit Texture Studio.

Representa el estado activo de la sesión: imagen de origen, parámetros de la
herramienta Texture Ripper, ruta de guardado y marca de modificaciones no
guardadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from iv_orbit_texture_studio.imaging.perspective import InterpolationMode, Point, Quad


@dataclass
class SourceImageInfo:
    """Metadatos de la imagen de origen."""

    file_path: str = ""
    sha256: str = ""
    is_embedded: bool = True
    asset_filename: str = "assets/source.png"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "sha256": self.sha256,
            "is_embedded": self.is_embedded,
            "asset_filename": self.asset_filename,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceImageInfo:
        return cls(
            file_path=str(data.get("file_path", "")),
            sha256=str(data.get("sha256", "")),
            is_embedded=bool(data.get("is_embedded", True)),
            asset_filename=str(data.get("asset_filename", "assets/source.png")),
        )


@dataclass
class TextureRipperData:
    """Estado y parámetros de la herramienta Texture Ripper."""

    quad: Quad | None = None
    output_width: int = 512
    output_height: int = 512
    lock_aspect_ratio: bool = False
    interpolation: InterpolationMode = InterpolationMode.LANCZOS4

    def to_dict(self) -> dict[str, Any]:
        quad_list = None
        if self.quad is not None:
            quad_list = [[p.x, p.y] for p in self.quad.points]
        return {
            "quad": quad_list,
            "output_width": self.output_width,
            "output_height": self.output_height,
            "lock_aspect_ratio": self.lock_aspect_ratio,
            "interpolation": self.interpolation.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextureRipperData:
        quad_raw = data.get("quad")
        quad = None
        if isinstance(quad_raw, list) and len(quad_raw) == 4:
            try:
                quad = Quad(
                    p0=Point(float(quad_raw[0][0]), float(quad_raw[0][1])),
                    p1=Point(float(quad_raw[1][0]), float(quad_raw[1][1])),
                    p2=Point(float(quad_raw[2][0]), float(quad_raw[2][1])),
                    p3=Point(float(quad_raw[3][0]), float(quad_raw[3][1])),
                )
            except Exception:
                quad = None

        interp_str = data.get("interpolation", InterpolationMode.LANCZOS4.value)
        try:
            interp = InterpolationMode(interp_str)
        except ValueError:
            interp = InterpolationMode.LANCZOS4

        return cls(
            quad=quad,
            output_width=int(data.get("output_width", 512)),
            output_height=int(data.get("output_height", 512)),
            lock_aspect_ratio=bool(data.get("lock_aspect_ratio", False)),
            interpolation=interp,
        )


@dataclass
class Document:
    """Documento de trabajo principal."""

    project_name: str = "Sin título"
    file_path: Path | None = None
    source: SourceImageInfo = field(default_factory=SourceImageInfo)
    texture_ripper: TextureRipperData = field(default_factory=TextureRipperData)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    is_modified: bool = False

    def touch_modified(self) -> None:
        self.modified_at = datetime.now(UTC).isoformat()
        self.is_modified = True

    def mark_clean(self, saved_path: Path | None = None) -> None:
        if saved_path is not None:
            self.file_path = saved_path
            if self.project_name == "Sin título":
                self.project_name = saved_path.stem
        self.is_modified = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": 1,
            "project_name": self.project_name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "source": self.source.to_dict(),
            "texture_ripper": self.texture_ripper.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], file_path: Path | None = None) -> Document:
        project_name = str(data.get("project_name", "Sin título"))
        if file_path is not None and project_name == "Sin título":
            project_name = file_path.stem

        source_data = data.get("source", {})
        ripper_data = data.get("texture_ripper", {})

        return cls(
            project_name=project_name,
            file_path=file_path,
            source=SourceImageInfo.from_dict(source_data),
            texture_ripper=TextureRipperData.from_dict(ripper_data),
            created_at=str(data.get("created_at", datetime.now(UTC).isoformat())),
            modified_at=str(data.get("modified_at", datetime.now(UTC).isoformat())),
            is_modified=False,
        )

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

from iv_orbit_texture_studio.core.atlas_item import AtlasItem
from iv_orbit_texture_studio.core.region import SpriteRegion
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
class AtlasSettings:
    """Configuración para el empaquetado del atlas de sprites."""

    padding: int = 2
    spacing: int = 2
    max_width: int = 4096
    max_height: int = 4096
    power_of_two: bool = True
    square: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "padding": self.padding,
            "spacing": self.spacing,
            "max_width": self.max_width,
            "max_height": self.max_height,
            "power_of_two": self.power_of_two,
            "square": self.square,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AtlasSettings:
        return cls(
            padding=int(data.get("padding", 2)),
            spacing=int(data.get("spacing", 2)),
            max_width=int(data.get("max_width", 4096)),
            max_height=int(data.get("max_height", 4096)),
            power_of_two=bool(data.get("power_of_two", True)),
            square=bool(data.get("square", False)),
        )


@dataclass
class TexturePrepSettings:
    """Configuración para los filtros de color y generación seamless."""

    brightness: float = 0.0  # [-1.0, 1.0]
    contrast: float = 0.0  # [-1.0, 1.0]
    saturation: float = 0.0  # [-1.0, 1.0]
    red_gain: float = 1.0  # [0.0, 3.0]
    green_gain: float = 1.0  # [0.0, 3.0]
    blue_gain: float = 1.0  # [0.0, 3.0]
    equalize_light: float = 0.0  # [0.0, 1.0]
    seamless_enabled: bool = False
    seamless_blend: float = 0.20  # [0.02, 0.45]
    tiling_grid_x: int = 3
    tiling_grid_y: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "red_gain": self.red_gain,
            "green_gain": self.green_gain,
            "blue_gain": self.blue_gain,
            "equalize_light": self.equalize_light,
            "seamless_enabled": self.seamless_enabled,
            "seamless_blend": self.seamless_blend,
            "tiling_grid_x": self.tiling_grid_x,
            "tiling_grid_y": self.tiling_grid_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TexturePrepSettings:
        return cls(
            brightness=float(data.get("brightness", 0.0)),
            contrast=float(data.get("contrast", 0.0)),
            saturation=float(data.get("saturation", 0.0)),
            red_gain=float(data.get("red_gain", 1.0)),
            green_gain=float(data.get("green_gain", 1.0)),
            blue_gain=float(data.get("blue_gain", 1.0)),
            equalize_light=float(data.get("equalize_light", 0.0)),
            seamless_enabled=bool(data.get("seamless_enabled", False)),
            seamless_blend=float(data.get("seamless_blend", 0.20)),
            tiling_grid_x=int(data.get("tiling_grid_x", 3)),
            tiling_grid_y=int(data.get("tiling_grid_y", 3)),
        )


@dataclass
class PbrSettings:
    """Configuración para la generación de mapas PBR y normales."""

    normal_strength: float = 2.0
    format_opengl: bool = True
    normal_blur: int = 0
    invert_x: bool = False
    invert_y: bool = False

    height_contrast: float = 1.0
    height_brightness: float = 0.0
    height_invert: bool = False
    height_blur: int = 0

    base_roughness: float = 0.5
    roughness_detail: float = 0.3
    roughness_invert: bool = False
    roughness_contrast: float = 1.0

    ao_strength: float = 1.5
    ao_radius: int = 5
    ao_contrast: float = 1.0

    metallic: float = 0.0
    packing_format: str = "ORM"  # "ORM" o "RMA"

    def to_dict(self) -> dict[str, Any]:
        return {
            "normal_strength": self.normal_strength,
            "format_opengl": self.format_opengl,
            "normal_blur": self.normal_blur,
            "invert_x": self.invert_x,
            "invert_y": self.invert_y,
            "height_contrast": self.height_contrast,
            "height_brightness": self.height_brightness,
            "height_invert": self.height_invert,
            "height_blur": self.height_blur,
            "base_roughness": self.base_roughness,
            "roughness_detail": self.roughness_detail,
            "roughness_invert": self.roughness_invert,
            "roughness_contrast": self.roughness_contrast,
            "ao_strength": self.ao_strength,
            "ao_radius": self.ao_radius,
            "ao_contrast": self.ao_contrast,
            "metallic": self.metallic,
            "packing_format": self.packing_format,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PbrSettings:
        return cls(
            normal_strength=float(data.get("normal_strength", 2.0)),
            format_opengl=bool(data.get("format_opengl", True)),
            normal_blur=int(data.get("normal_blur", 0)),
            invert_x=bool(data.get("invert_x", False)),
            invert_y=bool(data.get("invert_y", False)),
            height_contrast=float(data.get("height_contrast", 1.0)),
            height_brightness=float(data.get("height_brightness", 0.0)),
            height_invert=bool(data.get("height_invert", False)),
            height_blur=int(data.get("height_blur", 0)),
            base_roughness=float(data.get("base_roughness", 0.5)),
            roughness_detail=float(data.get("roughness_detail", 0.3)),
            roughness_invert=bool(data.get("roughness_invert", False)),
            roughness_contrast=float(data.get("roughness_contrast", 1.0)),
            ao_strength=float(data.get("ao_strength", 1.5)),
            ao_radius=int(data.get("ao_radius", 5)),
            ao_contrast=float(data.get("ao_contrast", 1.0)),
            metallic=float(data.get("metallic", 0.0)),
            packing_format=str(data.get("packing_format", "ORM")),
        )


@dataclass
class Document:
    """Documento de trabajo principal."""

    project_name: str = "Sin título"
    file_path: Path | None = None
    source: SourceImageInfo = field(default_factory=SourceImageInfo)
    texture_ripper: TextureRipperData = field(default_factory=TextureRipperData)
    sprites: list[SpriteRegion] = field(default_factory=list)
    atlas_items: list[AtlasItem] = field(default_factory=list)
    atlas: AtlasSettings = field(default_factory=AtlasSettings)
    texture_prep: TexturePrepSettings = field(default_factory=TexturePrepSettings)
    pbr: PbrSettings = field(default_factory=PbrSettings)
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
            "sprites": [s.to_dict() for s in self.sprites],
            "atlas_items": [item.to_dict() for item in self.atlas_items],
            "atlas": self.atlas.to_dict(),
            "texture_prep": self.texture_prep.to_dict(),
            "pbr": self.pbr.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], file_path: Path | None = None) -> Document:
        project_name = str(data.get("project_name", "Sin título"))
        if file_path is not None and project_name == "Sin título":
            project_name = file_path.stem

        source_data = data.get("source", {})
        ripper_data = data.get("texture_ripper", {})
        sprites_raw = data.get("sprites", [])
        sprites = [SpriteRegion.from_dict(s) for s in sprites_raw if isinstance(s, dict)]
        atlas_data = data.get("atlas", {})
        atlas = (
            AtlasSettings.from_dict(atlas_data) if isinstance(atlas_data, dict) else AtlasSettings()
        )
        prep_data = data.get("texture_prep", {})
        texture_prep = (
            TexturePrepSettings.from_dict(prep_data)
            if isinstance(prep_data, dict)
            else TexturePrepSettings()
        )
        pbr_data = data.get("pbr", {})
        pbr = PbrSettings.from_dict(pbr_data) if isinstance(pbr_data, dict) else PbrSettings()

        return cls(
            project_name=project_name,
            file_path=file_path,
            source=SourceImageInfo.from_dict(source_data),
            texture_ripper=TextureRipperData.from_dict(ripper_data),
            sprites=sprites,
            atlas=atlas,
            texture_prep=texture_prep,
            pbr=pbr,
            created_at=str(data.get("created_at", datetime.now(UTC).isoformat())),
            modified_at=str(data.get("modified_at", datetime.now(UTC).isoformat())),
            is_modified=False,
        )

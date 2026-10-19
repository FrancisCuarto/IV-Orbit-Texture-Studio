import json
import zipfile
from pathlib import Path

import pytest

from iv_orbit_texture_studio.core.document import Document
from iv_orbit_texture_studio.imaging.perspective import InterpolationMode, Point, Quad
from iv_orbit_texture_studio.project_io import (
    CorruptProjectError,
    MissingSourceImageError,
    UnsupportedVersionError,
    ZipSlipSecurityError,
    load_project,
    save_project,
)


def _make_dummy_image_bytes() -> bytes:
    from io import BytesIO

    from PIL import Image

    bio = BytesIO()
    img = Image.new("RGBA", (64, 48), color=(255, 0, 128, 255))
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_project_save_and_load_roundtrip(tmp_path: Path):
    proj_file = tmp_path / "test_project.ivtex"
    img_bytes = _make_dummy_image_bytes()

    doc = Document(project_name="Proyecto Prueba")
    doc.texture_ripper.quad = Quad(
        p0=Point(5.0, 5.0),
        p1=Point(55.0, 5.0),
        p2=Point(55.0, 40.0),
        p3=Point(5.0, 40.0),
    )
    doc.texture_ripper.output_width = 1024
    doc.texture_ripper.output_height = 512
    doc.texture_ripper.lock_aspect_ratio = True
    doc.texture_ripper.interpolation = InterpolationMode.CUBIC
    doc.source.file_path = "C:/fake/path/texture.png"

    # Save
    save_project(proj_file, doc, image_bytes=img_bytes, embed_image=True)
    assert proj_file.is_file()

    # Verify container is a valid zip with project.json and assets
    with zipfile.ZipFile(proj_file, "r") as zf:
        names = zf.namelist()
        assert "project.json" in names
        assert any(n.startswith("assets/") for n in names)

        # Inspect project.json
        meta = json.loads(zf.read("project.json").decode("utf-8"))
        assert meta["format_version"] == 1
        assert meta["project_name"] == "Proyecto Prueba"
        assert meta["texture_ripper"]["output_width"] == 1024
        assert meta["texture_ripper"]["output_height"] == 512
        assert meta["texture_ripper"]["interpolation"] == "cubic"

    # Load
    loaded_doc, loaded_bytes = load_project(proj_file)
    assert loaded_doc.project_name == "Proyecto Prueba"
    assert loaded_bytes == img_bytes
    assert loaded_doc.texture_ripper.quad is not None
    assert loaded_doc.texture_ripper.quad.p0 == Point(5.0, 5.0)
    assert loaded_doc.texture_ripper.output_width == 1024
    assert loaded_doc.texture_ripper.output_height == 512
    assert loaded_doc.texture_ripper.interpolation == InterpolationMode.CUBIC
    assert loaded_doc.texture_ripper.lock_aspect_ratio is True
    assert loaded_doc.is_modified is False


def test_project_zipslip_protection(tmp_path: Path):
    evil_proj = tmp_path / "evil.ivtex"

    # Create a zip containing an entry with path traversal '..'
    with zipfile.ZipFile(evil_proj, "w") as zf:
        zf.writestr("project.json", json.dumps({"format_version": 1}))
        zf.writestr("../evil_script.py", "print('hacked')")

    with pytest.raises(ZipSlipSecurityError, match="path traversal"):
        load_project(evil_proj)


def test_project_corrupt_zip(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.ivtex"
    corrupt_file.write_bytes(b"not a valid zip file content")

    with pytest.raises(CorruptProjectError, match="no es un proyecto .ivtex válido"):
        load_project(corrupt_file)


def test_project_missing_project_json(tmp_path: Path):
    no_json = tmp_path / "no_json.ivtex"
    with zipfile.ZipFile(no_json, "w") as zf:
        zf.writestr("dummy.txt", "hello")

    with pytest.raises(CorruptProjectError, match="no contiene 'project.json'"):
        load_project(no_json)


def test_project_invalid_json_content(tmp_path: Path):
    bad_json = tmp_path / "bad_json.ivtex"
    with zipfile.ZipFile(bad_json, "w") as zf:
        zf.writestr("project.json", "{this is not valid json")

    with pytest.raises(CorruptProjectError, match="Error al analizar 'project.json'"):
        load_project(bad_json)


def test_project_unsupported_future_version(tmp_path: Path):
    future_file = tmp_path / "future.ivtex"
    with zipfile.ZipFile(future_file, "w") as zf:
        zf.writestr(
            "project.json",
            json.dumps({"format_version": 999, "project_name": "Futuro"}),
        )

    with pytest.raises(UnsupportedVersionError, match="solo soporta hasta la versión"):
        load_project(future_file)


def test_project_missing_external_source_image(tmp_path: Path):
    proj_file = tmp_path / "external_missing.ivtex"
    with zipfile.ZipFile(proj_file, "w") as zf:
        zf.writestr(
            "project.json",
            json.dumps(
                {
                    "format_version": 1,
                    "project_name": "Perdido",
                    "source": {
                        "file_path": str(tmp_path / "non_existent.png"),
                        "is_embedded": False,
                    },
                }
            ),
        )

    with pytest.raises(MissingSourceImageError, match="No se pudo cargar la imagen de origen"):
        load_project(proj_file)


def test_project_with_sprites_and_atlas(tmp_path: Path):
    from iv_orbit_texture_studio.core.region import Pivot, PivotMode, Rect, SpriteRegion

    proj_file = tmp_path / "sprites_proj.ivtex"
    img_bytes = _make_dummy_image_bytes()

    doc = Document(project_name="Proyecto con Sprites")
    doc.sprites.append(
        SpriteRegion.create(
            "sprite_1", Rect(0, 0, 16, 16), Pivot.from_mode(PivotMode.BOTTOM_CENTER)
        )
    )
    doc.sprites.append(
        SpriteRegion.create("sprite_2", Rect(20, 10, 32, 32), Pivot.from_mode(PivotMode.CENTER))
    )
    doc.atlas.spacing = 4
    doc.atlas.power_of_two = True

    save_project(proj_file, doc, image_bytes=img_bytes)

    loaded, _ = load_project(proj_file)
    assert len(loaded.sprites) == 2
    assert loaded.sprites[0].name == "sprite_1"
    assert loaded.sprites[0].rect == Rect(0, 0, 16, 16)
    assert loaded.sprites[0].pivot.mode == PivotMode.BOTTOM_CENTER
    assert loaded.sprites[1].name == "sprite_2"
    assert loaded.atlas.spacing == 4
    assert loaded.atlas.power_of_two is True


def test_project_with_texture_prep_settings(tmp_path):
    proj_file = tmp_path / "prep_proj.ivtex"
    img_bytes = _make_dummy_image_bytes()

    doc = Document(project_name="Proyecto con Filtros y Seamless")
    doc.texture_prep.brightness = 0.25
    doc.texture_prep.contrast = 0.40
    doc.texture_prep.saturation = -0.50
    doc.texture_prep.red_gain = 1.2
    doc.texture_prep.seamless_enabled = True
    doc.texture_prep.seamless_blend = 0.30
    doc.texture_prep.tiling_grid_x = 4
    doc.texture_prep.tiling_grid_y = 2

    save_project(proj_file, doc, image_bytes=img_bytes)

    loaded, _ = load_project(proj_file)
    assert loaded.texture_prep.brightness == 0.25
    assert loaded.texture_prep.contrast == 0.40
    assert loaded.texture_prep.saturation == -0.50
    assert loaded.texture_prep.red_gain == 1.2
    assert loaded.texture_prep.seamless_enabled is True
    assert loaded.texture_prep.seamless_blend == 0.30
    assert loaded.texture_prep.tiling_grid_x == 4
    assert loaded.texture_prep.tiling_grid_y == 2


def test_project_with_pbr_settings(tmp_path):
    proj_file = tmp_path / "pbr_proj.ivtex"
    img_bytes = _make_dummy_image_bytes()

    doc = Document(project_name="Proyecto con Mapas PBR")
    doc.pbr.normal_strength = 3.5
    doc.pbr.format_opengl = False  # DirectX
    doc.pbr.normal_blur = 1
    doc.pbr.height_contrast = 1.4
    doc.pbr.height_invert = True
    doc.pbr.base_roughness = 0.7
    doc.pbr.roughness_detail = 0.5
    doc.pbr.roughness_invert = True  # Glossiness
    doc.pbr.ao_strength = 2.0
    doc.pbr.ao_radius = 7
    doc.pbr.metallic = 0.8
    doc.pbr.packing_format = "RMA"

    save_project(proj_file, doc, image_bytes=img_bytes)

    loaded, _ = load_project(proj_file)
    assert abs(loaded.pbr.normal_strength - 3.5) < 1e-4
    assert loaded.pbr.format_opengl is False
    assert loaded.pbr.normal_blur == 1
    assert abs(loaded.pbr.height_contrast - 1.4) < 1e-4
    assert loaded.pbr.height_invert is True
    assert abs(loaded.pbr.base_roughness - 0.7) < 1e-4
    assert abs(loaded.pbr.roughness_detail - 0.5) < 1e-4
    assert loaded.pbr.roughness_invert is True
    assert abs(loaded.pbr.ao_strength - 2.0) < 1e-4
    assert loaded.pbr.ao_radius == 7
    assert abs(loaded.pbr.metallic - 0.8) < 1e-4
    assert loaded.pbr.packing_format == "RMA"

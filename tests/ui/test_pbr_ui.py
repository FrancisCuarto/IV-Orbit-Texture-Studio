"""Pruebas de interfaz e integración para generación de mapas PBR y normales."""

from pathlib import Path

import numpy as np
from PIL import Image

from iv_orbit_texture_studio.core.document import PbrSettings
from iv_orbit_texture_studio.imaging.image_io import load_image
from iv_orbit_texture_studio.ui.main_window import MainWindow


def _create_sample_texture(path: Path, width: int = 64, height: int = 64) -> None:
    """Crea una imagen con gradientes y detalles para pruebas PBR."""
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            arr[y, x] = [
                (x * 4) % 256,
                (y * 4) % 256,
                ((x + y) * 2) % 256,
                255,
            ]
    img = Image.fromarray(arr, mode="RGBA")
    img.save(path)


def test_pbr_panel_initial_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Sin imagen cargada, los controles PBR deben estar deshabilitados
    assert not window.action_export_pbr.isEnabled()
    assert not window.pbr_panel._combo_map_type.isEnabled()
    assert not window.pbr_panel._slider_norm_str.isEnabled()
    assert not window.pbr_panel._combo_norm_format.isEnabled()
    assert not window.pbr_panel._chk_inv_x.isEnabled()
    assert not window.pbr_panel._chk_inv_y.isEnabled()
    assert not window.pbr_panel._slider_h_contrast.isEnabled()
    assert not window.pbr_panel._slider_base_rough.isEnabled()
    assert not window.pbr_panel._slider_ao_str.isEnabled()
    assert not window.pbr_panel._btn_reset.isEnabled()
    assert not window.pbr_panel._btn_export_active.isEnabled()
    assert not window.pbr_panel._btn_export_all.isEnabled()


def test_pbr_mode_switching_and_dock_visibility(qtbot, tmp_path):
    img_path = tmp_path / "texture.png"
    _create_sample_texture(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.open_image(img_path) is True

    # Inicialmente modo ripper
    assert window.action_mode_ripper.isChecked()
    assert not window.action_mode_pbr.isChecked()
    assert window.canvas.tool is window.tool

    # Cambiar a modo Mapas PBR y Normales
    window.set_mode("pbr")
    assert window.action_mode_pbr.isChecked()
    assert not window.action_mode_ripper.isChecked()
    assert not window.action_mode_sprites.isChecked()
    assert not window.action_mode_prep.isChecked()
    assert window.canvas.tool is window.pbr_tool
    assert window.dock_pbr.isVisible()

    # Volver a modo Preparación y luego a PBR
    window.set_mode("prep")
    assert window.action_mode_prep.isChecked()
    assert window.canvas.tool is window.prep_tool

    window.set_mode("pbr")
    assert window.action_mode_pbr.isChecked()
    assert window.canvas.tool is window.pbr_tool


def test_pbr_map_type_switching_and_canvas(qtbot, tmp_path):
    img_path = tmp_path / "texture.png"
    _create_sample_texture(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.set_mode("pbr")

    # Por defecto, el mapa activo es 'normal'
    assert window.pbr_tool.active_map_type == "normal"
    normal_pixels = window.pbr_tool.processed_pixels
    assert normal_pixels is not None

    # Cambiar al mapa de altura (height)
    window.pbr_panel._combo_map_type.setCurrentIndex(1)
    assert window.pbr_tool.active_map_type == "height"
    height_pixels = window.pbr_tool.processed_pixels
    assert height_pixels is not None
    assert not np.array_equal(normal_pixels, height_pixels)

    # Cambiar a rugosidad (roughness)
    window.pbr_panel._combo_map_type.setCurrentIndex(2)
    assert window.pbr_tool.active_map_type == "roughness"

    # Cambiar a oclusión ambiental (ao)
    window.pbr_panel._combo_map_type.setCurrentIndex(3)
    assert window.pbr_tool.active_map_type == "ao"

    # Cambiar a empaquetado ORM/RMA
    window.pbr_panel._combo_map_type.setCurrentIndex(4)
    assert window.pbr_tool.active_map_type == "orm"


def test_pbr_parameter_adjustments_reactive(qtbot, tmp_path):
    img_path = tmp_path / "pbr_reactive.png"
    _create_sample_texture(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.set_mode("pbr")

    # Controles habilitados
    assert window.pbr_panel._slider_norm_str.isEnabled()
    assert window.pbr_panel._btn_reset.isEnabled()

    initial_normal = window.pbr_tool.get_map("normal")
    assert initial_normal is not None

    # Modificar fuerza de normales a 4.0 (slider a 40)
    window.pbr_panel._slider_norm_str.setValue(40)
    modified_normal = window.pbr_tool.get_map("normal")
    assert modified_normal is not None
    assert not np.array_equal(initial_normal, modified_normal)
    assert window.document.is_modified

    # Cambiar formato a DirectX
    window.pbr_panel._combo_norm_format.setCurrentIndex(1)
    directx_normal = window.pbr_tool.get_map("normal")
    assert directx_normal is not None
    assert not np.array_equal(modified_normal, directx_normal)

    # Restablecer con botón
    window.pbr_panel._btn_reset.click()
    reset_normal = window.pbr_tool.get_map("normal")
    assert reset_normal is not None
    assert np.array_equal(initial_normal, reset_normal)
    assert window.pbr_panel._slider_norm_str.value() == 20
    assert window.pbr_panel._combo_norm_format.currentIndex() == 0


def test_export_active_pbr_map(qtbot, tmp_path, monkeypatch):
    img_path = tmp_path / "to_export.png"
    _create_sample_texture(img_path, width=48, height=48)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.set_mode("pbr")

    export_target = tmp_path / "exported_normal.png"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_target), "PNG"),
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information",
        lambda *args, **kwargs: None,
    )

    window.pbr_panel.export_active_map()

    assert export_target.exists()
    loaded_exported = load_image(export_target)
    assert loaded_exported.width == 48
    assert loaded_exported.height == 48


def test_export_all_pbr_maps_batch(qtbot, tmp_path, monkeypatch):
    img_path = tmp_path / "brick.png"
    _create_sample_texture(img_path, width=32, height=32)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.set_mode("pbr")

    batch_dir = tmp_path / "pbr_output"
    batch_dir.mkdir()

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(batch_dir),
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information",
        lambda *args, **kwargs: None,
    )

    # Disparar mediante la acción o el panel
    assert window.action_export_pbr.isEnabled()
    window.action_export_pbr.trigger()

    expected_files = [
        batch_dir / "brick_normal.png",
        batch_dir / "brick_height.png",
        batch_dir / "brick_roughness.png",
        batch_dir / "brick_ao.png",
        batch_dir / "brick_orm.png",
    ]

    for f in expected_files:
        assert f.exists(), f"El archivo {f.name} no se encontró en la carpeta de exportación."
        loaded = load_image(f)
        assert loaded.width == 32
        assert loaded.height == 32


def test_project_save_and_load_pbr_settings(qtbot, tmp_path):
    img_path = tmp_path / "proj_texture.png"
    _create_sample_texture(img_path, width=40, height=40)

    proj_path = tmp_path / "project_phase6.ivtex"

    window1 = MainWindow()
    qtbot.addWidget(window1)
    window1.show()
    assert window1.open_image(img_path) is True

    # Configurar valores personalizados de PBR
    custom_pbr = PbrSettings(
        normal_strength=3.5,
        format_opengl=False,
        invert_x=True,
        invert_y=True,
        height_contrast=1.45,
        height_brightness=-0.1,
        height_invert=True,
        base_roughness=0.8,
        roughness_detail=0.4,
        roughness_invert=True,
        ao_strength=0.7,
        ao_radius=6,
        metallic=0.25,
        packing_format="RMA",
    )
    window1.pbr_panel.set_settings(custom_pbr)

    # Guardar proyecto
    assert window1.save_project(proj_path) is True
    assert proj_path.exists()

    # Abrir en una segunda ventana
    window2 = MainWindow()
    qtbot.addWidget(window2)
    window2.show()
    assert window2.open_project(proj_path) is True

    # Verificar que todos los parámetros PBR se restauraron fielmente
    restored = window2.pbr_panel.get_settings()
    assert abs(restored.normal_strength - 3.5) < 1e-3
    assert restored.format_opengl is False
    assert restored.invert_x is True
    assert restored.invert_y is True
    assert abs(restored.height_contrast - 1.45) < 1e-3
    assert abs(restored.height_brightness - (-0.1)) < 1e-3
    assert restored.height_invert is True
    assert abs(restored.base_roughness - 0.8) < 1e-3
    assert abs(restored.roughness_detail - 0.4) < 1e-3
    assert restored.roughness_invert is True
    assert abs(restored.ao_strength - 0.7) < 1e-3
    assert restored.ao_radius == 6
    assert abs(restored.metallic - 0.25) < 1e-3
    assert restored.packing_format == "RMA"

"""Pruebas de interfaz e integración para Preparación de texturas, Seamless y Mosaico."""

from pathlib import Path

import numpy as np
from PIL import Image

from iv_orbit_texture_studio.core.document import TexturePrepSettings
from iv_orbit_texture_studio.imaging.image_io import load_image
from iv_orbit_texture_studio.ui.main_window import MainWindow


def _create_sample_texture(path: Path, width: int = 64, height: int = 64) -> None:
    """Crea una imagen de textura de muestra para pruebas."""
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            arr[y, x] = [
                (x * 4) % 256,
                (y * 4) % 256,
                128,
                255,
            ]
    img = Image.fromarray(arr, mode="RGBA")
    img.save(path)


def test_prep_panel_initial_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Sin imagen cargada, los controles de preparación deben estar deshabilitados
    assert not window.action_export_prep.isEnabled()
    assert not window.prep_panel._slider_bright.isEnabled()
    assert not window.prep_panel._slider_contrast.isEnabled()
    assert not window.prep_panel._slider_sat.isEnabled()
    assert not window.prep_panel._slider_eq.isEnabled()
    assert not window.prep_panel._btn_reset_color.isEnabled()
    assert not window.prep_panel._chk_seamless.isEnabled()
    assert not window.prep_panel._chk_tiled.isEnabled()
    assert not window.prep_panel._btn_export.isEnabled()


def test_mode_switching_and_dock_visibility(qtbot, tmp_path):
    img_path = tmp_path / "texture.png"
    _create_sample_texture(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.open_image(img_path) is True

    # Inicialmente modo ripper
    assert window.action_mode_ripper.isChecked()
    assert not window.action_mode_prep.isChecked()
    assert window.canvas.tool is window.tool

    # Cambiar a modo Preparación y Mosaico
    window.set_mode("prep")
    assert window.action_mode_prep.isChecked()
    assert not window.action_mode_ripper.isChecked()
    assert not window.action_mode_sprites.isChecked()
    assert window.canvas.tool is window.prep_tool
    assert window.dock_prep.isVisible()

    # Volver a modo Sprites y luego a Ripper
    window.set_mode("sprites")
    assert window.action_mode_sprites.isChecked()
    assert window.canvas.tool is window.sprite_tool

    window.set_mode("ripper")
    assert window.action_mode_ripper.isChecked()
    assert window.canvas.tool is window.tool


def test_color_adjustments_reactive(qtbot, tmp_path):
    img_path = tmp_path / "color_texture.png"
    _create_sample_texture(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.set_mode("prep")

    # Controles habilitados
    assert window.prep_panel._slider_bright.isEnabled()
    assert window.prep_panel._btn_reset_color.isEnabled()

    initial_pixels = window.prep_tool.processed_pixels
    assert initial_pixels is not None

    # Ajustar brillo a +30 %
    window.prep_panel._slider_bright.setValue(30)
    modified_pixels = window.prep_tool.processed_pixels
    assert modified_pixels is not None
    assert not np.array_equal(initial_pixels, modified_pixels)
    assert window.document.is_modified

    # Ajustar contraste a +20 %
    window.prep_panel._slider_contrast.setValue(20)

    # Restablecer filtros con el botón
    window.prep_panel._btn_reset_color.click()
    reset_pixels = window.prep_tool.processed_pixels
    assert reset_pixels is not None
    assert np.array_equal(initial_pixels, reset_pixels)
    assert window.prep_panel._slider_bright.value() == 0
    assert window.prep_panel._slider_contrast.value() == 0


def test_seamless_toggle_and_tiling_preview(qtbot, tmp_path):
    img_path = tmp_path / "seamless_texture.png"
    _create_sample_texture(img_path, width=64, height=64)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.set_mode("prep")

    # Activar seamless
    window.prep_panel._chk_seamless.setChecked(True)
    settings = window.prep_panel.get_settings()
    assert settings.seamless_enabled is True
    assert window.prep_tool.settings.seamless_enabled is True

    # Cambiar margen de mezcla a 25 %
    window.prep_panel._slider_blend.setValue(25)
    assert window.prep_panel.get_settings().seamless_blend == 0.25

    # Activar vista mosaico (tiling) 3x3
    window.prep_panel._chk_tiled.setChecked(True)
    assert window.prep_tool.is_tiled_view is True

    window.prep_panel._spin_grid_x.setValue(3)
    window.prep_panel._spin_grid_y.setValue(3)

    tiled_pixels = window.prep_tool.processed_pixels
    assert tiled_pixels is not None
    assert tiled_pixels.shape == (64 * 3, 64 * 3, 4)

    # Desactivar vista mosaico y volver a 1x1
    window.prep_panel._chk_tiled.setChecked(False)
    assert window.prep_tool.is_tiled_view is False
    assert window.prep_tool.processed_pixels.shape == (64, 64, 4)


def test_export_prepared_texture(qtbot, tmp_path, monkeypatch):
    img_path = tmp_path / "to_export.png"
    _create_sample_texture(img_path, width=48, height=48)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.set_mode("prep")

    # Ajustar saturación y activar seamless
    window.prep_panel._slider_sat.setValue(25)
    window.prep_panel._chk_seamless.setChecked(True)

    export_target = tmp_path / "exported_texture.png"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_target), "PNG"),
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information",
        lambda *args, **kwargs: None,
    )

    window.prep_panel.export_texture()

    assert export_target.exists()
    loaded_exported = load_image(export_target)
    assert loaded_exported.width == 48
    assert loaded_exported.height == 48


def test_project_save_and_load_texture_prep_settings(qtbot, tmp_path):
    img_path = tmp_path / "proj_texture.png"
    _create_sample_texture(img_path, width=50, height=50)

    proj_path = tmp_path / "project_phase5.ivtex"

    window1 = MainWindow()
    qtbot.addWidget(window1)
    window1.show()
    assert window1.open_image(img_path) is True

    # Configurar valores personalizados de preparación
    custom_settings = TexturePrepSettings(
        brightness=0.15,
        contrast=0.25,
        saturation=-0.10,
        equalize_light=0.40,
        red_gain=1.1,
        green_gain=0.9,
        blue_gain=1.0,
        seamless_enabled=True,
        seamless_blend=0.20,
        tiling_grid_x=3,
        tiling_grid_y=3,
    )
    window1.prep_panel.set_settings(custom_settings)

    # Guardar proyecto
    assert window1.save_project(proj_path) is True
    assert proj_path.exists()

    # Abrir en una nueva ventana
    window2 = MainWindow()
    qtbot.addWidget(window2)
    window2.show()
    assert window2.open_project(proj_path) is True

    # Verificar que los ajustes se restauraron exactamente
    restored = window2.prep_panel.get_settings()
    assert abs(restored.brightness - 0.15) < 1e-3
    assert abs(restored.contrast - 0.25) < 1e-3
    assert abs(restored.saturation - (-0.10)) < 1e-3
    assert abs(restored.equalize_light - 0.40) < 1e-3
    assert abs(restored.red_gain - 1.1) < 1e-3
    assert abs(restored.green_gain - 0.9) < 1e-3
    assert abs(restored.blue_gain - 1.0) < 1e-3
    assert restored.seamless_enabled is True
    assert abs(restored.seamless_blend - 0.20) < 1e-3
    assert restored.tiling_grid_x == 3
    assert restored.tiling_grid_y == 3

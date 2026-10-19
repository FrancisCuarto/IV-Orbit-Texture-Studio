"""Pruebas de interfaz e integración para las herramientas de Sprites y Atlas."""

from pathlib import Path

import numpy as np
from PIL import Image

from iv_orbit_texture_studio.core.region import PivotMode
from iv_orbit_texture_studio.ui.main_window import MainWindow


def _create_sprite_sheet_image(path: Path) -> None:
    """Crea una imagen con fondo transparente y dos sprites coloreados bien separados."""
    arr = np.zeros((100, 200, 4), dtype=np.uint8)
    # Sprite 1: en (10, 10), 30x40
    arr[10:50, 10:40] = [255, 0, 0, 255]
    # Sprite 2: en (60, 20), 40x50
    arr[20:70, 60:100] = [0, 255, 0, 255]
    img = Image.fromarray(arr, mode="RGBA")
    img.save(path)


def test_sprite_panel_initial_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Sin imagen cargada, los controles de sprites deben estar deshabilitados
    assert not window.action_detect_sprites.isEnabled()
    assert not window.action_export_atlas.isEnabled()
    assert not window.action_pack_atlas.isEnabled()
    assert not window.sprite_panel._btn_detect.isEnabled()
    assert not window.sprite_panel._btn_pack.isEnabled()
    assert not window.sprite_panel._btn_export_atlas.isEnabled()


def test_sprite_auto_detection_and_table(qtbot, tmp_path):
    img_path = tmp_path / "sheet.png"
    _create_sprite_sheet_image(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.open_image(img_path) is True
    window.set_mode("sprites")
    assert window.action_mode_sprites.isChecked()
    assert window.canvas.tool is window.sprite_tool

    # Ejecutar detección automática
    window.sprite_panel.detect_sprites()
    assert len(window.sprite_tool.sprites) == 2

    # Verificar tabla poblada
    assert window.sprite_panel._table.rowCount() == 2
    row0_name = window.sprite_panel._table.item(0, 0).text()
    assert row0_name == "sprite_01"

    # Seleccionar primer sprite
    window.sprite_tool.select_sprite(window.sprite_tool.sprites[0].id)
    assert window.sprite_panel._edit_name.text() == "sprite_01"

    # Renombrar sprite
    window.sprite_panel._edit_name.setText("hero_idle")
    window.sprite_panel._on_name_edited()
    assert window.sprite_tool.sprites[0].name == "hero_idle"
    assert window.sprite_panel._table.item(0, 0).text() == "hero_idle"


def test_sprite_pivot_configuration(qtbot, tmp_path):
    img_path = tmp_path / "sheet_pivot.png"
    _create_sprite_sheet_image(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.sprite_panel.detect_sprites()

    # Seleccionar sprite
    s0 = window.sprite_tool.sprites[0]
    window.sprite_tool.select_sprite(s0.id)

    # Cambiar pivote a BOTTOM_CENTER (pies)
    combo = window.sprite_panel._combo_pivot
    idx = combo.findData(PivotMode.BOTTOM_CENTER)
    assert idx >= 0
    combo.setCurrentIndex(idx)

    # Verificar que el sprite tiene el modo actualizado
    curr = window.sprite_tool.selected_sprite
    assert curr is not None
    assert curr.pivot.mode == PivotMode.BOTTOM_CENTER
    assert curr.pivot.x == 0.5
    assert curr.pivot.y == 1.0


def test_atlas_generation_and_export(qtbot, tmp_path, monkeypatch):
    img_path = tmp_path / "sheet_atlas.png"
    _create_sprite_sheet_image(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.sprite_panel.detect_sprites()

    # Generar atlas
    atlas_res = window.sprite_panel.generate_atlas()
    assert atlas_res is not None
    assert atlas_res.width > 0
    assert atlas_res.height > 0
    assert len(atlas_res.sprites) == 2
    assert window.action_export_atlas.isEnabled()
    assert window.sprite_panel._btn_export_atlas.isEnabled()

    # Exportar atlas interceptando QFileDialog y QMessageBox
    out_img = tmp_path / "my_atlas.png"

    def mock_get_save_filename(*args, **kwargs):
        return (str(out_img), "Imágenes PNG (*.png)")

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        mock_get_save_filename,
    )
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: None)

    window.sprite_panel.export_atlas()
    assert out_img.is_file()
    out_json = out_img.with_suffix(".json")
    assert out_json.is_file()
    assert '"frames"' in out_json.read_text(encoding="utf-8")


def test_sprite_project_persistence(qtbot, tmp_path):
    img_path = tmp_path / "project_sprites.png"
    _create_sprite_sheet_image(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    window.sprite_panel.detect_sprites()

    # Renombrar primer sprite y cambiar pivote
    s0_id = window.sprite_tool.sprites[0].id
    window.sprite_tool.rename_sprite(s0_id, "player_run")
    window.sprite_tool.select_sprite(s0_id)
    combo = window.sprite_panel._combo_pivot
    combo.setCurrentIndex(combo.findData(PivotMode.BOTTOM_CENTER))

    # Guardar proyecto
    proj_path = tmp_path / "sprites_project.ivtex"
    assert window.save_project(proj_path) is True
    assert proj_path.is_file()

    # Cargar en una nueva ventana
    window2 = MainWindow()
    qtbot.addWidget(window2)
    window2.show()
    assert window2.open_project(proj_path) is True

    # Verificar que los sprites fueron restaurados
    assert len(window2.sprite_tool.sprites) == 2
    restored_0 = window2.sprite_tool.sprites[0]
    assert restored_0.name == "player_run"
    assert restored_0.pivot.mode == PivotMode.BOTTOM_CENTER


def test_manual_sprite_add_and_remove(qtbot, tmp_path):
    img_path = tmp_path / "sheet_manual.png"
    _create_sprite_sheet_image(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)

    assert len(window.sprite_tool.sprites) == 0
    window.sprite_panel._btn_add_manual.click()
    assert len(window.sprite_tool.sprites) == 1

    # Eliminar
    window.sprite_panel._btn_remove.click()
    assert len(window.sprite_tool.sprites) == 0

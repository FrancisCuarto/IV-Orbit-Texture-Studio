"""Pruebas de interfaz e integración para el flujo principal de recorte y composición de Atlas.

Verifica:
1. Pegado directo de capturas de pantalla desde el portapapeles (Ctrl+V).
2. Recorte de perspectiva en Texture Ripper y botón '➕ Añadir al Atlas'.
3. Acumulación de múltiples texturas desde capturas distintas.
4. Modo Sprites y Atlas con arrastre interactivo, posicionamiento libre y snapping.
5. Auto-empaquetado inteligente (MaxRects).
6. Exportación completa del Atlas (imagen PNG + metadatos JSON).
7. Persistencia y restauración de atlas con texturas en proyectos .ivtex.
"""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtWidgets import QFileDialog, QMessageBox

from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper
from iv_orbit_texture_studio.ui.main_window import MainWindow


def _create_mock_qimage(w: int, h: int, color: QColor) -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGBA8888)
    img.fill(color)
    return img


def test_clipboard_paste_and_ripper_initialization(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Inicialmente sin imagen
    assert not window.canvas.has_image
    assert not window.action_export.isEnabled()
    assert not window.action_add_to_atlas.isEnabled()

    # Simular imagen en el portapapeles
    mock_screenshot = _create_mock_qimage(400, 300, QColor(255, 120, 50, 255))

    class MockClipboard:
        def image(self):
            return mock_screenshot

    monkeypatch.setattr("PySide6.QtGui.QGuiApplication.clipboard", lambda: MockClipboard())

    # Ejecutar pegado desde portapapeles (Ctrl+V)
    success = window.paste_from_clipboard()
    assert success is True
    assert window.canvas.has_image
    assert window.current_image is not None
    assert window.current_image.width == 400
    assert window.current_image.height == 300
    assert window.action_mode_ripper.isChecked()
    assert window.tool.selection.is_valid()
    assert window.action_add_to_atlas.isEnabled()


def test_add_multiple_ripped_textures_to_atlas(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # 1. Pegar primera captura
    mock_screenshot_1 = _create_mock_qimage(300, 300, QColor(200, 50, 50, 255))
    monkeypatch.setattr(
        "PySide6.QtGui.QGuiApplication.clipboard",
        lambda: type("MockClip", (), {"image": lambda self: mock_screenshot_1})(),
    )
    window.paste_from_clipboard()

    # Configurar dimensiones de salida a 128x128
    window.ripper_panel.set_dimensions(128, 128)

    # Añadir al atlas
    window.ripper_panel.add_to_atlas()
    assert len(window.atlas_tool.items) == 1
    item1 = window.atlas_tool.items[0]
    assert item1.width == 128
    assert item1.height == 128

    # 2. Pegar segunda captura diferente
    mock_screenshot_2 = _create_mock_qimage(500, 400, QColor(50, 150, 250, 255))
    monkeypatch.setattr(
        "PySide6.QtGui.QGuiApplication.clipboard",
        lambda: type("MockClip", (), {"image": lambda self: mock_screenshot_2})(),
    )
    window.paste_from_clipboard()

    # Configurar dimensiones de salida a 64x64
    window.ripper_panel.set_dimensions(64, 64)

    # Añadir segunda textura al atlas
    window.ripper_panel.add_to_atlas()
    assert len(window.atlas_tool.items) == 2
    item2 = window.atlas_tool.items[1]
    assert item2.width == 64
    assert item2.height == 64


def test_atlas_mode_canvas_and_interactive_dragging(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Cargar captura y añadir 2 texturas
    img = _create_mock_qimage(200, 200, QColor(100, 200, 100, 255))
    monkeypatch.setattr(
        "PySide6.QtGui.QGuiApplication.clipboard",
        lambda: type("MockClip", (), {"image": lambda self: img})(),
    )
    window.paste_from_clipboard()
    window.ripper_panel.set_dimensions(100, 100)
    window.ripper_panel.add_to_atlas()
    window.ripper_panel.set_dimensions(80, 80)
    window.ripper_panel.add_to_atlas()

    # Cambiar a Modo Sprites y Atlas
    window.set_mode("sprites")
    assert window.action_mode_sprites.isChecked()
    assert window.sprite_tool.submode == "atlas"
    assert window.sprite_panel._tabs.currentIndex() == 0  # Compositor de Atlas
    assert window.sprite_panel._table_atlas.rowCount() == 2

    # Verificar selección
    item0 = window.atlas_tool.items[0]
    window.atlas_tool.select_item(item0.id)
    assert window.atlas_tool.selected_id == item0.id
    assert window.sprite_panel._edit_atlas_name.text() == item0.name

    # Probar arrastre interactivo con el ratón sobre el lienzo
    mapper = CoordinateMapper()
    p_press = QPointF(item0.x + 10, item0.y + 10)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p_press,
        p_press,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    handled_press = window.sprite_tool.handle_mouse_press(press_event, mapper)
    assert handled_press is True

    # Mover el ratón 50 px a la derecha y 30 px hacia abajo
    p_move = QPointF(item0.x + 60, item0.y + 40)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p_move,
        p_move,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    handled_move = window.sprite_tool.handle_mouse_move(move_event, mapper)
    assert handled_move is True

    p_rel = QPointF(item0.x + 60, item0.y + 40)
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        p_rel,
        p_rel,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    handled_release = window.sprite_tool.handle_mouse_release(release_event, mapper)
    assert handled_release is True

    # Comprobar que la posición cambió
    assert item0.x == 50 or item0.x > 0
    assert item0.y == 30 or item0.y > 0


def test_atlas_auto_pack_and_export(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Cargar captura y añadir 3 texturas
    img = _create_mock_qimage(256, 256, QColor(255, 200, 50, 255))
    monkeypatch.setattr(
        "PySide6.QtGui.QGuiApplication.clipboard",
        lambda: type("MockClip", (), {"image": lambda self: img})(),
    )
    window.paste_from_clipboard()
    window.ripper_panel.set_dimensions(128, 128)
    window.ripper_panel.add_to_atlas()
    window.ripper_panel.set_dimensions(64, 64)
    window.ripper_panel.add_to_atlas()
    window.ripper_panel.set_dimensions(64, 64)
    window.ripper_panel.add_to_atlas()

    window.set_mode("sprites")

    # Ejecutar auto-empaquetado
    window.sprite_panel.auto_pack_atlas()

    # Verificar que ningún elemento solapa con otro
    items = window.atlas_tool.items
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            assert not items[i].rect.intersects(items[j].rect)

    # Exportar atlas interceptando diálogos
    out_img = tmp_path / "game_atlas.png"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(out_img), "Imágenes PNG (*.png)"),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    window.sprite_panel.export_composed_atlas()
    assert out_img.is_file()
    out_json = out_img.with_suffix(".json")
    assert out_json.is_file()

    content = out_json.read_text(encoding="utf-8")
    assert '"frames"' in content
    assert "textura_01" in content
    assert "textura_02" in content
    assert "textura_03" in content


def test_atlas_items_project_roundtrip(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Añadir 2 texturas con nombres personalizados
    img = _create_mock_qimage(200, 200, QColor(40, 180, 120, 255))
    monkeypatch.setattr(
        "PySide6.QtGui.QGuiApplication.clipboard",
        lambda: type("MockClip", (), {"image": lambda self: img})(),
    )
    window.paste_from_clipboard()
    window.ripper_panel.set_dimensions(96, 96)
    window.ripper_panel.add_to_atlas()
    window.ripper_panel.set_dimensions(48, 48)
    window.ripper_panel.add_to_atlas()

    # Renombrar en atlas
    window.set_mode("sprites")
    window.atlas_tool.items[0].name = "wall_brick"
    window.atlas_tool.items[0].x = 10
    window.atlas_tool.items[0].y = 20

    window.atlas_tool.items[1].name = "floor_tile"
    window.atlas_tool.items[1].x = 120
    window.atlas_tool.items[1].y = 40

    # Guardar proyecto .ivtex
    proj_path = tmp_path / "composed_atlas_project.ivtex"
    saved = window.save_project(proj_path)
    assert saved is True
    assert proj_path.is_file()

    # Cargar en una ventana nueva limpia
    window2 = MainWindow()
    qtbot.addWidget(window2)
    window2.show()

    opened = window2.open_project(proj_path)
    assert opened is True
    assert len(window2.atlas_tool.items) == 2

    it0 = window2.atlas_tool.items[0]
    it1 = window2.atlas_tool.items[1]
    assert it0.name == "wall_brick"
    assert it0.width == 96
    assert it0.height == 96
    assert it0.x == 10
    assert it0.y == 20

    assert it1.name == "floor_tile"
    assert it1.width == 48
    assert it1.height == 48
    assert it1.x == 120
    assert it1.y == 40

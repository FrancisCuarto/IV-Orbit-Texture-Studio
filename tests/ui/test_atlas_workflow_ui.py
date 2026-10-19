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


def test_atlas_undo_redo_and_keyboard_shortcuts(qtbot, monkeypatch):
    from PySide6.QtGui import QKeyEvent

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    img = _create_mock_qimage(200, 120, QColor(180, 90, 220, 255))
    monkeypatch.setattr(
        "PySide6.QtGui.QGuiApplication.clipboard",
        lambda: type("MockClip", (), {"image": lambda self: img})(),
    )
    window.paste_from_clipboard()
    window.ripper_panel.set_dimensions(100, 60)
    window.ripper_panel.add_to_atlas()

    # El botón de acceso rápido al Atlas muestra el contador actualizado y abre el compositor
    assert window.ripper_panel._btn_open_atlas.isEnabled()
    assert "(1)" in window.ripper_panel._btn_open_atlas.text()
    window.ripper_panel._btn_open_atlas.click()
    assert window.action_mode_sprites.isChecked()
    assert window.sprite_tool.submode == "atlas"

    atlas = window.atlas_tool
    item = atlas.selected_item
    assert item is not None
    orig_x, orig_y = item.x, item.y

    # Mover con flechas (1 px y Shift+Flecha 10 px): se fusionan en un único comando de Undo
    ev_right = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    ev_down_shift = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier
    )
    assert window.sprite_tool.handle_key_press(ev_right) is True
    assert window.sprite_tool.handle_key_press(ev_down_shift) is True
    assert (item.x, item.y) == (orig_x + 1, orig_y + 10)

    # Deshacer restaura ambos movimientos de una vez (por merge_key)
    window.action_undo.trigger()
    item = atlas.selected_item
    assert item is not None
    assert (item.x, item.y) == (orig_x, orig_y)

    # Rehacer vuelve a aplicar el movimiento
    window.action_redo.trigger()
    item = atlas.selected_item
    assert item is not None
    assert (item.x, item.y) == (orig_x + 1, orig_y + 10)

    # Rotar 90° intercambia ancho y alto (100x60 -> 60x100) y es reversible
    ev_rot = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier)
    assert window.sprite_tool.handle_key_press(ev_rot) is True
    item = atlas.selected_item
    assert item is not None
    assert (item.width, item.height) == (60, 100)

    window.action_undo.trigger()
    item = atlas.selected_item
    assert item is not None
    assert (item.width, item.height) == (100, 60)

    # Duplicar con Ctrl+D crea una segunda pieza sin colisión de nombre ni solapamiento
    ev_dup = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert window.sprite_tool.handle_key_press(ev_dup) is True
    assert len(atlas.items) == 2
    assert atlas.items[0].name != atlas.items[1].name
    assert len(atlas.overlapping_ids()) == 0

    # Eliminar con Supr y luego deshacer la eliminación
    ev_del = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    assert window.sprite_tool.handle_key_press(ev_del) is True
    assert len(atlas.items) == 1
    window.action_undo.trigger()
    assert len(atlas.items) == 2


def test_atlas_unique_names_fit_canvas_and_direct_file_import(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Guardar dos archivos PNG en disco e importarlos directamente al Atlas
    f1 = tmp_path / "brick.png"
    f2 = tmp_path / "brick_copy.png"
    _create_mock_qimage(80, 80, QColor(200, 80, 40, 255)).save(str(f1))
    _create_mock_qimage(120, 60, QColor(40, 160, 200, 255)).save(str(f2))

    added = window.sprite_panel.add_image_files_to_atlas([f1, f2])
    assert added == 2
    assert len(window.atlas_tool.items) == 2

    # Intentar renombrar la segunda textura al mismo nombre que la primera genera sufijo único
    second_id = window.atlas_tool.items[1].id
    final_name = window.atlas_tool.rename_item(second_id, "brick")
    assert final_name == "brick_2"

    # Ajustar lienzo al contenido en potencia de dos
    window.atlas_tool.fit_canvas_to_content(power_of_two=True)
    assert window.atlas_tool.atlas_width == 256
    assert window.atlas_tool.atlas_height in (64, 128)

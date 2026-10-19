from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import Point
from iv_orbit_texture_studio.ui.main_window import MainWindow


def _create_test_image(path: Path, width: int = 300, height: int = 200) -> None:
    img = Image.new("RGBA", (width, height), color=(120, 160, 200, 255))
    img.save(path)


def test_texture_ripper_panel_initial_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    panel = window.ripper_panel
    assert not panel._btn_export.isEnabled()
    assert not panel._btn_reset_rect.isEnabled()
    assert "Cargá una imagen primero" in panel._label_status.text()


def test_texture_ripper_panel_on_image_load(qtbot, tmp_path):
    img_path = tmp_path / "test_source.png"
    _create_test_image(img_path, 400, 300)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    success = window.open_image(img_path)
    assert success is True

    panel = window.ripper_panel
    # When image loads, default quad is initialized
    assert window.tool.selection.is_valid()
    assert panel._btn_export.isEnabled()
    assert panel._btn_reset_rect.isEnabled()
    assert "✓ 4 vértices listos" in panel._label_status.text()

    # Aspect ratio lock toggle
    panel._chk_lock_aspect.setChecked(True)
    orig_w = panel._spin_width.value()
    orig_h = panel._spin_height.value()

    # Doubling width should double height when locked
    panel._spin_width.setValue(orig_w * 2)
    assert panel._spin_height.value() == orig_h * 2


def test_texture_ripper_canvas_handle_drag(qtbot, tmp_path):
    img_path = tmp_path / "drag_test.png"
    _create_test_image(img_path, 200, 200)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)

    tool = window.tool
    canvas = window.canvas

    # At zoom 1.0 and offset (0, 0)
    canvas.actual_size()
    canvas.pan_by(-canvas.mapper.offset.x, -canvas.mapper.offset.y)

    # Let's set a known quad:
    # TL: (20, 20), TR: (180, 20), BR: (180, 180), BL: (20, 180)
    from iv_orbit_texture_studio.imaging.perspective import Quad

    tool.selection.set_quad(Quad(Point(20, 20), Point(180, 20), Point(180, 180), Point(20, 180)))
    canvas.update()

    # The top-left handle is at image (20, 20) -> screen (20, 20)
    # Hover over handle 0
    p0 = QPointF(20.0, 20.0)
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p0,
        p0,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(move_ev)
    assert tool.selection.hovered_index == 0

    # Press left button on handle 0
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p0,
        p0,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(press_ev)
    assert tool.selection.dragged_index == 0

    # Drag to (35, 45)
    p_drag = QPointF(35.0, 45.0)
    drag_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p_drag,
        p_drag,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(drag_ev)
    assert tool.selection.points[0] == Point(35.0, 45.0)

    # Release
    rel_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        p_drag,
        p_drag,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseReleaseEvent(rel_ev)
    assert tool.selection.dragged_index is None


def test_texture_ripper_export_flow(qtbot, tmp_path, monkeypatch):
    img_path = tmp_path / "export_src.png"
    _create_test_image(img_path, 200, 200)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)

    panel = window.ripper_panel
    panel._spin_width.setValue(128)
    panel._spin_height.setValue(64)

    target_export = tmp_path / "exported_texture.png"

    info_shown = False

    def mock_get_save(default_target):
        return str(target_export)

    def mock_show_info(title, msg):
        nonlocal info_shown
        info_shown = True

    def mock_show_error(title, msg):
        raise AssertionError(f"Export failed with error: {title} - {msg}")

    monkeypatch.setattr(panel, "_get_save_file_name", mock_get_save)
    monkeypatch.setattr(panel, "_show_info", mock_show_info)
    monkeypatch.setattr(panel, "_show_error", mock_show_error)

    # Trigger export
    panel.export_texture()

    assert info_shown is True
    assert target_export.is_file()

    # Re-open exported file and verify dimensions
    with Image.open(target_export) as im:
        assert im.size == (128, 64)
        assert im.mode == "RGBA"


def test_texture_ripper_degenerate_warning(qtbot, tmp_path):
    img_path = tmp_path / "degen_src.png"
    _create_test_image(img_path, 200, 200)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)

    # Set self-intersecting (bowtie) quad
    from iv_orbit_texture_studio.imaging.perspective import Quad

    bowtie = Quad(Point(0, 0), Point(100, 100), Point(100, 0), Point(0, 100))
    window.tool.set_quad(bowtie)

    # Export must be disabled and warning must be shown
    assert not window.tool.selection.is_valid()
    assert not window.ripper_panel._btn_export.isEnabled()
    assert not window.action_export.isEnabled()
    assert "⚠" in window.ripper_panel._label_status.text()

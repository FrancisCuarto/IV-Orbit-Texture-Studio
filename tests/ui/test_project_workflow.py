from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from iv_orbit_texture_studio.imaging.perspective import InterpolationMode, Point, Quad
from iv_orbit_texture_studio.ui.main_window import MainWindow


def _create_test_image(path: Path, width: int = 200, height: int = 150) -> None:
    img = Image.new("RGBA", (width, height), color=(100, 200, 150, 255))
    img.save(path)


def test_main_window_project_save_and_load(qtbot, tmp_path):
    img_path = tmp_path / "src_texture.png"
    _create_test_image(img_path, 200, 150)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # 1. Open image
    assert window.open_image(img_path) is True
    assert window.undo_stack.isClean()
    assert "*" not in window.windowTitle()

    # 2. Modify quad (adjust to corners)
    window.tool.select_image_corners()
    assert not window.undo_stack.isClean()
    assert "*" in window.windowTitle()

    # 3. Modify dimensions and sampling
    window.ripper_panel.set_dimensions(1024, 768)
    window.ripper_panel.set_interpolation_mode(InterpolationMode.NEAREST)

    # 4. Save project to .ivtex
    proj_path = tmp_path / "saved_workflow.ivtex"
    success = window.save_project(proj_path)
    assert success is True
    assert proj_path.is_file()
    assert window.undo_stack.isClean()
    assert "*" not in window.windowTitle()

    # 5. Open a clean second window and load the saved project
    window2 = MainWindow()
    qtbot.addWidget(window2)
    window2.show()

    assert window2.open_project(proj_path) is True
    assert window2.canvas.has_image
    assert window2.current_image.width == 200
    assert window2.current_image.height == 150

    # Verify quad restored to corners
    assert window2.tool.selection.points[0] == Point(0.0, 0.0)
    assert window2.tool.selection.points[1] == Point(200.0, 0.0)
    assert window2.tool.selection.points[2] == Point(200.0, 150.0)
    assert window2.tool.selection.points[3] == Point(0.0, 150.0)

    # Verify output dimensions and sampling restored
    assert window2.ripper_panel.output_width == 1024
    assert window2.ripper_panel.output_height == 768
    assert window2.ripper_panel.interpolation_mode == InterpolationMode.NEAREST
    assert window2.undo_stack.isClean()


def test_main_window_undo_redo_vertex_drag(qtbot, tmp_path):
    img_path = tmp_path / "undo_test.png"
    _create_test_image(img_path, 200, 200)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)

    # Known quad
    orig_quad = Quad(Point(20, 20), Point(180, 20), Point(180, 180), Point(20, 180))
    window.tool.set_quad(orig_quad)
    window.undo_stack.clear()

    window.canvas.actual_size()
    window.canvas.pan_by(-window.canvas.mapper.offset.x, -window.canvas.mapper.offset.y)

    # 1. Drag vertex 0 from (20, 20) to (50, 60)
    p0 = QPointF(20.0, 20.0)
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p0,
        p0,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.canvas.mousePressEvent(press_ev)

    p_dest = QPointF(50.0, 60.0)
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p_dest,
        p_dest,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.canvas.mouseMoveEvent(move_ev)

    rel_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        p_dest,
        p_dest,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.canvas.mouseReleaseEvent(rel_ev)

    assert window.tool.selection.points[0] == Point(50.0, 60.0)
    assert not window.undo_stack.isClean()
    assert window.undo_stack.canUndo()

    # 2. Undo
    window.action_undo.trigger()
    assert window.tool.selection.points[0] == Point(20.0, 20.0)
    assert window.undo_stack.canRedo()

    # 3. Redo
    window.action_redo.trigger()
    assert window.tool.selection.points[0] == Point(50.0, 60.0)


def test_main_window_new_project_reset(qtbot, tmp_path):
    img_path = tmp_path / "reset_test.png"
    _create_test_image(img_path, 200, 200)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_image(img_path)
    assert window.canvas.has_image

    # New project resets workspace
    assert window.new_project() is True
    assert not window.canvas.has_image
    assert window.current_image is None
    assert window.tool.selection.count == 0
    assert window.undo_stack.isClean()

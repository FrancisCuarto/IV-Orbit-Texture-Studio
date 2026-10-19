from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QWheelEvent

from iv_orbit_texture_studio.ui.canvas.image_canvas import ImageCanvas


def _make_test_qimage(w=100, h=80):
    img = QImage(w, h, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.blue)
    return img


def test_canvas_set_and_clear_image(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()

    assert not canvas.has_image
    img = _make_test_qimage(200, 100)
    canvas.set_image(img)

    assert canvas.has_image
    assert canvas.image_size.width == 200.0
    assert canvas.image_size.height == 100.0
    assert canvas.fit_mode is True

    canvas.clear_image()
    assert not canvas.has_image
    assert canvas.image_size is None


def test_canvas_cursor_tracking(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.show()

    img = _make_test_qimage(100, 100)
    canvas.set_image(img)

    # Put zoom at 1.0 and offset at 0,0
    canvas.mapper.reset()

    coords_received = []

    def on_cursor(x, y, inside):
        coords_received.append((x, y, inside))

    canvas.cursor_moved.connect(on_cursor)

    # Move mouse inside image bounds (e.g. at screen 50, 50 -> image 50, 50)
    pos = QPointF(50.0, 50.0)
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos,
        pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(event)

    assert len(coords_received) == 1
    assert coords_received[0] == (50.0, 50.0, True)

    # Move mouse outside image bounds
    pos_out = QPointF(150.0, 50.0)
    event_out = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos_out,
        pos_out,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(event_out)

    assert len(coords_received) == 2
    assert coords_received[1][2] is False  # inside is False


def test_canvas_pan_interaction(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.show()

    img = _make_test_qimage(100, 100)
    canvas.set_image(img)
    initial_offset = canvas.mapper.offset

    # Press middle button to pan
    p1 = QPointF(100.0, 100.0)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p1,
        p1,
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(press_event)

    # Drag to 150, 120 (delta dx=50, dy=20)
    p2 = QPointF(150.0, 120.0)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p2,
        p2,
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(move_event)

    # Release
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        p2,
        p2,
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseReleaseEvent(release_event)

    assert canvas.mapper.offset.x == initial_offset.x + 50.0
    assert canvas.mapper.offset.y == initial_offset.y + 20.0
    assert canvas.fit_mode is False


def test_canvas_wheel_zoom(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.show()

    img = _make_test_qimage(100, 100)
    canvas.set_image(img)
    old_zoom = canvas.mapper.zoom

    # Zoom in wheel event (120 angle delta y)
    from PySide6.QtCore import QPoint

    wheel_event = QWheelEvent(
        QPointF(200.0, 200.0),
        QPointF(200.0, 200.0),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    canvas.wheelEvent(wheel_event)
    assert canvas.mapper.zoom > old_zoom


def test_canvas_left_click_pan(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.show()

    img = _make_test_qimage(100, 100)
    canvas.set_image(img)
    initial_offset = canvas.mapper.offset

    # Left-click on canvas
    p1 = QPointF(250.0, 250.0)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p1,
        p1,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(press_event)

    # Drag left-click by dx=-30, dy=40
    p2 = QPointF(220.0, 290.0)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p2,
        p2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(move_event)

    # Release
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        p2,
        p2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseReleaseEvent(release_event)

    assert canvas.mapper.offset.x == initial_offset.x - 30.0
    assert canvas.mapper.offset.y == initial_offset.y + 40.0

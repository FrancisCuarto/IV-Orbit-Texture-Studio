from PySide6.QtGui import QUndoStack

from iv_orbit_texture_studio.core.commands import (
    ChangeDimensionsCommand,
    ChangeInterpolationCommand,
    MoveVertexCommand,
    SetQuadCommand,
)
from iv_orbit_texture_studio.imaging.perspective import InterpolationMode, Point, Quad
from iv_orbit_texture_studio.tools.texture_ripper.selection import SelectionModel


def test_move_vertex_command():
    selection = SelectionModel()
    quad = Quad(Point(10, 10), Point(90, 10), Point(90, 90), Point(10, 90))
    selection.set_quad(quad)

    callback_called = 0

    def on_change(idx, pt):
        nonlocal callback_called
        callback_called += 1
        selection.move_vertex(idx, pt)

    stack = QUndoStack()
    cmd = MoveVertexCommand(0, Point(10, 10), Point(25, 30), on_change)
    stack.push(cmd)

    # Push executes redo()
    assert callback_called == 1
    assert selection.points[0] == Point(25, 30)

    # Undo
    stack.undo()
    assert callback_called == 2
    assert selection.points[0] == Point(10, 10)

    # Redo
    stack.redo()
    assert callback_called == 3
    assert selection.points[0] == Point(25, 30)


def test_set_quad_command():
    quad1 = Quad(Point(10, 10), Point(90, 10), Point(90, 90), Point(10, 90))
    quad2 = Quad(Point(0, 0), Point(100, 0), Point(100, 100), Point(0, 100))

    current_quad: Quad | None = quad1

    def apply_quad(q):
        nonlocal current_quad
        current_quad = q

    stack = QUndoStack()
    cmd = SetQuadCommand(quad1, quad2, apply_quad, text="Ajustar a esquinas")
    stack.push(cmd)

    assert current_quad == quad2

    stack.undo()
    assert current_quad == quad1

    stack.redo()
    assert current_quad == quad2


def test_change_dimensions_command():
    dims = (512, 512)

    def apply_dims(w, h):
        nonlocal dims
        dims = (w, h)

    stack = QUndoStack()
    cmd = ChangeDimensionsCommand((512, 512), (1024, 768), apply_dims)
    stack.push(cmd)

    assert dims == (1024, 768)

    stack.undo()
    assert dims == (512, 512)

    stack.redo()
    assert dims == (1024, 768)


def test_change_interpolation_command():
    mode = InterpolationMode.LANCZOS4

    def apply_interp(m):
        nonlocal mode
        mode = m

    stack = QUndoStack()
    cmd = ChangeInterpolationCommand(
        InterpolationMode.LANCZOS4, InterpolationMode.NEAREST, apply_interp
    )
    stack.push(cmd)

    assert mode == InterpolationMode.NEAREST

    stack.undo()
    assert mode == InterpolationMode.LANCZOS4

    stack.redo()
    assert mode == InterpolationMode.NEAREST

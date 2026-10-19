from PIL import Image

from iv_orbit_texture_studio.ui.main_window import MainWindow


def test_main_window_initial_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert not window.canvas.has_image
    assert not window.action_zoom_in.isEnabled()
    assert not window.action_zoom_out.isEnabled()
    assert not window.action_fit.isEnabled()
    assert not window.action_actual_size.isEnabled()
    assert not window.action_center.isEnabled()
    assert window._label_file.text() == "Sin imagen"


def test_main_window_open_image(qtbot, tmp_path):
    img_path = tmp_path / "sample.png"
    pil_img = Image.new("RGBA", (200, 100), color=(100, 150, 200, 255))
    pil_img.save(img_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    success = window.open_image(img_path)
    assert success is True
    assert window.canvas.has_image
    assert window.current_image is not None
    assert window.current_image.width == 200
    assert window.current_image.height == 100

    # Actions must now be enabled
    assert window.action_zoom_in.isEnabled()
    assert window.action_zoom_out.isEnabled()
    assert window.action_fit.isEnabled()
    assert window.action_actual_size.isEnabled()
    assert window.action_center.isEnabled()

    # Title and status bar
    assert "sample.png" in window.windowTitle()
    assert window._label_file.text() == "sample.png"
    assert "200 × 100 px" in window._label_size.text()

    # Test zoom actions
    init_zoom = window.canvas.mapper.zoom
    window.action_zoom_in.trigger()
    assert window.canvas.mapper.zoom > init_zoom

    window.action_actual_size.trigger()
    assert window.canvas.mapper.zoom == 1.0

    window.action_zoom_out.trigger()
    assert window.canvas.mapper.zoom < 1.0

    window.action_fit.trigger()
    assert window.canvas.fit_mode is True


def test_main_window_open_invalid_image(qtbot, tmp_path, monkeypatch):
    bad_file = tmp_path / "bad.png"
    bad_file.write_bytes(b"corrupt")

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Prevent QMessageBox modal from blocking test execution
    dialog_shown = False

    def mock_show_error(title, message):
        nonlocal dialog_shown
        dialog_shown = True

    monkeypatch.setattr(window, "_show_error", mock_show_error)

    success = window.open_image(bad_file)
    assert success is False
    assert dialog_shown is True
    assert not window.canvas.has_image

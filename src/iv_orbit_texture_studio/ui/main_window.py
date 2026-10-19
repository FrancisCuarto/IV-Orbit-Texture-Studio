"""Ventana principal de la aplicación."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import QFileDialog, QLabel, QMainWindow, QMessageBox, QWidget

from iv_orbit_texture_studio.imaging.image_io import (
    ImageLoadError,
    LoadedImage,
    load_image,
    open_dialog_filter,
)
from iv_orbit_texture_studio.ui.canvas.image_canvas import ImageCanvas
from iv_orbit_texture_studio.ui.qt_image import rgba_array_to_qimage

logger = logging.getLogger(__name__)

APP_TITLE = "IV Orbit Texture Studio"


class MainWindow(QMainWindow):
    """Ventana principal: menú, barra de herramientas, lienzo y barra de estado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_image: LoadedImage | None = None
        self._last_directory: Path | None = None

        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self.canvas = ImageCanvas(self)
        self.setCentralWidget(self.canvas)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()
        self._connect_canvas()
        self._update_actions()

    # ---------------------------------------------------------------- acciones
    def _create_actions(self) -> None:
        self.action_open = QAction(self.tr("&Abrir imagen…"), self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.open_image_dialog)

        self.action_quit = QAction(self.tr("&Salir"), self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(self.close)

        self.action_zoom_in = QAction(self.tr("A&cercar"), self)
        self.action_zoom_in.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        self.action_zoom_in.triggered.connect(self.canvas.zoom_in)

        self.action_zoom_out = QAction(self.tr("A&lejar"), self)
        self.action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.action_zoom_out.triggered.connect(self.canvas.zoom_out)

        self.action_fit = QAction(self.tr("&Ajustar a la ventana"), self)
        self.action_fit.setShortcut(QKeySequence("Ctrl+0"))
        self.action_fit.triggered.connect(self.canvas.fit_to_view)

        self.action_actual_size = QAction(self.tr("&Tamaño real (100 %)"), self)
        self.action_actual_size.setShortcut(QKeySequence("Ctrl+1"))
        self.action_actual_size.triggered.connect(self.canvas.actual_size)

        self.action_center = QAction(self.tr("C&entrar imagen"), self)
        self.action_center.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.action_center.triggered.connect(self.canvas.center_image)

        self._view_actions = (
            self.action_zoom_in,
            self.action_zoom_out,
            self.action_fit,
            self.action_actual_size,
            self.action_center,
        )

    def _create_menus(self) -> None:
        menu_file = self.menuBar().addMenu(self.tr("&Archivo"))
        menu_file.addAction(self.action_open)
        menu_file.addSeparator()
        menu_file.addAction(self.action_quit)

        menu_view = self.menuBar().addMenu(self.tr("&Ver"))
        for action in self._view_actions:
            menu_view.addAction(action)

    def _create_toolbar(self) -> None:
        toolbar = self.addToolBar(self.tr("Principal"))
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.action_open)
        toolbar.addSeparator()
        for action in self._view_actions:
            toolbar.addAction(action)

    def _create_status_bar(self) -> None:
        self._label_file = QLabel()
        self._label_size = QLabel()
        self._label_zoom = QLabel()
        self._label_cursor = QLabel()
        for label in (self._label_size, self._label_zoom, self._label_cursor):
            label.setMinimumWidth(110)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status = self.statusBar()
        status.addWidget(self._label_file, 1)
        status.addPermanentWidget(self._label_cursor)
        status.addPermanentWidget(self._label_size)
        status.addPermanentWidget(self._label_zoom)
        self._refresh_status()

    def _connect_canvas(self) -> None:
        self.canvas.view_changed.connect(self._on_view_changed)
        self.canvas.cursor_moved.connect(self._on_cursor_moved)
        self.canvas.cursor_left.connect(self._on_cursor_left)

    def _update_actions(self) -> None:
        has_image = self.canvas.has_image
        for action in self._view_actions:
            action.setEnabled(has_image)

    # ---------------------------------------------------------------- apertura
    def open_image_dialog(self) -> None:
        start_dir = str(self._last_directory) if self._last_directory else ""
        filter_text = self.tr("Imágenes ({patterns});;Todos los archivos (*)").format(
            patterns=open_dialog_filter()
        )
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Abrir imagen"), start_dir, filter_text)
        if path:
            self.open_image(Path(path))

    def open_image(self, path: Path) -> bool:
        """Carga ``path`` y la muestra. Devuelve ``True`` si tuvo éxito."""
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            loaded = load_image(path)
            qimage = rgba_array_to_qimage(loaded.pixels)
        except ImageLoadError as exc:
            QGuiApplication.restoreOverrideCursor()
            logger.warning("No se pudo abrir la imagen %s: %s", exc.path.name, exc)
            self._show_error(self.tr("No se pudo abrir la imagen"), str(exc))
            return False
        except MemoryError:
            QGuiApplication.restoreOverrideCursor()
            logger.exception("Memoria insuficiente al abrir %s", path.name)
            self._show_error(
                self.tr("No se pudo abrir la imagen"),
                self.tr("Memoria insuficiente para cargar esta imagen."),
            )
            return False
        QGuiApplication.restoreOverrideCursor()

        self._current_image = loaded
        self._last_directory = path.parent
        self.canvas.set_image(qimage)
        self.setWindowTitle(f"{path.name} — {APP_TITLE}")
        self._update_actions()
        self._refresh_status()
        self.statusBar().showMessage(self.tr("Imagen abierta: {name}").format(name=path.name), 4000)
        return True

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    # -------------------------------------------------------------- estado
    @property
    def current_image(self) -> LoadedImage | None:
        return self._current_image

    def _refresh_status(self) -> None:
        image = self._current_image
        if image is None:
            self._label_file.setText(self.tr("Sin imagen"))
            self._label_size.setText("—")
        else:
            self._label_file.setText(image.path.name)
            self._label_size.setText(f"{image.width} × {image.height} px")
        self._on_view_changed(self.canvas.mapper.zoom)

    def _on_view_changed(self, zoom: float) -> None:
        if self.canvas.has_image:
            self._label_zoom.setText(f"{zoom * 100:.1f} %")
        else:
            self._label_zoom.setText("—")

    def _on_cursor_moved(self, x: float, y: float, inside: bool) -> None:
        if inside:
            self._label_cursor.setText(f"x {int(x)}, y {int(y)}")
        else:
            self._label_cursor.setText("—")

    def _on_cursor_left(self) -> None:
        self._label_cursor.setText("—")

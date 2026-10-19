"""Ventana principal de la aplicación."""

from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QGuiApplication,
    QKeySequence,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from iv_orbit_texture_studio.core.commands import MoveVertexCommand, SetQuadCommand
from iv_orbit_texture_studio.core.document import Document, SourceImageInfo
from iv_orbit_texture_studio.imaging.image_io import (
    ImageLoadError,
    LoadedImage,
    load_image,
    load_image_from_bytes,
    open_dialog_filter,
)
from iv_orbit_texture_studio.imaging.perspective import Point, Quad
from iv_orbit_texture_studio.project_io import (
    CorruptProjectError,
    MissingSourceImageError,
    ProjectIOError,
    UnsupportedVersionError,
    ZipSlipSecurityError,
    load_project,
    save_project,
)
from iv_orbit_texture_studio.tools.sprites import SpritePanel, SpriteTool
from iv_orbit_texture_studio.tools.texture_ripper.preview import TextureRipperPanel
from iv_orbit_texture_studio.tools.texture_ripper.tool import TextureRipperTool
from iv_orbit_texture_studio.ui.canvas.image_canvas import ImageCanvas
from iv_orbit_texture_studio.ui.qt_image import rgba_array_to_qimage

logger = logging.getLogger(__name__)

APP_TITLE = "IV Orbit Texture Studio"
PROJECT_FILE_FILTER = "Proyectos IV Orbit (*.ivtex);;Todos los archivos (*)"


class MainWindow(QMainWindow):
    """Ventana principal: menú, barra de herramientas, lienzo, historial y barra de estado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_image: LoadedImage | None = None
        self._last_directory: Path | None = None
        self._document: Document = Document()
        self.undo_stack: QUndoStack = QUndoStack(self)
        self.prompt_on_close: bool = "PYTEST_CURRENT_TEST" not in os.environ

        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self.canvas = ImageCanvas(self)
        self.setCentralWidget(self.canvas)

        # Herramienta Texture Ripper y panel de control
        self.tool = TextureRipperTool(self)
        self.canvas.set_tool(self.tool)

        self.ripper_panel = TextureRipperPanel(self.tool, self)
        self.dock_panel = QDockWidget(self.tr("Texture Ripper"), self)
        self.dock_panel.setObjectName("dock_texture_ripper")
        self.dock_panel.setWidget(self.ripper_panel)
        self.dock_panel.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_panel)

        # Herramienta Sprites y Atlas
        self.sprite_tool = SpriteTool(self)
        self.sprite_panel = SpritePanel(self.sprite_tool, self)
        self.dock_sprites = QDockWidget(self.tr("Sprites y Atlas"), self)
        self.dock_sprites.setObjectName("dock_sprites_atlas")
        self.dock_sprites.setWidget(self.sprite_panel)
        self.dock_sprites.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_sprites)
        self.tabifyDockWidget(self.dock_panel, self.dock_sprites)
        self.dock_panel.raise_()

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()
        self._connect_signals()
        self._update_actions()
        self._update_window_title()

    # ---------------------------------------------------------------- acciones
    def _create_actions(self) -> None:
        # Archivo
        self.action_new_project = QAction(self.tr("&Nuevo proyecto"), self)
        self.action_new_project.setShortcut(QKeySequence.StandardKey.New)
        self.action_new_project.triggered.connect(self.new_project)

        self.action_open = QAction(self.tr("&Abrir imagen…"), self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.open_image_dialog)

        self.action_open_project = QAction(self.tr("Abrir &proyecto…"), self)
        self.action_open_project.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.action_open_project.triggered.connect(self.open_project_dialog)

        self.action_save_project = QAction(self.tr("&Guardar proyecto"), self)
        self.action_save_project.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save_project.triggered.connect(self.save_project_dialog)

        self.action_save_project_as = QAction(self.tr("Guardar proyecto &como…"), self)
        self.action_save_project_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_project_as.triggered.connect(self.save_project_as_dialog)

        self.action_export = QAction(self.tr("&Exportar textura rectificada…"), self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export.triggered.connect(self.ripper_panel.export_texture)

        self.action_export_atlas = QAction(self.tr("Exportar &atlas de sprites…"), self)
        self.action_export_atlas.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.action_export_atlas.triggered.connect(self.sprite_panel.export_atlas)

        self.action_quit = QAction(self.tr("&Salir"), self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(self.close)

        # Modos de trabajo
        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)

        self.action_mode_ripper = QAction(self.tr("Modo &Texture Ripper"), self)
        self.action_mode_ripper.setCheckable(True)
        self.action_mode_ripper.setChecked(True)
        self.action_mode_ripper.triggered.connect(lambda: self.set_mode("ripper"))
        self.mode_group.addAction(self.action_mode_ripper)

        self.action_mode_sprites = QAction(self.tr("Modo &Sprites y Atlas"), self)
        self.action_mode_sprites.setCheckable(True)
        self.action_mode_sprites.setChecked(False)
        self.action_mode_sprites.triggered.connect(lambda: self.set_mode("sprites"))
        self.mode_group.addAction(self.action_mode_sprites)

        # Operaciones de sprites
        self.action_detect_sprites = QAction(self.tr("&Detectar sprites automáticamente"), self)
        self.action_detect_sprites.triggered.connect(self.sprite_panel.detect_sprites)

        self.action_pack_atlas = QAction(self.tr("&Generar atlas"), self)
        self.action_pack_atlas.triggered.connect(self.sprite_panel.generate_atlas)

        # Edición / Historial
        self.action_undo = self.undo_stack.createUndoAction(self, self.tr("&Deshacer"))
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)

        self.action_redo = self.undo_stack.createRedoAction(self, self.tr("&Rehacer"))
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)

        self.action_corners = QAction(self.tr("Ajustar selección a las &esquinas"), self)
        self.action_corners.triggered.connect(self.tool.select_image_corners)

        self.action_reset_sel = QAction(self.tr("&Restablecer selección inicial"), self)
        self.action_reset_sel.triggered.connect(self.tool.reset_to_default)

        self.action_clear_sel = QAction(self.tr("&Limpiar selección"), self)
        self.action_clear_sel.triggered.connect(self.tool.clear)

        # Ver / Navegación
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
        menu_file.addAction(self.action_new_project)
        menu_file.addSeparator()
        menu_file.addAction(self.action_open)
        menu_file.addAction(self.action_open_project)
        menu_file.addSeparator()
        menu_file.addAction(self.action_save_project)
        menu_file.addAction(self.action_save_project_as)
        menu_file.addSeparator()
        menu_file.addAction(self.action_export)
        menu_file.addAction(self.action_export_atlas)
        menu_file.addSeparator()
        menu_file.addAction(self.action_quit)

        menu_edit = self.menuBar().addMenu(self.tr("&Editar"))
        menu_edit.addAction(self.action_undo)
        menu_edit.addAction(self.action_redo)
        menu_edit.addSeparator()
        menu_edit.addAction(self.action_corners)
        menu_edit.addAction(self.action_reset_sel)
        menu_edit.addAction(self.action_clear_sel)

        menu_tools = self.menuBar().addMenu(self.tr("&Herramientas"))
        menu_tools.addAction(self.action_mode_ripper)
        menu_tools.addAction(self.action_mode_sprites)
        menu_tools.addSeparator()
        menu_tools.addAction(self.action_detect_sprites)
        menu_tools.addAction(self.action_pack_atlas)

        menu_view = self.menuBar().addMenu(self.tr("&Ver"))
        for action in self._view_actions:
            menu_view.addAction(action)

        menu_window = self.menuBar().addMenu(self.tr("&Ventana"))
        menu_window.addAction(self.dock_panel.toggleViewAction())
        menu_window.addAction(self.dock_sprites.toggleViewAction())

    def _create_toolbar(self) -> None:
        toolbar = self.addToolBar(self.tr("Principal"))
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.action_new_project)
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_open_project)
        toolbar.addAction(self.action_save_project)
        toolbar.addSeparator()
        toolbar.addAction(self.action_undo)
        toolbar.addAction(self.action_redo)
        toolbar.addSeparator()
        toolbar.addAction(self.action_export)
        toolbar.addAction(self.action_export_atlas)
        toolbar.addSeparator()
        toolbar.addAction(self.action_mode_ripper)
        toolbar.addAction(self.action_mode_sprites)
        toolbar.addSeparator()
        for action in self._view_actions:
            toolbar.addAction(action)

    def set_mode(self, mode: str) -> None:
        """Cambia el modo activo entre Texture Ripper y Sprites."""
        if mode == "ripper":
            self.canvas.set_tool(self.tool)
            self.dock_panel.show()
            self.dock_panel.raise_()
            self.action_mode_ripper.setChecked(True)
            self.action_mode_sprites.setChecked(False)
        elif mode == "sprites":
            self.canvas.set_tool(self.sprite_tool)
            self.dock_sprites.show()
            self.dock_sprites.raise_()
            self.action_mode_ripper.setChecked(False)
            self.action_mode_sprites.setChecked(True)
        self._update_actions()

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

    def _connect_signals(self) -> None:
        self.canvas.view_changed.connect(self._on_view_changed)
        self.canvas.cursor_moved.connect(self._on_cursor_moved)
        self.canvas.cursor_left.connect(self._on_cursor_left)
        self.tool.selection_changed.connect(self._update_actions)
        self.tool.vertex_drag_finished.connect(self._on_vertex_drag_finished)
        self.tool.quad_changed_by_user.connect(self._on_quad_changed_by_user)
        self.undo_stack.cleanChanged.connect(self._on_clean_changed)
        self.ripper_panel.export_requested.connect(self._on_export_finished)
        self.sprite_tool.sprites_changed.connect(self._on_sprites_changed)
        self.sprite_panel.atlas_exported.connect(self._on_atlas_exported)

    def _on_export_finished(self, path: Path) -> None:
        self.statusBar().showMessage(
            self.tr("Textura exportada en: {name}").format(name=path.name), 6000
        )

    def _on_sprites_changed(self) -> None:
        self._update_actions()
        if self.canvas.has_image:
            self._document.touch_modified()
            self._update_window_title()

    def _on_atlas_exported(self, image_path: Path, json_path: Path) -> None:
        self.statusBar().showMessage(
            self.tr("Atlas exportado: {img} y {json}").format(
                img=image_path.name, json=json_path.name
            ),
            6000,
        )

    def _update_actions(self) -> None:
        has_image = self.canvas.has_image
        self.action_save_project.setEnabled(has_image)
        self.action_save_project_as.setEnabled(has_image)
        self.action_export.setEnabled(has_image and self.tool.selection.is_valid())
        self.action_corners.setEnabled(has_image)
        self.action_reset_sel.setEnabled(has_image)
        self.action_clear_sel.setEnabled(has_image and self.tool.selection.count > 0)
        self.action_detect_sprites.setEnabled(has_image)
        has_sprites = len(self.sprite_tool.sprites) > 0
        self.action_pack_atlas.setEnabled(has_image and has_sprites)
        self.action_export_atlas.setEnabled(has_image and has_sprites)
        for action in self._view_actions:
            action.setEnabled(has_image)

    def _update_window_title(self) -> None:
        proj_name = self._document.project_name
        dirty = "*" if (not self.undo_stack.isClean() or self._document.is_modified) else ""
        self.setWindowTitle(f"{proj_name}{dirty} — {APP_TITLE}")

    def _on_clean_changed(self, is_clean: bool) -> None:
        self._update_window_title()

    # -------------------------------------------------------- slots de historial
    def _on_vertex_drag_finished(self, idx: int, old_pt: Point, new_pt: Point) -> None:
        def apply_pt(i: int, p: Point) -> None:
            self.tool.selection.move_vertex(i, p)
            self.tool.selection_changed.emit()
            self.canvas.update()

        cmd = MoveVertexCommand(idx, old_pt, new_pt, apply_pt)
        self.undo_stack.push(cmd)

    def _on_quad_changed_by_user(
        self, old_quad: Quad | None, new_quad: Quad | None, text: str
    ) -> None:
        def apply_quad(q: Quad | None) -> None:
            if q is None:
                self.tool.selection.clear()
            else:
                self.tool.selection.set_quad(q)
            self.tool.selection_changed.emit()
            self.canvas.update()

        cmd = SetQuadCommand(old_quad, new_quad, apply_quad, text=text)
        self.undo_stack.push(cmd)

    # ------------------------------------------------------------- ciclo de vida
    def maybe_save_changes(self) -> bool:
        """Verifica si hay cambios pendientes y solicita confirmación al usuario."""
        if not self.prompt_on_close or not self.canvas.has_image:
            return True
        if self.undo_stack.isClean() and not self._document.is_modified:
            return True

        reply = QMessageBox.question(
            self,
            self.tr("Guardar cambios"),
            self.tr(
                "El proyecto tiene cambios no guardados.\n¿Deseás guardarlos antes de continuar?"
            ),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if reply == QMessageBox.StandardButton.Save:
            return self.save_project_dialog()
        return reply == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (API de Qt)
        if self.maybe_save_changes():
            event.accept()
        else:
            event.ignore()

    def new_project(self) -> bool:
        """Inicia un nuevo proyecto en blanco tras confirmar cambios pendientes."""
        if not self.maybe_save_changes():
            return False

        self._current_image = None
        self._document = Document()
        self.canvas.clear_image()
        self.tool.selection.clear()
        self.tool.selection_changed.emit()
        self.sprite_tool.clear()
        self.undo_stack.clear()
        self.ripper_panel.set_source_image(None)
        self.sprite_panel.set_source_image(None)
        self._update_window_title()
        self._update_actions()
        self._refresh_status()
        self.statusBar().showMessage(self.tr("Nuevo proyecto iniciado"), 3000)
        return True

    # ----------------------------------------------------------- carga de imagen
    def open_image_dialog(self) -> None:
        if not self.maybe_save_changes():
            return

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
        self._document = Document(
            project_name=path.name,
            source=SourceImageInfo(file_path=str(path)),
        )
        self.undo_stack.clear()
        self.sprite_tool.clear()

        self.canvas.set_image(qimage)
        self.ripper_panel.set_source_image(loaded)
        self.sprite_panel.set_source_image(loaded)
        self._update_window_title()
        self._update_actions()
        self._refresh_status()
        self.statusBar().showMessage(self.tr("Imagen abierta: {name}").format(name=path.name), 4000)
        return True

    # ------------------------------------------------------- gestión de proyectos
    def open_project_dialog(self) -> None:
        if not self.maybe_save_changes():
            return

        start_dir = str(self._last_directory) if self._last_directory else ""
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Abrir proyecto"), start_dir, PROJECT_FILE_FILTER
        )
        if path:
            self.open_project(Path(path))

    def open_project(self, path: Path) -> bool:
        """Abre un proyecto .ivtex y restaura todo el estado de trabajo."""
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            doc, image_bytes = load_project(path)
            if image_bytes is None:
                raise CorruptProjectError("El archivo no contiene datos de imagen válidos.")

            loaded = load_image_from_bytes(
                image_bytes,
                virtual_path=doc.source.asset_filename or path.name,
            )
            qimage = rgba_array_to_qimage(loaded.pixels)
        except (
            CorruptProjectError,
            ZipSlipSecurityError,
            UnsupportedVersionError,
            MissingSourceImageError,
            ProjectIOError,
            ImageLoadError,
        ) as exc:
            QGuiApplication.restoreOverrideCursor()
            logger.warning("Error al abrir proyecto %s: %s", path.name, exc)
            self._show_error(self.tr("Error al abrir proyecto"), str(exc))
            return False
        except Exception as exc:
            QGuiApplication.restoreOverrideCursor()
            logger.exception("Error inesperado al abrir proyecto %s: %s", path.name, exc)
            self._show_error(self.tr("Error inesperado"), str(exc))
            return False
        finally:
            QGuiApplication.restoreOverrideCursor()

        self._document = doc
        self._current_image = loaded
        self._last_directory = path.parent
        self.undo_stack.clear()

        # Restaurar vista e imagen
        self.canvas.set_image(qimage)
        self.ripper_panel.set_source_image(loaded)
        self.sprite_panel.set_source_image(loaded)

        # Restaurar parámetros de Texture Ripper
        self.ripper_panel.set_dimensions(
            doc.texture_ripper.output_width, doc.texture_ripper.output_height
        )
        self.ripper_panel.set_lock_aspect_ratio(doc.texture_ripper.lock_aspect_ratio)
        self.ripper_panel.set_interpolation_mode(doc.texture_ripper.interpolation)

        if doc.texture_ripper.quad is not None:
            self.tool.set_quad(doc.texture_ripper.quad)
        else:
            self.tool.clear()

        # Restaurar sprites y atlas
        self.sprite_tool.set_sprites(list(doc.sprites))
        self.sprite_panel.set_atlas_settings(doc.atlas)

        self._update_window_title()
        self._update_actions()
        self._refresh_status()
        self.statusBar().showMessage(
            self.tr("Proyecto cargado: {name}").format(name=path.name), 4000
        )
        return True

    def save_project_dialog(self) -> bool:
        if self._document.file_path is not None:
            return self.save_project(self._document.file_path)
        return self.save_project_as_dialog()

    def save_project_as_dialog(self) -> bool:
        start_dir = str(self._last_directory) if self._last_directory else ""
        suggested = f"{self._document.project_name}.ivtex"
        default_target = Path(start_dir) / suggested if start_dir else Path(suggested)

        chosen, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Guardar proyecto como"),
            str(default_target),
            PROJECT_FILE_FILTER,
        )
        if not chosen:
            return False

        target = Path(chosen)
        if target.suffix.lower() != ".ivtex":
            target = target.with_suffix(".ivtex")

        return self.save_project(target)

    def _get_current_image_bytes(self) -> bytes | None:
        if self._current_image is None:
            return None
        if self._current_image.path.is_file():
            try:
                return self._current_image.path.read_bytes()
            except OSError:
                pass
        # Generar PNG en memoria desde el arreglo RGBA
        bio = BytesIO()
        im = Image.fromarray(self._current_image.pixels, mode="RGBA")
        im.save(bio, format="PNG")
        return bio.getvalue()

    def save_project(self, path: Path) -> bool:
        """Guarda el proyecto actual en ``path`` de forma atómica."""
        if not self.canvas.has_image:
            return False

        # Sincronizar estado actual del UI en el documento
        self._document.texture_ripper.quad = self.tool.selection.get_quad()
        self._document.texture_ripper.output_width = self.ripper_panel.output_width
        self._document.texture_ripper.output_height = self.ripper_panel.output_height
        self._document.texture_ripper.lock_aspect_ratio = self.ripper_panel.lock_aspect_ratio
        self._document.texture_ripper.interpolation = self.ripper_panel.interpolation_mode

        # Sincronizar sprites y atlas
        self._document.sprites = list(self.sprite_tool.sprites)
        self._document.atlas = self.sprite_panel.get_atlas_settings()

        img_bytes = self._get_current_image_bytes()

        try:
            save_project(path, self._document, image_bytes=img_bytes, embed_image=True)
            self._last_directory = path.parent
            self.undo_stack.setClean()
            self._document.mark_clean(path)
            self._update_window_title()
            self.statusBar().showMessage(
                self.tr("Proyecto guardado: {name}").format(name=path.name), 4000
            )
            return True
        except ProjectIOError as exc:
            logger.exception("Error al guardar proyecto en %s: %s", path.name, exc)
            self._show_error(self.tr("Error al guardar el proyecto"), str(exc))
            return False

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    # -------------------------------------------------------------- estado
    @property
    def current_image(self) -> LoadedImage | None:
        return self._current_image

    @property
    def document(self) -> Document:
        return self._document

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

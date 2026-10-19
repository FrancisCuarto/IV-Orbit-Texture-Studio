"""Panel de control para la herramienta de sprites y generación de atlas.

Permite configurar la detección automática por transparencia en imágenes individuales,
así como la composición interactiva, reorganización manual libre y auto-empaquetado
de múltiples texturas en un Atlas unificado.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from iv_orbit_texture_studio.core.atlas_item import AtlasItem
from iv_orbit_texture_studio.core.document import AtlasSettings
from iv_orbit_texture_studio.core.region import Pivot, PivotMode, Rect
from iv_orbit_texture_studio.exporters.atlas_exporter import export_atlas_and_metadata
from iv_orbit_texture_studio.imaging.atlas import (
    AtlasFitError,
    AtlasResult,
    composite_atlas_items,
    pack_sprites_to_atlas,
)
from iv_orbit_texture_studio.imaging.sprites import extract_sprite_pixels
from iv_orbit_texture_studio.tools.sprites.tool import SpriteTool
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import Size
from iv_orbit_texture_studio.ui.qt_image import rgba_array_to_qimage

if TYPE_CHECKING:
    from iv_orbit_texture_studio.imaging.image_io import LoadedImage

logger = logging.getLogger(__name__)


class SpritePanel(QWidget):
    """Panel lateral de control para sprites y atlas."""

    atlas_exported = Signal(Path, Path)  # (image_path, json_path)
    submode_changed = Signal(str)  # "atlas" o "sprites"

    def __init__(self, tool: SpriteTool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool = tool
        self._source_image: LoadedImage | None = None
        self._updating_table = False
        self._updating_atlas_table = False
        self._updating_atlas_pos = False
        self._last_atlas_result: AtlasResult | None = None

        self._setup_ui()
        self._tool.sprites_changed.connect(self._on_sprites_changed)
        self._tool.selected_sprite_changed.connect(self._on_selected_sprite_changed)
        self._tool.atlas_tool.atlas_changed.connect(self._on_atlas_changed)
        self._tool.atlas_tool.item_selected.connect(self._on_atlas_item_selected)
        self._tool.atlas_tool.item_moved.connect(self._on_atlas_item_moved)

        self._update_ui_state()
        self._update_atlas_ui_state()
        self.setMinimumWidth(330)

    def set_source_image(self, image: LoadedImage | None) -> None:
        self._source_image = image
        self._tool.set_image_size(
            None if image is None else Size(float(image.width), float(image.height))
        )
        self._update_ui_state()
        self._update_atlas_ui_state()

    def set_active_tab(self, index: int) -> None:
        """Cambia programáticamente la pestaña activa (0: Compositor de Atlas, 1: Detección)."""
        if 0 <= index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    # ---------------------------------------------------------------------- UI
    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # ================================================= Pestaña 0: Compositor de Atlas
        tab_atlas = QWidget()
        scroll_atlas = QScrollArea()
        scroll_atlas.setWidgetResizable(True)
        scroll_atlas.setFrameShape(QFrame.Shape.NoFrame)

        container_atlas = QWidget()
        layout_atlas = QVBoxLayout(container_atlas)
        layout_atlas.setContentsMargins(6, 6, 6, 6)
        layout_atlas.setSpacing(10)

        # 1. Grupo: Texturas en el Atlas
        group_items = QGroupBox(self.tr("Texturas en el Atlas"))
        v_items = QVBoxLayout(group_items)

        self._table_atlas = QTableWidget(0, 3)
        self._table_atlas.setHorizontalHeaderLabels(
            [self.tr("Nombre"), self.tr("Pos (X, Y)"), self.tr("Tamaño")]
        )
        self._table_atlas.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table_atlas.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table_atlas.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table_atlas.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table_atlas.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table_atlas.setMinimumHeight(130)
        self._table_atlas.itemSelectionChanged.connect(self._on_atlas_table_selection_changed)
        v_items.addWidget(self._table_atlas)

        h_btn_items = QHBoxLayout()
        self._btn_remove_atlas = QPushButton(self.tr("Eliminar"))
        self._btn_remove_atlas.setToolTip(self.tr("Eliminar la textura seleccionada del atlas"))
        self._btn_remove_atlas.clicked.connect(self._remove_selected_atlas_item)

        self._btn_clear_atlas = QPushButton(self.tr("Limpiar todo"))
        self._btn_clear_atlas.setToolTip(self.tr("Quitar todas las texturas del atlas"))
        self._btn_clear_atlas.clicked.connect(self._tool.atlas_tool.clear)

        h_btn_items.addWidget(self._btn_remove_atlas)
        h_btn_items.addWidget(self._btn_clear_atlas)
        v_items.addLayout(h_btn_items)

        # Propiedades del elemento seleccionado en Atlas
        form_item_props = QFormLayout()
        self._edit_atlas_name = QLineEdit()
        self._edit_atlas_name.setPlaceholderText(self.tr("Nombre de la textura"))
        self._edit_atlas_name.editingFinished.connect(self._on_atlas_name_edited)
        form_item_props.addRow(self.tr("Nombre:"), self._edit_atlas_name)

        h_pos = QHBoxLayout()
        self._spin_atlas_x = QSpinBox()
        self._spin_atlas_x.setRange(-4096, 16384)
        self._spin_atlas_x.valueChanged.connect(self._on_atlas_pos_edited)

        self._spin_atlas_y = QSpinBox()
        self._spin_atlas_y.setRange(-4096, 16384)
        self._spin_atlas_y.valueChanged.connect(self._on_atlas_pos_edited)

        h_pos.addWidget(QLabel("X:"))
        h_pos.addWidget(self._spin_atlas_x)
        h_pos.addWidget(QLabel("Y:"))
        h_pos.addWidget(self._spin_atlas_y)
        form_item_props.addRow(self.tr("Posición px:"), h_pos)
        v_items.addLayout(form_item_props)
        layout_atlas.addWidget(group_items)

        # 2. Grupo: Dimensiones y Empaquetado
        group_dims = QGroupBox(self.tr("Empaquetado y Dimensiones"))
        v_dims = QVBoxLayout(group_dims)
        form_dims = QFormLayout()

        self._combo_atlas_dims = QComboBox()
        self._combo_atlas_dims.addItem("Auto (Ajustado)", (0, 0))
        self._combo_atlas_dims.addItem("512 × 512 px", (512, 512))
        self._combo_atlas_dims.addItem("1024 × 1024 px", (1024, 1024))
        self._combo_atlas_dims.addItem("2048 × 2048 px", (2048, 2048))
        self._combo_atlas_dims.addItem("4096 × 4096 px", (4096, 4096))
        self._combo_atlas_dims.addItem(self.tr("Personalizado…"), (-1, -1))
        self._combo_atlas_dims.setCurrentIndex(2)  # 1024x1024 default
        self._combo_atlas_dims.currentIndexChanged.connect(self._on_atlas_dims_combo_changed)
        form_dims.addRow(self.tr("Lienzo:"), self._combo_atlas_dims)

        h_custom_dims = QHBoxLayout()
        self._spin_atlas_custom_w = QSpinBox()
        self._spin_atlas_custom_w.setRange(32, 16384)
        self._spin_atlas_custom_w.setSingleStep(64)
        self._spin_atlas_custom_w.setValue(1024)
        self._spin_atlas_custom_w.valueChanged.connect(self._on_atlas_custom_dim_changed)

        self._spin_atlas_custom_h = QSpinBox()
        self._spin_atlas_custom_h.setRange(32, 16384)
        self._spin_atlas_custom_h.setSingleStep(64)
        self._spin_atlas_custom_h.setValue(1024)
        self._spin_atlas_custom_h.valueChanged.connect(self._on_atlas_custom_dim_changed)

        h_custom_dims.addWidget(QLabel("W:"))
        h_custom_dims.addWidget(self._spin_atlas_custom_w)
        h_custom_dims.addWidget(QLabel("H:"))
        h_custom_dims.addWidget(self._spin_atlas_custom_h)
        form_dims.addRow(self.tr("Personalizado:"), h_custom_dims)
        self._spin_atlas_custom_w.setEnabled(False)
        self._spin_atlas_custom_h.setEnabled(False)

        self._spin_compose_spacing = QSpinBox()
        self._spin_compose_spacing.setRange(0, 64)
        self._spin_compose_spacing.setValue(2)
        self._spin_compose_spacing.setSuffix(" px")
        form_dims.addRow(self.tr("Espaciado:"), self._spin_compose_spacing)

        self._spin_compose_padding = QSpinBox()
        self._spin_compose_padding.setRange(0, 64)
        self._spin_compose_padding.setValue(2)
        self._spin_compose_padding.setSuffix(" px")
        form_dims.addRow(self.tr("Margen ext.:"), self._spin_compose_padding)

        self._chk_compose_pot = QCheckBox(self.tr("Potencia de dos (POT: 512, 1024…)"))
        self._chk_compose_pot.setChecked(True)
        form_dims.addRow("", self._chk_compose_pot)

        self._chk_compose_square = QCheckBox(self.tr("Atlas cuadrado (Ancho == Alto)"))
        self._chk_compose_square.setChecked(False)
        form_dims.addRow("", self._chk_compose_square)
        v_dims.addLayout(form_dims)

        self._btn_atlas_autopack = QPushButton(self.tr("⚡ Auto-empaquetar (MaxRects)"))
        self._btn_atlas_autopack.setToolTip(
            self.tr("Reorganiza automáticamente todas las texturas sin solapamientos")
        )
        self._btn_atlas_autopack.clicked.connect(self.auto_pack_atlas)
        v_dims.addWidget(self._btn_atlas_autopack)

        self._label_atlas_stats_composed = QLabel("—")
        self._label_atlas_stats_composed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_atlas_stats_composed.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        v_dims.addWidget(self._label_atlas_stats_composed)

        layout_atlas.addWidget(group_dims)

        # 3. Grupo: Exportación
        group_export_comp = QGroupBox(self.tr("Exportación"))
        v_export_comp = QVBoxLayout(group_export_comp)

        self._btn_export_composed_atlas = QPushButton(self.tr("💾 Exportar Atlas y JSON…"))
        self._btn_export_composed_atlas.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; "
            "font-weight: bold; padding: 7px; border-radius: 4px; }\n"
            "QPushButton:hover { background-color: #0b5ed7; }\n"
            "QPushButton:disabled { background-color: #444444; color: #888888; }"
        )
        self._btn_export_composed_atlas.clicked.connect(self.export_composed_atlas)
        v_export_comp.addWidget(self._btn_export_composed_atlas)

        self._btn_import_sheet_sprites = QPushButton(
            self.tr("📥 Importar sprites detectados al Atlas")
        )
        self._btn_import_sheet_sprites.setToolTip(
            self.tr("Agrega los sprites detectados en la imagen abierta como texturas al atlas")
        )
        self._btn_import_sheet_sprites.clicked.connect(self.import_detected_sprites_to_atlas)
        v_export_comp.addWidget(self._btn_import_sheet_sprites)

        layout_atlas.addWidget(group_export_comp)
        scroll_atlas.setWidget(container_atlas)

        v_tab_atlas = QVBoxLayout(tab_atlas)
        v_tab_atlas.setContentsMargins(0, 0, 0, 0)
        v_tab_atlas.addWidget(scroll_atlas)
        self._tabs.addTab(tab_atlas, self.tr("Compositor de Atlas"))

        # ================================================= Pestaña 1: Detección en Imagen
        tab_detect = QWidget()
        scroll_detect = QScrollArea()
        scroll_detect.setWidgetResizable(True)
        scroll_detect.setFrameShape(QFrame.Shape.NoFrame)

        container_detect = QWidget()
        layout_detect = QVBoxLayout(container_detect)
        layout_detect.setContentsMargins(6, 6, 6, 6)
        layout_detect.setSpacing(10)

        # 1. Grupo: Detección Automática
        group_detect = QGroupBox(self.tr("Detección por transparencia"))
        form_detect = QFormLayout(group_detect)

        self._spin_alpha_thresh = QSpinBox()
        self._spin_alpha_thresh.setRange(1, 255)
        self._spin_alpha_thresh.setValue(10)
        self._spin_alpha_thresh.setToolTip(self.tr("Umbral mínimo de opacidad (1 a 255)"))

        self._spin_min_area = QSpinBox()
        self._spin_min_area.setRange(1, 50000)
        self._spin_min_area.setValue(6)
        self._spin_min_area.setSuffix(" px")
        self._spin_min_area.setToolTip(
            self.tr("Ignorar componentes con menos píxeles que este valor")
        )

        self._spin_padding = QSpinBox()
        self._spin_padding.setRange(0, 50)
        self._spin_padding.setValue(0)
        self._spin_padding.setSuffix(" px")
        self._spin_padding.setToolTip(self.tr("Margen añadido alrededor de cada sprite detectado"))

        self._btn_detect = QPushButton(self.tr("Detectar sprites automáticamente"))
        self._btn_detect.clicked.connect(self.detect_sprites)

        form_detect.addRow(self.tr("Umbral alfa:"), self._spin_alpha_thresh)
        form_detect.addRow(self.tr("Área mínima:"), self._spin_min_area)
        form_detect.addRow(self.tr("Margen / Padding:"), self._spin_padding)
        form_detect.addRow("", self._btn_detect)
        layout_detect.addWidget(group_detect)

        # 2. Grupo: Lista de Sprites
        group_list = QGroupBox(self.tr("Sprites"))
        v_list = QVBoxLayout(group_list)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(
            [self.tr("Nombre"), self.tr("Posición"), self.tr("Tamaño")]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setMinimumHeight(120)
        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)
        v_list.addWidget(self._table)

        h_btn_list = QHBoxLayout()
        self._btn_add_manual = QPushButton(self.tr("Agregar"))
        self._btn_add_manual.setToolTip(self.tr("Agrega un nuevo sprite en el centro de la imagen"))
        self._btn_add_manual.clicked.connect(self._add_manual_sprite)

        self._btn_remove = QPushButton(self.tr("Eliminar"))
        self._btn_remove.clicked.connect(self._tool.remove_selected)

        self._btn_clear = QPushButton(self.tr("Limpiar todos"))
        self._btn_clear.clicked.connect(self._tool.clear)

        h_btn_list.addWidget(self._btn_add_manual)
        h_btn_list.addWidget(self._btn_remove)
        h_btn_list.addWidget(self._btn_clear)
        v_list.addLayout(h_btn_list)
        layout_detect.addWidget(group_list)

        # 3. Grupo: Propiedades del Sprite Seleccionado
        group_props = QGroupBox(self.tr("Propiedades del sprite"))
        form_props = QFormLayout(group_props)

        self._edit_name = QLineEdit()
        self._edit_name.setPlaceholderText(self.tr("Nombre del sprite"))
        self._edit_name.editingFinished.connect(self._on_name_edited)
        form_props.addRow(self.tr("Nombre:"), self._edit_name)

        # Pivote
        self._combo_pivot = QComboBox()
        self._combo_pivot.addItem(self.tr("Centro (0.5, 0.5)"), PivotMode.CENTER)
        self._combo_pivot.addItem(
            self.tr("Pie / Base inferior (0.5, 1.0)"), PivotMode.BOTTOM_CENTER
        )
        self._combo_pivot.addItem(self.tr("Superior Izquierda (0.0, 0.0)"), PivotMode.TOP_LEFT)
        self._combo_pivot.addItem(self.tr("Superior Centro (0.5, 0.0)"), PivotMode.TOP_CENTER)
        self._combo_pivot.addItem(self.tr("Superior Derecha (1.0, 0.0)"), PivotMode.TOP_RIGHT)
        self._combo_pivot.addItem(self.tr("Inferior Izquierda (0.0, 1.0)"), PivotMode.BOTTOM_LEFT)
        self._combo_pivot.addItem(self.tr("Inferior Derecha (1.0, 1.0)"), PivotMode.BOTTOM_RIGHT)
        self._combo_pivot.addItem(self.tr("Personalizado…"), PivotMode.CUSTOM)
        self._combo_pivot.currentIndexChanged.connect(self._on_pivot_combo_changed)
        form_props.addRow(self.tr("Pivote:"), self._combo_pivot)

        h_custom_pivot = QHBoxLayout()
        self._spin_piv_x = QDoubleSpinBox()
        self._spin_piv_x.setRange(0.0, 1.0)
        self._spin_piv_x.setSingleStep(0.05)
        self._spin_piv_x.setValue(0.5)
        self._spin_piv_x.valueChanged.connect(self._on_custom_pivot_changed)

        self._spin_piv_y = QDoubleSpinBox()
        self._spin_piv_y.setRange(0.0, 1.0)
        self._spin_piv_y.setSingleStep(0.05)
        self._spin_piv_y.setValue(0.5)
        self._spin_piv_y.valueChanged.connect(self._on_custom_pivot_changed)

        h_custom_pivot.addWidget(QLabel("X:"))
        h_custom_pivot.addWidget(self._spin_piv_x)
        h_custom_pivot.addWidget(QLabel("Y:"))
        h_custom_pivot.addWidget(self._spin_piv_y)
        form_props.addRow(self.tr("Normalizado:"), h_custom_pivot)
        layout_detect.addWidget(group_props)

        # 4. Grupo: Empaquetado de Sprites Detectados
        group_atlas = QGroupBox(self.tr("Empaquetado de Sprites Detectados"))
        v_atlas = QVBoxLayout(group_atlas)
        form_atlas = QFormLayout()

        self._spin_atlas_spacing = QSpinBox()
        self._spin_atlas_spacing.setRange(0, 32)
        self._spin_atlas_spacing.setValue(2)
        self._spin_atlas_spacing.setSuffix(" px")

        self._spin_atlas_padding = QSpinBox()
        self._spin_atlas_padding.setRange(0, 32)
        self._spin_atlas_padding.setValue(2)
        self._spin_atlas_padding.setSuffix(" px")

        self._chk_pot = QCheckBox(self.tr("Potencia de dos (POT: 256, 512, 1024…)"))
        self._chk_pot.setChecked(True)

        self._chk_square = QCheckBox(self.tr("Atlas cuadrado (Ancho == Alto)"))
        self._chk_square.setChecked(False)

        form_atlas.addRow(self.tr("Espaciado:"), self._spin_atlas_spacing)
        form_atlas.addRow(self.tr("Margen ext.:"), self._spin_atlas_padding)
        form_atlas.addRow("", self._chk_pot)
        form_atlas.addRow("", self._chk_square)
        v_atlas.addLayout(form_atlas)

        # Previsualización del atlas tradicional
        self._preview_frame = QFrame()
        self._preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._preview_frame.setStyleSheet("background-color: #1a1a1a; border-radius: 4px;")
        self._preview_frame.setMinimumHeight(110)
        v_prev_frame = QVBoxLayout(self._preview_frame)
        self._label_preview = QLabel(self.tr("Sin generar"))
        self._label_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_preview.setStyleSheet("color: #888888;")
        v_prev_frame.addWidget(self._label_preview)
        v_atlas.addWidget(self._preview_frame)

        self._label_atlas_stats = QLabel("—")
        self._label_atlas_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_atlas_stats.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        v_atlas.addWidget(self._label_atlas_stats)

        self._btn_pack = QPushButton(self.tr("Generar Atlas"))
        self._btn_pack.clicked.connect(self.generate_atlas)
        v_atlas.addWidget(self._btn_pack)

        self._btn_export_atlas = QPushButton(self.tr("Exportar Atlas y JSON…"))
        self._btn_export_atlas.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; "
            "font-weight: bold; padding: 6px; border-radius: 4px; }\n"
            "QPushButton:hover { background-color: #0b5ed7; }\n"
            "QPushButton:disabled { background-color: #444444; color: #888888; }"
        )
        self._btn_export_atlas.clicked.connect(self.export_atlas)
        v_atlas.addWidget(self._btn_export_atlas)

        layout_detect.addWidget(group_atlas)
        scroll_detect.setWidget(container_detect)

        v_tab_detect = QVBoxLayout(tab_detect)
        v_tab_detect.setContentsMargins(0, 0, 0, 0)
        v_tab_detect.addWidget(scroll_detect)
        self._tabs.addTab(tab_detect, self.tr("Detección en Imagen"))

        main_layout.addWidget(self._tabs)

    # -------------------------------------------------------- eventos de pestañas
    def _on_tab_changed(self, index: int) -> None:
        if index == 0:
            self._tool.submode = "atlas"
            self.submode_changed.emit("atlas")
        else:
            self._tool.submode = "sprites"
            self.submode_changed.emit("sprites")

    # ---------------------------------------------------- eventos Compositor Atlas
    def _update_atlas_ui_state(self) -> None:
        items = self._tool.atlas_tool.items
        has_items = len(items) > 0
        has_selected = self._tool.atlas_tool.selected_id is not None
        has_source = self._source_image is not None and len(self._tool.sprites) > 0

        self._btn_clear_atlas.setEnabled(has_items)
        self._btn_atlas_autopack.setEnabled(has_items)
        self._btn_export_composed_atlas.setEnabled(has_items)
        self._btn_remove_atlas.setEnabled(has_selected)
        self._edit_atlas_name.setEnabled(has_selected)
        self._spin_atlas_x.setEnabled(has_selected)
        self._spin_atlas_y.setEnabled(has_selected)
        self._btn_import_sheet_sprites.setEnabled(has_source)

        selected = self._tool.atlas_tool.selected_item
        if selected is not None:
            self._edit_atlas_name.setText(selected.name)
            self._updating_atlas_pos = True
            self._spin_atlas_x.setValue(selected.x)
            self._spin_atlas_y.setValue(selected.y)
            self._updating_atlas_pos = False
        else:
            self._edit_atlas_name.clear()

        # Actualizar etiqueta de estadísticas
        w = self._tool.atlas_tool.atlas_width
        h = self._tool.atlas_tool.atlas_height
        count = len(items)
        plural = "s" if count != 1 else ""
        overlap_count = 0
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if items[i].rect.intersects(items[j].rect):
                    overlap_count += 1

        if overlap_count > 0:
            status_text = (
                f"{w} × {h} px  |  {count} textura{plural}  |  ⚠️ {overlap_count} solapamiento(s)"
            )
            self._label_atlas_stats_composed.setStyleSheet(
                "color: #ff5555; font-size: 11px; font-weight: bold;"
            )
        else:
            status_text = f"{w} × {h} px  |  {count} textura{plural}  |  ✓ Sin solapamientos"
            self._label_atlas_stats_composed.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        self._label_atlas_stats_composed.setText(status_text)

    def _on_atlas_changed(self) -> None:
        self._refresh_atlas_table()
        self._update_atlas_ui_state()

    def _on_atlas_item_selected(self, item_id: str) -> None:
        self._update_atlas_ui_state()
        if not self._updating_atlas_table:
            for row in range(self._table_atlas.rowCount()):
                it = self._table_atlas.item(row, 0)
                if it and it.data(Qt.ItemDataRole.UserRole) == item_id:
                    self._table_atlas.selectRow(row)
                    break

    def _on_atlas_item_moved(self, item_id: str, new_x: int, new_y: int) -> None:
        if not self._updating_atlas_pos and self._tool.atlas_tool.selected_id == item_id:
            self._updating_atlas_pos = True
            self._spin_atlas_x.setValue(new_x)
            self._spin_atlas_y.setValue(new_y)
            self._updating_atlas_pos = False

    def _refresh_atlas_table(self) -> None:
        self._updating_atlas_table = True
        items = self._tool.atlas_tool.items
        self._table_atlas.setRowCount(len(items))

        for row, it in enumerate(items):
            item_name = QTableWidgetItem(it.name)
            item_name.setData(Qt.ItemDataRole.UserRole, it.id)
            item_pos = QTableWidgetItem(f"{it.x}, {it.y}")
            item_size = QTableWidgetItem(f"{it.width} × {it.height}")

            item_pos.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self._table_atlas.setItem(row, 0, item_name)
            self._table_atlas.setItem(row, 1, item_pos)
            self._table_atlas.setItem(row, 2, item_size)

            if it.id == self._tool.atlas_tool.selected_id:
                self._table_atlas.selectRow(row)

        self._updating_atlas_table = False

    def _on_atlas_table_selection_changed(self) -> None:
        if self._updating_atlas_table:
            return
        selected = self._table_atlas.selectedItems()
        if selected:
            row = selected[0].row()
            it = self._table_atlas.item(row, 0)
            if it is not None:
                item_id = str(it.data(Qt.ItemDataRole.UserRole))
                self._tool.atlas_tool.select_item(item_id)

    def _remove_selected_atlas_item(self) -> None:
        sel_id = self._tool.atlas_tool.selected_id
        if sel_id is not None:
            self._tool.atlas_tool.remove_item(sel_id)

    def _on_atlas_name_edited(self) -> None:
        selected = self._tool.atlas_tool.selected_item
        if selected is not None:
            new_name = self._edit_atlas_name.text().strip()
            if new_name and new_name != selected.name:
                selected.name = new_name
                self._tool.atlas_tool.rebuild_composite()
                self._tool.atlas_tool.atlas_changed.emit()

    def _on_atlas_pos_edited(self) -> None:
        if self._updating_atlas_pos:
            return
        selected = self._tool.atlas_tool.selected_item
        if selected is not None:
            nx = self._spin_atlas_x.value()
            ny = self._spin_atlas_y.value()
            if selected.x != nx or selected.y != ny:
                selected.x = nx
                selected.y = ny
                self._tool.atlas_tool.rebuild_composite()
                self._tool.atlas_tool.atlas_changed.emit()

    def _on_atlas_dims_combo_changed(self, index: int) -> None:
        data = self._combo_atlas_dims.itemData(index)
        if data == (-1, -1):
            self._spin_atlas_custom_w.setEnabled(True)
            self._spin_atlas_custom_h.setEnabled(True)
            self._tool.atlas_tool.set_atlas_dimensions(
                self._spin_atlas_custom_w.value(), self._spin_atlas_custom_h.value()
            )
        elif data == (0, 0):
            self._spin_atlas_custom_w.setEnabled(False)
            self._spin_atlas_custom_h.setEnabled(False)
            self.auto_pack_atlas()
        else:
            w, h = data
            self._spin_atlas_custom_w.setEnabled(False)
            self._spin_atlas_custom_h.setEnabled(False)
            self._tool.atlas_tool.set_atlas_dimensions(w, h)

    def _on_atlas_custom_dim_changed(self) -> None:
        if self._combo_atlas_dims.currentData() == (-1, -1):
            self._tool.atlas_tool.set_atlas_dimensions(
                self._spin_atlas_custom_w.value(), self._spin_atlas_custom_h.value()
            )

    def auto_pack_atlas(self) -> None:
        """Acomoda automáticamente todas las texturas usando MaxRects."""
        self._tool.atlas_tool.auto_pack(
            padding=self._spin_compose_padding.value(),
            spacing=self._spin_compose_spacing.value(),
            power_of_two=self._chk_compose_pot.isChecked(),
            square=self._chk_compose_square.isChecked(),
        )

    def import_detected_sprites_to_atlas(self) -> None:
        """Importa todos los sprites actualmente detectados de la imagen como AtlasItems."""
        if self._source_image is None or not self._tool.sprites:
            return
        count = 0
        for s in self._tool.sprites:
            crop = extract_sprite_pixels(self._source_image.pixels, s.rect)
            item = AtlasItem.create(name=s.name, pixels=crop, pivot=s.pivot)
            self._tool.atlas_tool.add_item(item)
            count += 1
        self._tabs.setCurrentIndex(0)
        QMessageBox.information(
            self,
            self.tr("Sprites importados"),
            self.tr("Se importaron {count} sprites al Compositor de Atlas.").format(count=count),
        )

    def export_composed_atlas(self) -> None:
        """Exporta el atlas interactivo compuesto y sus metadatos JSON a disco."""
        items = self._tool.atlas_tool.items
        if not items:
            QMessageBox.warning(
                self,
                self.tr("Atlas vacío"),
                self.tr("No hay texturas en el atlas para exportar."),
            )
            return

        default_name = "atlas.png"
        start_dir = ""
        if self._source_image is not None:
            default_name = f"{self._source_image.path.stem}_atlas.png"
            start_dir = str(self._source_image.path.parent / default_name)

        path_str, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Exportar imagen del Atlas (se creará también el archivo .json)"),
            start_dir,
            self.tr("Imágenes PNG (*.png);;Todos los archivos (*)"),
        )
        if not path_str:
            return

        img_target = Path(path_str)
        if img_target.suffix.lower() != ".png":
            img_target = img_target.with_suffix(".png")

        try:
            result = composite_atlas_items(
                items,
                self._tool.atlas_tool.atlas_width,
                self._tool.atlas_tool.atlas_height,
                atlas_image_name=img_target.name,
            )
            out_img, out_json = export_atlas_and_metadata(result, img_target, overwrite=True)
            QMessageBox.information(
                self,
                self.tr("Atlas exportado exitosamente"),
                self.tr(
                    "Se exportaron correctamente:\n• Imagen: {img}\n• Metadatos: {json}"
                ).format(img=out_img.name, json=out_json.name),
            )
            self.atlas_exported.emit(out_img, out_json)
        except Exception as exc:
            logger.exception("Error al exportar atlas compuesto: %s", exc)
            QMessageBox.critical(self, self.tr("Error al exportar"), str(exc))

    # ------------------------------------------------- eventos Detección de Sprites
    def _update_ui_state(self) -> None:
        has_img = self._source_image is not None
        has_sprites = len(self._tool.sprites) > 0
        has_selected = self._tool.selected_sprite is not None

        self._btn_detect.setEnabled(has_img)
        self._btn_add_manual.setEnabled(has_img)
        self._btn_clear.setEnabled(has_sprites)
        self._btn_remove.setEnabled(has_selected)
        self._edit_name.setEnabled(has_selected)
        self._combo_pivot.setEnabled(has_selected)
        self._spin_piv_x.setEnabled(has_selected)
        self._spin_piv_y.setEnabled(has_selected)
        self._btn_pack.setEnabled(has_img and has_sprites)
        self._btn_export_atlas.setEnabled(self._last_atlas_result is not None)

        if has_selected:
            sprite = self._tool.selected_sprite
            if sprite is not None:
                self._edit_name.setText(sprite.name)
                for idx in range(self._combo_pivot.count()):
                    if self._combo_pivot.itemData(idx) == sprite.pivot.mode:
                        self._combo_pivot.blockSignals(True)
                        self._combo_pivot.setCurrentIndex(idx)
                        self._combo_pivot.blockSignals(False)
                        break
                self._spin_piv_x.blockSignals(True)
                self._spin_piv_y.blockSignals(True)
                self._spin_piv_x.setValue(sprite.pivot.x)
                self._spin_piv_y.setValue(sprite.pivot.y)
                self._spin_piv_x.blockSignals(False)
                self._spin_piv_y.blockSignals(False)
        else:
            self._edit_name.clear()

    def _on_sprites_changed(self) -> None:
        self._refresh_table()
        self._update_ui_state()
        self._update_atlas_ui_state()

    def _on_selected_sprite_changed(self, sprite_id: str) -> None:
        self._update_ui_state()
        if not self._updating_table:
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == sprite_id:
                    self._table.selectRow(row)
                    break

    def _refresh_table(self) -> None:
        self._updating_table = True
        self._table.setRowCount(len(self._tool.sprites))

        for row, s in enumerate(self._tool.sprites):
            item_name = QTableWidgetItem(s.name)
            item_name.setData(Qt.ItemDataRole.UserRole, s.id)
            item_pos = QTableWidgetItem(f"{s.rect.x}, {s.rect.y}")
            item_size = QTableWidgetItem(f"{s.rect.width} × {s.rect.height}")

            item_pos.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self._table.setItem(row, 0, item_name)
            self._table.setItem(row, 1, item_pos)
            self._table.setItem(row, 2, item_size)

            if s.id == self._tool.selected_id:
                self._table.selectRow(row)

        self._updating_table = False

    def _on_table_selection_changed(self) -> None:
        if self._updating_table:
            return
        selected_rows = self._table.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            item = self._table.item(row, 0)
            if item is not None:
                sprite_id = str(item.data(Qt.ItemDataRole.UserRole))
                self._tool.select_sprite(sprite_id)

    def _on_name_edited(self) -> None:
        sprite = self._tool.selected_sprite
        if sprite is not None:
            new_name = self._edit_name.text().strip()
            if new_name and new_name != sprite.name:
                self._tool.rename_sprite(sprite.id, new_name)

    def _on_pivot_combo_changed(self, index: int) -> None:
        sprite = self._tool.selected_sprite
        if sprite is not None:
            mode: PivotMode = self._combo_pivot.itemData(index)
            if mode != PivotMode.CUSTOM:
                new_pivot = Pivot.from_mode(mode)
                self._tool.set_sprite_pivot(sprite.id, new_pivot)

    def _on_custom_pivot_changed(self) -> None:
        sprite = self._tool.selected_sprite
        if sprite is not None:
            px = self._spin_piv_x.value()
            py = self._spin_piv_y.value()
            new_pivot = Pivot(x=px, y=py, mode=PivotMode.CUSTOM)
            self._tool.set_sprite_pivot(sprite.id, new_pivot)

    def _add_manual_sprite(self) -> None:
        if self._source_image is None:
            return
        w = min(64, self._source_image.width)
        h = min(64, self._source_image.height)
        cx = (self._source_image.width - w) // 2
        cy = (self._source_image.height - h) // 2
        self._tool.add_sprite(Rect(cx, cy, w, h))

    # ------------------------------------------------------------- detección
    def detect_sprites(self) -> None:
        """Ejecuta la detección automática de componentes conexos por transparencia."""
        if self._source_image is None:
            return

        alpha_thresh = self._spin_alpha_thresh.value()
        min_area = self._spin_min_area.value()
        padding = self._spin_padding.value()

        count = self._tool.auto_detect(
            self._source_image.pixels,
            alpha_threshold=alpha_thresh,
            min_area=min_area,
            padding=padding,
        )

        if count == 0:
            QMessageBox.information(
                self,
                self.tr("Detección de sprites"),
                self.tr("No se detectaron regiones opacas con los parámetros seleccionados."),
            )

    # ------------------------------------------------------ generación tradicional
    def generate_atlas(self) -> AtlasResult | None:
        """Empaqueta todos los sprites en un atlas y actualiza la previsualización."""
        if self._source_image is None or not self._tool.sprites:
            return None

        sprites_with_pixels = []
        for s in self._tool.sprites:
            crop = extract_sprite_pixels(self._source_image.pixels, s.rect)
            sprites_with_pixels.append((s, crop))

        try:
            result = pack_sprites_to_atlas(
                sprites_with_pixels,
                padding=self._spin_atlas_padding.value(),
                spacing=self._spin_atlas_spacing.value(),
                power_of_two=self._chk_pot.isChecked(),
                square=self._chk_square.isChecked(),
            )
            self._last_atlas_result = result

            # Previsualización en miniatura
            qimg = rgba_array_to_qimage(result.image)
            pix = QPixmap.fromImage(qimg)
            self._label_preview.setPixmap(
                pix.scaled(
                    self._label_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

            count = len(result.sprites)
            self._label_atlas_stats.setText(
                f"{result.width} × {result.height} px  |  {count} sprite{'s' if count != 1 else ''}"
            )
            self._update_ui_state()
            return result
        except AtlasFitError as exc:
            logger.warning("Error de empaquetado de atlas: %s", exc)
            QMessageBox.warning(self, self.tr("Error al empaquetar atlas"), str(exc))
            return None

    def get_atlas_settings(self) -> AtlasSettings:
        """Obtiene la configuración actual de empaquetado del atlas."""
        return AtlasSettings(
            spacing=self._spin_atlas_spacing.value(),
            padding=self._spin_atlas_padding.value(),
            power_of_two=self._chk_pot.isChecked(),
            square=self._chk_square.isChecked(),
        )

    def set_atlas_settings(self, settings: AtlasSettings) -> None:
        """Aplica la configuración de empaquetado del atlas."""
        self._spin_atlas_spacing.setValue(settings.spacing)
        self._spin_atlas_padding.setValue(settings.padding)
        self._chk_pot.setChecked(settings.power_of_two)
        self._chk_square.setChecked(settings.square)

    def export_atlas(self) -> None:
        """Exporta el atlas (según la pestaña activa o el contexto disponible)."""
        if self._tabs.currentIndex() == 0 and len(self._tool.atlas_tool.items) > 0:
            self.export_composed_atlas()
        else:
            self._export_legacy_atlas()

    def _export_legacy_atlas(self) -> None:
        atlas_result = self._last_atlas_result
        if atlas_result is None:
            atlas_result = self.generate_atlas()
            if atlas_result is None:
                return

        default_name = "atlas.png"
        start_dir = ""
        if self._source_image is not None:
            default_name = f"{self._source_image.path.stem}_atlas.png"
            start_dir = str(self._source_image.path.parent / default_name)

        path_str, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Exportar imagen del Atlas (se creará también el archivo .json)"),
            start_dir,
            self.tr("Imágenes PNG (*.png);;Todos los archivos (*)"),
        )
        if not path_str:
            return

        img_target = Path(path_str)
        if img_target.suffix.lower() != ".png":
            img_target = img_target.with_suffix(".png")

        try:
            out_img, out_json = export_atlas_and_metadata(atlas_result, img_target, overwrite=True)
            QMessageBox.information(
                self,
                self.tr("Atlas exportado exitosamente"),
                self.tr(
                    "Se exportaron correctamente:\n• Imagen: {img}\n• Metadatos: {json}"
                ).format(img=out_img.name, json=out_json.name),
            )
            self.atlas_exported.emit(out_img, out_json)
        except Exception as exc:
            logger.exception("Error al exportar atlas: %s", exc)
            QMessageBox.critical(self, self.tr("Error al exportar"), str(exc))

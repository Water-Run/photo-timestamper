"""
Photo-Timestamper PyQt6 用户界面
Lightroom 风格专业界面 - 重构版
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QMessageBox,
    QCheckBox, QLineEdit, QSpinBox, QGroupBox, QDialog,
    QAbstractItemView, QMenu, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import (
    QPixmap, QImage, QDragEnterEvent, QDropEvent, QIcon,
    QAction, QShortcut, QKeySequence, QPainter, QColor, QPen, QBrush
)

from PIL import Image

from .core import (
    ConfigManager, StyleManager, BatchProcessor, TimeExtractor,
    WatermarkRenderer, scan_images, get_base_path, logger
)
from .i18n import I18n, t, LANGUAGE_NAMES
from . import __version__, __author__, __collaborators__


# ==================== 主题颜色定义 ====================

# Lightroom 蓝色主题
LIGHTROOM_BLUE = "#0a84ff"
LIGHTROOM_BLUE_HOVER = "#409cff"
LIGHTROOM_BLUE_PRESSED = "#0066cc"

LIGHTROOM_STYLE = f"""
/* 主窗口背景 */
QMainWindow {{
    background-color: #1e1e1e;
}}

QWidget {{
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}}

/* 分割器 */
QSplitter::handle {{
    background-color: #3d3d3d;
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* 左侧面板 */
#LeftPanel {{
    background-color: #252525;
    border-right: 1px solid #3d3d3d;
}}

/* 面板标题 */
#PanelTitle {{
    color: #808080;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 12px 16px 8px 16px;
    background-color: transparent;
}}

/* 分组框 */
QGroupBox {{
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    margin-top: 20px;
    padding: 20px 16px 16px 16px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 8px;
    color: #a0a0a0;
    background-color: #2d2d2d;
}}

/* 按钮样式 */
QPushButton {{
    background-color: #3d3d3d;
    border: 1px solid #4d4d4d;
    border-radius: 6px;
    padding: 10px 20px;
    color: #e0e0e0;
    font-weight: 500;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #4d4d4d;
    border-color: #5d5d5d;
}}

QPushButton:pressed {{
    background-color: #2d2d2d;
}}

QPushButton:disabled {{
    background-color: #2d2d2d;
    color: #606060;
    border-color: #3d3d3d;
}}

/* 主要操作按钮 - Lightroom 蓝 */
QPushButton#PrimaryButton {{
    background-color: {LIGHTROOM_BLUE};
    border: none;
    color: white;
    font-weight: bold;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {LIGHTROOM_BLUE_HOVER};
}}

QPushButton#PrimaryButton:pressed {{
    background-color: {LIGHTROOM_BLUE_PRESSED};
}}

QPushButton#PrimaryButton:disabled {{
    background-color: #404040;
    color: #808080;
}}

/* 危险操作按钮 */
QPushButton#DangerButton {{
    background-color: #d32f2f;
    border: none;
    color: white;
}}

QPushButton#DangerButton:hover {{
    background-color: #e53935;
}}

/* 下拉框 */
QComboBox {{
    background-color: #3d3d3d;
    border: 1px solid #4d4d4d;
    border-radius: 6px;
    padding: 10px 14px;
    padding-right: 36px;
    color: #e0e0e0;
    min-height: 24px;
}}

QComboBox:hover {{
    border-color: #5d5d5d;
}}

QComboBox:focus {{
    border-color: {LIGHTROOM_BLUE};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #808080;
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: #2d2d2d;
    border: 1px solid #4d4d4d;
    border-radius: 6px;
    selection-background-color: {LIGHTROOM_BLUE};
    outline: none;
    padding: 4px;
}}

QComboBox QAbstractItemView::item {{
    padding: 10px 14px;
    min-height: 28px;
    border-radius: 4px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: #404040;
}}

/* 列表控件 */
QListWidget {{
    background-color: #2a2a2a;
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    outline: none;
    padding: 6px;
}}

QListWidget::item {{
    background-color: transparent;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 2px 0;
}}

QListWidget::item:hover {{
    background-color: #353535;
}}

QListWidget::item:selected {{
    background-color: {LIGHTROOM_BLUE};
    color: white;
}}

QListWidget::item:selected:!active {{
    background-color: #404040;
}}

/* 滚动条 */
QScrollBar:vertical {{
    background-color: #2a2a2a;
    width: 14px;
    margin: 0;
    border-radius: 7px;
}}

QScrollBar::handle:vertical {{
    background-color: #4d4d4d;
    min-height: 40px;
    border-radius: 7px;
    margin: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #5d5d5d;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: #2a2a2a;
    height: 14px;
    margin: 0;
    border-radius: 7px;
}}

QScrollBar::handle:horizontal {{
    background-color: #4d4d4d;
    min-width: 40px;
    border-radius: 7px;
    margin: 3px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #5d5d5d;
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* 进度条 */
QProgressBar {{
    background-color: #2d2d2d;
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {LIGHTROOM_BLUE};
    border-radius: 5px;
}}

/* 复选框 */
QCheckBox {{
    spacing: 10px;
    color: #e0e0e0;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #4d4d4d;
    background-color: #2d2d2d;
}}

QCheckBox::indicator:hover {{
    border-color: #5d5d5d;
}}

QCheckBox::indicator:checked {{
    background-color: {LIGHTROOM_BLUE};
    border-color: {LIGHTROOM_BLUE};
    image: url(check.png);
}}

QCheckBox::indicator:checked:hover {{
    background-color: {LIGHTROOM_BLUE_HOVER};
    border-color: {LIGHTROOM_BLUE_HOVER};
}}

/* 输入框 */
QLineEdit {{
    background-color: #2d2d2d;
    border: 1px solid #4d4d4d;
    border-radius: 6px;
    padding: 10px 14px;
    color: #e0e0e0;
    selection-background-color: {LIGHTROOM_BLUE};
}}

QLineEdit:hover {{
    border-color: #5d5d5d;
}}

QLineEdit:focus {{
    border-color: {LIGHTROOM_BLUE};
}}

QLineEdit:disabled {{
    background-color: #252525;
    color: #606060;
}}

/* 数字输入框 */
QSpinBox {{
    background-color: #2d2d2d;
    border: 1px solid #4d4d4d;
    border-radius: 6px;
    padding: 10px 14px;
    color: #e0e0e0;
    min-height: 24px;
}}

QSpinBox:hover {{
    border-color: #5d5d5d;
}}

QSpinBox:focus {{
    border-color: {LIGHTROOM_BLUE};
}}

QSpinBox::up-button,
QSpinBox::down-button {{
    background-color: #3d3d3d;
    border: none;
    width: 24px;
    border-radius: 3px;
}}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover {{
    background-color: #4d4d4d;
}}

/* 标签 */
QLabel {{
    color: #c0c0c0;
    background-color: transparent;
}}

QLabel#SectionLabel {{
    color: #808080;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* 预览区域 */
#PreviewPanel {{
    background-color: #1a1a1a;
    border: 1px solid #2d2d2d;
    border-radius: 10px;
}}

/* 对话框 */
QDialog {{
    background-color: #2d2d2d;
}}

/* 状态栏 */
QStatusBar {{
    background-color: #252525;
    border-top: 1px solid #3d3d3d;
    color: #808080;
    padding: 6px 16px;
    font-size: 12px;
}}

/* 工具提示 */
QToolTip {{
    background-color: #3d3d3d;
    border: 1px solid #4d4d4d;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e0e0e0;
}}

/* 搜索框样式 */
#SearchBox {{
    background-color: #2d2d2d;
    border: 1px solid #4d4d4d;
    border-radius: 6px;
    padding: 8px 12px;
    padding-left: 32px;
    color: #e0e0e0;
}}

#SearchBox:focus {{
    border-color: {LIGHTROOM_BLUE};
}}
"""


# ==================== 处理线程 ====================

class ProcessingThread(QThread):
    """后台处理线程"""

    progress = pyqtSignal(int, int, str)
    preview = pyqtSignal(str, object)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, processor: BatchProcessor, image_paths: list[str], style_name: str):
        super().__init__()
        self.processor = processor
        self.image_paths = image_paths
        self.style_name = style_name

    def run(self):
        try:
            results = self.processor.process_batch(
                self.image_paths,
                self.style_name,
                progress_callback=self._on_progress,
                preview_callback=self._on_preview
            )
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"处理线程异常: {e}")
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, filename: str):
        self.progress.emit(current, total, filename)

    def _on_preview(self, filepath: str, image: Image.Image):
        self.preview.emit(filepath, image)

    def cancel(self):
        self.processor.cancel()


# ==================== 自定义复选框（带勾号）====================

class CheckableListItem(QWidget):
    """带复选框的列表项"""

    checked_changed = pyqtSignal(bool)

    def __init__(self, text: str, filepath: str, thumbnail: Optional[QPixmap] = None, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self._checked = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # 复选框
        self.checkbox = QCheckBox()
        self.checkbox.setFixedSize(22, 22)
        self.checkbox.stateChanged.connect(self._on_check_changed)
        layout.addWidget(self.checkbox)

        # 缩略图 - 尺寸提升2倍
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(96, 72)  # 原来是 48x36
        self.thumb_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border-radius: 4px;
                border: 1px solid #3d3d3d;
            }
        """)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if thumbnail:
            self.set_thumbnail(thumbnail)
        layout.addWidget(self.thumb_label)

        # 文件名
        self.name_label = QLabel(text)
        self.name_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        layout.addWidget(self.name_label, stretch=1)

    def set_thumbnail(self, pixmap: QPixmap):
        """设置缩略图"""
        scaled = pixmap.scaled(
            94, 70,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.thumb_label.setPixmap(scaled)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool):
        self._checked = checked
        self.checkbox.setChecked(checked)

    def _on_check_changed(self, state):
        self._checked = state == Qt.CheckState.Checked.value
        self.checked_changed.emit(self._checked)


# ==================== 图片列表组件 ====================

class ImageListWidget(QFrame):
    """图片列表组件，支持拖放和缩略图预览"""

    files_dropped = pyqtSignal(list)
    selection_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("ImageListWidget")

        self._file_items: dict[str, QListWidgetItem] = {}
        self._thumbnails: dict[str, QPixmap] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText(t("search_placeholder"))
        self.search_box.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_box)

        # 列表控件
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.setSpacing(2)
        layout.addWidget(self.list_widget)

        # 空状态提示
        self.empty_label = QLabel(t("drop_hint"))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #606060;
                font-size: 14px;
                padding: 50px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.empty_label)

        self._update_empty_state()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"#ImageListWidget {{ border: 2px dashed {LIGHTROOM_BLUE}; border-radius: 8px; }}")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).is_dir():
                files.extend(scan_images(path, recursive=True))
            elif path.lower().endswith(('.jpg', '.jpeg')):
                files.append(path)

        if files:
            self.files_dropped.emit(files)

    def add_files(self, files: list[str]) -> tuple[int, int]:
        """添加文件到列表，返回 (添加数量, 重复数量)"""
        existing_names = set(self._file_items.keys())
        added = 0
        duplicates = 0

        for filepath in files:
            filename = Path(filepath).name

            # 检查重复（基于文件名）
            if filename in existing_names:
                duplicates += 1
                continue

            # 创建列表项
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, filepath)
            item.setSizeHint(QSize(0, 84))  # 原来是 56，增加高度适应更大缩略图

            # 创建自定义 widget
            item_widget = CheckableListItem(filename, filepath)
            item_widget.checked_changed.connect(lambda checked, f=filepath: self._on_item_checked(f, checked))

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)

            self._file_items[filename] = item
            existing_names.add(filename)
            added += 1

            # 延迟加载缩略图
            QTimer.singleShot(50 * added, lambda fp=filepath, w=item_widget: self._load_thumbnail(fp, w))

        self._update_empty_state()
        return added, duplicates

    def _load_thumbnail(self, filepath: str, widget: CheckableListItem):
        """异步加载缩略图"""
        try:
            if filepath in self._thumbnails:
                widget.set_thumbnail(self._thumbnails[filepath])
                return

            image = Image.open(filepath)
            image.thumbnail((192, 144), Image.Resampling.LANCZOS)  # 原来是 96x72，提升2倍

            if image.mode != 'RGB':
                image = image.convert('RGB')

            qimage = QImage(
                image.tobytes(),
                image.width,
                image.height,
                image.width * 3,
                QImage.Format.Format_RGB888
            )
            pixmap = QPixmap.fromImage(qimage)

            self._thumbnails[filepath] = pixmap
            widget.set_thumbnail(pixmap)

        except Exception as e:
            logger.debug(f"加载缩略图失败: {e}")

    def _on_item_checked(self, filepath: str, checked: bool):
        """项目选中状态变化"""
        # 同步列表选择状态
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == filepath:
                item.setSelected(checked)
                break

    def get_all_files(self) -> list[str]:
        """获取所有文件路径"""
        return [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
            if not self.list_widget.item(i).isHidden()
        ]

    def get_selected_files(self) -> list[str]:
        """获取选中的文件路径（包括复选框选中的）"""
        selected = set()

        for item in self.list_widget.selectedItems():
            selected.add(item.data(Qt.ItemDataRole.UserRole))

        # 也检查复选框
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget and isinstance(widget, CheckableListItem) and widget.is_checked():
                selected.add(item.data(Qt.ItemDataRole.UserRole))

        return list(selected)

    def clear_files(self):
        """清空列表"""
        self.list_widget.clear()
        self._file_items.clear()
        self._thumbnails.clear()
        self._update_empty_state()

    def remove_selected(self):
        """移除选中项"""
        for item in self.list_widget.selectedItems():
            filepath = item.data(Qt.ItemDataRole.UserRole)
            filename = Path(filepath).name

            self._file_items.pop(filename, None)
            self._thumbnails.pop(filepath, None)
            self.list_widget.takeItem(self.list_widget.row(item))

        self._update_empty_state()

    def get_count(self) -> int:
        """获取文件数量"""
        return self.list_widget.count()

    def _filter_list(self, text: str):
        """根据搜索词过滤列表"""
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            filepath = item.data(Qt.ItemDataRole.UserRole)
            filename = Path(filepath).name.lower()
            item.setHidden(text not in filename)

    def _update_empty_state(self):
        """更新空状态显示"""
        has_items = self.list_widget.count() > 0
        self.empty_label.setVisible(not has_items)
        self.list_widget.setVisible(has_items)
        self.search_box.setVisible(has_items)

    def _on_selection_changed(self):
        """选择变化时发送信号"""
        selected = self.get_selected_files()
        self.selection_changed.emit(selected)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(LIGHTROOM_STYLE)

        remove_action = QAction(t("ctx_remove_selected"), self)
        remove_action.triggered.connect(self.remove_selected)
        menu.addAction(remove_action)

        menu.addSeparator()

        clear_action = QAction(t("ctx_clear_all"), self)
        clear_action.triggered.connect(self.clear_files)
        menu.addAction(clear_action)

        menu.exec(self.list_widget.mapToGlobal(pos))

    def update_texts(self):
        """更新界面文本"""
        self.search_box.setPlaceholderText(t("search_placeholder"))
        self.empty_label.setText(t("drop_hint"))


# ==================== 预览组件 ====================

class PreviewWidget(QFrame):
    """图片预览组件 - 高分辨率"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewPanel")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 预览标签
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border-radius: 10px;
            }
        """)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.preview_label)

        self._original_pixmap: QPixmap | None = None
        self._show_placeholder()

    def set_image(self, image: Image.Image):
        """设置预览图片"""
        if image.mode != 'RGB':
            image = image.convert('RGB')

        qimage = QImage(
            image.tobytes(),
            image.width,
            image.height,
            image.width * 3,
            QImage.Format.Format_RGB888
        )
        self._original_pixmap = QPixmap.fromImage(qimage)
        self._update_scaled_pixmap()

    def clear_image(self):
        """清除预览"""
        self._original_pixmap = None
        self._show_placeholder()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._original_pixmap:
            self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        """更新缩放后的图片"""
        if self._original_pixmap:
            available_size = self.preview_label.size()
            # 留出边距
            target_size = QSize(available_size.width() - 20, available_size.height() - 20)
            scaled = self._original_pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)

    def _show_placeholder(self):
        """显示占位符"""
        self.preview_label.setText("")
        self.preview_label.setPixmap(QPixmap())


# ==================== 语言选择对话框 ====================

class LanguageSelectDialog(QDialog):
    """首次运行语言选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Language / 选择语言")
        self.setFixedSize(400, 280)
        self.setStyleSheet(LIGHTROOM_STYLE)
        self.selected_language = "zh-CN"

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # 标题
        title = QLabel("Select Language / 选择语言")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # 说明
        desc = QLabel("Please select your preferred language:\n请选择您的首选语言：")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #a0a0a0; font-size: 13px;")
        layout.addWidget(desc)

        layout.addSpacing(10)

        # 语言选择
        self.language_combo = QComboBox()
        self.language_combo.setMinimumHeight(44)
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, code)
        layout.addWidget(self.language_combo)

        layout.addStretch()

        # 确认按钮
        confirm_btn = QPushButton("Confirm / 确定")
        confirm_btn.setObjectName("PrimaryButton")
        confirm_btn.setMinimumHeight(44)
        confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(confirm_btn)

    def _confirm(self):
        self.selected_language = self.language_combo.currentData()
        self.accept()

    def get_selected_language(self) -> str:
        return self.selected_language


# ==================== 设置对话框 ====================

class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config = config_manager.load()

        self.setWindowTitle(t("settings_title"))
        self.setMinimumSize(520, 620)
        self.setStyleSheet(LIGHTROOM_STYLE)

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # 使用滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # 语言设置
        lang_group = QGroupBox(t("settings_language"))
        lang_layout = QVBoxLayout(lang_group)
        lang_layout.setSpacing(12)

        self.language_combo = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, code)
        lang_layout.addWidget(self.language_combo)

        scroll_layout.addWidget(lang_group)

        # 时间源设置
        time_group = QGroupBox(t("settings_time_source"))
        time_layout = QVBoxLayout(time_group)
        time_layout.setSpacing(14)

        time_layout.addWidget(QLabel(t("settings_primary_source")))
        self.time_source_combo = QComboBox()
        self.time_source_combo.addItems([
            t("settings_exif"),
            t("settings_file_modified"),
            t("settings_file_created")
        ])
        time_layout.addWidget(self.time_source_combo)

        time_layout.addSpacing(8)

        self.fallback_check = QCheckBox(t("settings_fallback"))
        self.fallback_check.setChecked(True)
        time_layout.addWidget(self.fallback_check)

        scroll_layout.addWidget(time_group)

        # 输出设置
        output_group = QGroupBox(t("settings_output"))
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(14)

        self.same_dir_check = QCheckBox(t("settings_same_dir"))
        self.same_dir_check.setChecked(True)
        self.same_dir_check.toggled.connect(self._on_same_dir_toggled)
        output_layout.addWidget(self.same_dir_check)

        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(10)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(t("settings_output_dir"))
        self.output_dir_edit.setEnabled(False)
        dir_layout.addWidget(self.output_dir_edit)

        self.browse_btn = QPushButton(t("settings_browse"))
        self.browse_btn.setEnabled(False)
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(self.browse_btn)
        output_layout.addLayout(dir_layout)

        output_layout.addSpacing(8)

        output_layout.addWidget(QLabel(t("settings_filename_pattern")))
        self.filename_pattern_edit = QLineEdit()
        self.filename_pattern_edit.setText("{original}_stamped")
        self.filename_pattern_edit.setToolTip(t("settings_filename_tooltip"))
        output_layout.addWidget(self.filename_pattern_edit)

        output_layout.addSpacing(8)

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel(t("settings_jpeg_quality")))
        quality_layout.addStretch()
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setSuffix(" %")
        self.quality_spin.setFixedWidth(100)
        quality_layout.addWidget(self.quality_spin)
        output_layout.addLayout(quality_layout)

        output_layout.addSpacing(8)

        self.preserve_exif_check = QCheckBox(t("settings_preserve_exif"))
        self.preserve_exif_check.setChecked(True)
        output_layout.addWidget(self.preserve_exif_check)

        self.overwrite_check = QCheckBox(t("settings_overwrite"))
        output_layout.addWidget(self.overwrite_check)

        scroll_layout.addWidget(output_group)

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self.reset_btn = QPushButton(t("settings_reset"))
        self.reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(self.reset_btn)

        self.save_btn = QPushButton(t("settings_save"))
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setMinimumWidth(100)
        self.save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _load_settings(self):
        """加载设置"""
        # 语言
        current_lang = self.config.get('general', {}).get('language', 'zh-CN')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break

        primary = self.config.get('time_source', {}).get('primary', 'exif')
        source_map = {'exif': 0, 'file_modified': 1, 'file_created': 2}
        self.time_source_combo.setCurrentIndex(source_map.get(primary, 0))

        self.fallback_check.setChecked(
            self.config.get('time_source', {}).get('fallback_enabled', True)
        )

        output = self.config.get('output', {})
        self.same_dir_check.setChecked(output.get('same_directory', True))
        self.output_dir_edit.setText(output.get('custom_directory', ''))
        self.filename_pattern_edit.setText(output.get('filename_pattern', '{original}_stamped'))
        self.quality_spin.setValue(output.get('jpeg_quality', 95))
        self.preserve_exif_check.setChecked(output.get('preserve_exif', True))
        self.overwrite_check.setChecked(output.get('overwrite_existing', False))

    def _save_and_close(self):
        """保存并关闭"""
        # 语言
        new_lang = self.language_combo.currentData()
        self.config['general']['language'] = new_lang
        I18n.set_language(new_lang)

        source_map = {0: 'exif', 1: 'file_modified', 2: 'file_created'}
        self.config['time_source'] = {
            'primary': source_map.get(self.time_source_combo.currentIndex(), 'exif'),
            'fallback_enabled': self.fallback_check.isChecked(),
            'fallback_to': 'file_modified'
        }

        self.config['output'] = {
            'same_directory': self.same_dir_check.isChecked(),
            'custom_directory': self.output_dir_edit.text(),
            'filename_pattern': self.filename_pattern_edit.text() or '{original}_stamped',
            'jpeg_quality': self.quality_spin.value(),
            'preserve_exif': self.preserve_exif_check.isChecked(),
            'overwrite_existing': self.overwrite_check.isChecked()
        }

        self.config_manager.save(self.config)
        self.accept()

    def _reset_settings(self):
        """恢复默认"""
        self.config = self.config_manager.get_default()
        self._load_settings()

    def _on_same_dir_toggled(self, checked: bool):
        self.output_dir_edit.setEnabled(not checked)
        self.browse_btn.setEnabled(not checked)

    def _browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, t("settings_browse"))
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def get_config(self) -> dict:
        """获取当前配置"""
        return self.config


# ==================== 关于对话框 ====================

class AboutDialog(QDialog):
    """关于对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("about_title"))
        self.setFixedSize(450, 600)
        self.setStyleSheet(LIGHTROOM_STYLE)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # Logo - 使用 QLabel 并确保不被裁剪
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setMinimumHeight(140)
        logo_label.setMaximumHeight(140)
        logo_path = get_base_path() / "assets" / "logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(
                QSize(128, 128),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("📷")
            logo_label.setStyleSheet("font-size: 72px;")
        layout.addWidget(logo_label)

        layout.addSpacing(20)

        # 软件名称
        name_label = QLabel("Photo Timestamper")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
                background: transparent;
            }
        """)
        name_label.setFixedHeight(36)
        layout.addWidget(name_label)

        layout.addSpacing(8)

        # 中文名
        cn_name_label = QLabel(t("app_name_cn"))
        cn_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cn_name_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #808080;
                background: transparent;
            }
        """)
        cn_name_label.setFixedHeight(24)
        layout.addWidget(cn_name_label)

        layout.addSpacing(12)

        # 版本
        version_label = QLabel(t("about_version", version=__version__))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #a0a0a0; font-size: 13px; background: transparent;")
        version_label.setFixedHeight(24)
        layout.addWidget(version_label)

        layout.addSpacing(24)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3d3d3d;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        layout.addSpacing(24)

        # 作者
        author_label = QLabel(t("about_author", author=__author__))
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_label.setStyleSheet("color: #c0c0c0; font-size: 14px; background: transparent;")
        author_label.setFixedHeight(28)
        layout.addWidget(author_label)

        layout.addSpacing(16)

        # 协作者标题
        collab_title = QLabel(t("about_collaborators"))
        collab_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collab_title.setStyleSheet("color: #808080; font-size: 11px; background: transparent;")
        collab_title.setFixedHeight(20)
        layout.addWidget(collab_title)

        layout.addSpacing(6)

        # 协作者名单
        collab_names = QLabel(" • ".join(__collaborators__))
        collab_names.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collab_names.setStyleSheet("color: #a0a0a0; font-size: 13px; background: transparent;")
        collab_names.setFixedHeight(24)
        layout.addWidget(collab_names)

        layout.addSpacing(16)

        # 许可证
        license_label = QLabel(t("about_license"))
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setStyleSheet("color: #808080; font-size: 12px; background: transparent;")
        license_label.setFixedHeight(24)
        layout.addWidget(license_label)

        layout.addStretch()

        # GitHub 链接
        github_btn = QPushButton(t("about_github"))
        github_btn.setObjectName("PrimaryButton")
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.setFixedHeight(44)
        github_btn.clicked.connect(self._open_github)
        layout.addWidget(github_btn)

        layout.addSpacing(12)

        # 关闭按钮
        close_btn = QPushButton(t("about_close"))
        close_btn.setFixedHeight(44)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _open_github(self):
        import webbrowser
        webbrowser.open("https://github.com/Water-Run/photo-timestamper")


# ==================== 导入对话框 ====================

class ImportDialog(QDialog):
    """导入图片对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("import_title"))
        self.setFixedSize(420, 240)
        self.setStyleSheet(LIGHTROOM_STYLE)

        self.selected_files: list[str] = []
        self.recursive = True

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        # 说明
        info_label = QLabel(t("import_desc"))
        info_label.setStyleSheet("font-size: 14px; color: #e0e0e0;")
        layout.addWidget(info_label)

        # 递归选项
        self.recursive_check = QCheckBox(t("import_recursive"))
        self.recursive_check.setChecked(True)
        layout.addWidget(self.recursive_check)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.file_btn = QPushButton(t("import_select_files"))
        self.file_btn.setMinimumHeight(40)
        self.file_btn.clicked.connect(self._select_files)
        btn_layout.addWidget(self.file_btn)

        self.folder_btn = QPushButton(t("import_select_folder"))
        self.folder_btn.setObjectName("PrimaryButton")
        self.folder_btn.setMinimumHeight(40)
        self.folder_btn.clicked.connect(self._select_folder)
        btn_layout.addWidget(self.folder_btn)

        layout.addLayout(btn_layout)

        cancel_btn = QPushButton(t("import_cancel"))
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            t("import_select_files"),
            "",
            t("import_filter")
        )
        if files:
            self.selected_files = files
            self.recursive = self.recursive_check.isChecked()
            self.accept()

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("import_select_folder"))
        if folder:
            recursive = self.recursive_check.isChecked()
            self.selected_files = scan_images(folder, recursive=recursive)
            self.recursive = recursive
            self.accept()

    def get_files(self) -> list[str]:
        return self.selected_files


# ==================== 主窗口 ====================

class MainWindow(QMainWindow):
    """主窗口 - Lightroom 风格三栏布局"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.style_manager = StyleManager()

        # 设置语言
        saved_lang = self.config.get('general', {}).get('language', '')
        if saved_lang:
            I18n.set_language(saved_lang)

        self.processing_thread: ProcessingThread | None = None
        self._has_unsaved_content = False

        self._init_ui()
        self._setup_shortcuts()
        self._load_ui_state()

        # 首次运行检查
        if self.config_manager.is_first_run():
            QTimer.singleShot(100, self._show_language_selection)

    def _init_ui(self):
        self.setWindowTitle(t("app_name"))
        self.setMinimumSize(1280, 720)

        # 设置应用图标
        icon_path = get_base_path() / "assets" / "logo.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            icon_path = get_base_path() / "assets" / "logo.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))

        # 应用样式
        self.setStyleSheet(LIGHTROOM_STYLE)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建三栏布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # 左栏 - 控制面板
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # 中栏 - 原图预览
        self.original_preview = self._create_preview_panel(t("preview_original"))
        splitter.addWidget(self.original_preview)

        # 右栏 - 效果预览
        self.result_preview = self._create_preview_panel(t("preview_result"))
        splitter.addWidget(self.result_preview)

        # 设置分割比例
        splitter.setSizes([300, 490, 490])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        # 状态栏
        self.statusBar().showMessage(t("msg_ready"))

    def _setup_shortcuts(self):
        """设置快捷键"""
        # 导入 Ctrl+I
        import_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        import_shortcut.activated.connect(self._show_import_dialog)

        # 清空 Ctrl+Shift+C
        clear_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        clear_shortcut.activated.connect(self._clear_files)

        # 处理 Ctrl+Enter
        process_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        process_shortcut.activated.connect(self._start_processing)

        # 设置 Ctrl+,
        settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        settings_shortcut.activated.connect(self._show_settings)

        # 退出 Ctrl+Q
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)

        # 全选 Ctrl+A
        select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        select_all_shortcut.activated.connect(self._select_all_images)

        # 删除选中 Delete
        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self._remove_selected)

    def _create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        panel.setObjectName("LeftPanel")
        panel.setFixedWidth(300)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 顶部按钮栏
        top_btn_layout = QHBoxLayout()
        top_btn_layout.setSpacing(8)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setFixedHeight(36)
        self.settings_btn.setToolTip(t("tooltip_settings"))
        self.settings_btn.clicked.connect(self._show_settings)
        top_btn_layout.addWidget(self.settings_btn)

        self.about_btn = QPushButton("关于")
        self.about_btn.setFixedHeight(36)
        self.about_btn.clicked.connect(self._show_about)
        top_btn_layout.addWidget(self.about_btn)

        top_btn_layout.addStretch()
        layout.addLayout(top_btn_layout)

        # === 图片列表（移到前面）===
        list_label = QLabel(t("panel_image_list"))
        list_label.setObjectName("PanelTitle")
        layout.addWidget(list_label)

        self.image_list = ImageListWidget()
        self.image_list.files_dropped.connect(self._on_files_dropped)
        self.image_list.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self.image_list, stretch=1)

        # 列表信息和清空按钮
        list_info_layout = QHBoxLayout()
        list_info_layout.setSpacing(8)

        self.list_info_label = QLabel(t("image_count", count=0))
        self.list_info_label.setStyleSheet("color: #606060; font-size: 11px;")
        list_info_layout.addWidget(self.list_info_label)

        list_info_layout.addStretch()

        self.clear_btn = QPushButton(t("btn_clear_list"))
        self.clear_btn.setFixedHeight(32)
        self.clear_btn.setToolTip(t("tooltip_clear"))
        self.clear_btn.clicked.connect(self._clear_files)
        list_info_layout.addWidget(self.clear_btn)

        layout.addLayout(list_info_layout)

        layout.addSpacing(8)

        # === 导入区域（移到后面）===
        import_label = QLabel(t("panel_import"))
        import_label.setObjectName("PanelTitle")
        layout.addWidget(import_label)

        self.import_btn = QPushButton(t("btn_add_images"))
        self.import_btn.setObjectName("PrimaryButton")
        self.import_btn.setMinimumHeight(44)
        self.import_btn.setToolTip(t("tooltip_import"))
        self.import_btn.clicked.connect(self._show_import_dialog)
        layout.addWidget(self.import_btn)

        layout.addSpacing(8)

        # 水印样式
        style_label = QLabel(t("panel_watermark_style"))
        style_label.setObjectName("PanelTitle")
        layout.addWidget(style_label)

        self.style_combo = QComboBox()
        self.style_combo.setMinimumHeight(44)
        self._populate_styles()
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        layout.addWidget(self.style_combo)

        layout.addSpacing(16)

        # 处理进度
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)

        self.progress_label = QLabel(t("processing"))
        self.progress_label.setStyleSheet("color: #a0a0a0;")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton(t("btn_cancel"))
        self.cancel_btn.setObjectName("DangerButton")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        progress_layout.addWidget(self.cancel_btn)

        self.progress_widget.setVisible(False)
        layout.addWidget(self.progress_widget)

        # 执行按钮
        self.process_btn = QPushButton(t("btn_process_selected"))
        self.process_btn.setObjectName("PrimaryButton")
        self.process_btn.setMinimumHeight(48)
        self.process_btn.setToolTip(t("tooltip_process"))
        self.process_btn.clicked.connect(self._start_processing)
        layout.addWidget(self.process_btn)

        return panel

    def _create_preview_panel(self, title: str) -> QWidget:
        """创建预览面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 标题
        title_label = QLabel(title)
        title_label.setObjectName("PanelTitle")
        layout.addWidget(title_label)

        # 存储标题标签引用
        panel.title_label = title_label

        # 预览区域
        preview = PreviewWidget()
        layout.addWidget(preview, stretch=1)

        # 存储预览控件引用
        panel.preview_widget = preview

        return panel

    def _populate_styles(self):
        """填充样式下拉列表"""
        styles = self.style_manager.list_styles()
        self.style_combo.clear()
        self.style_combo.addItems(styles)

        last_style = self.config.get('ui', {}).get('last_style', '佳能')
        if last_style in styles:
            self.style_combo.setCurrentText(last_style)

    def _show_language_selection(self):
        """显示语言选择对话框"""
        dialog = LanguageSelectDialog(self)
        if dialog.exec():
            selected_lang = dialog.get_selected_language()
            I18n.set_language(selected_lang)
            self.config['general']['language'] = selected_lang
            self.config_manager.save(self.config)
            self.config_manager.set_first_run_complete()
            self._update_ui_texts()

    def _show_import_dialog(self):
        """显示导入对话框"""
        dialog = ImportDialog(self)
        if dialog.exec():
            files = dialog.get_files()
            if files:
                added, duplicates = self.image_list.add_files(files)
                self._update_list_info()
                self._has_unsaved_content = True

                if duplicates > 0:
                    self.statusBar().showMessage(
                        f"{t('msg_added_images', count=added)} | {t('msg_duplicate_skipped', count=duplicates)}"
                    )
                else:
                    self.statusBar().showMessage(t('msg_added_images', count=added))

    def _show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self.config_manager, self)
        if dialog.exec():
            self.config = self.config_manager.load()
            self._update_ui_texts()

    def _show_about(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _on_files_dropped(self, files: list[str]):
        """处理拖放的文件"""
        added, duplicates = self.image_list.add_files(files)
        self._update_list_info()
        self._has_unsaved_content = True

        if duplicates > 0:
            self.statusBar().showMessage(
                f"{t('msg_added_images', count=added)} | {t('msg_duplicate_skipped', count=duplicates)}"
            )
        else:
            self.statusBar().showMessage(t('msg_added_images', count=added))

    def _on_selection_changed(self, selected: list[str]):
        """选择变化时更新预览"""
        if selected:
            self._update_preview(selected[0])
        else:
            self.original_preview.preview_widget.clear_image()
            self.result_preview.preview_widget.clear_image()

    def _on_style_changed(self, style_name: str):
        """样式变化时更新预览"""
        self.config['ui']['last_style'] = style_name
        self.config_manager.save(self.config)

        selected = self.image_list.get_selected_files()
        if selected:
            self._update_preview(selected[0])

    def _update_preview(self, filepath: str):
        """更新预览 - 高分辨率"""
        try:
            # 显示原图
            image = Image.open(filepath)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # 原图预览 - 提升3倍分辨率
            original_preview = image.copy()
            original_preview.thumbnail((4800, 3600), Image.Resampling.LANCZOS)  # 原来是 1600x1200
            self.original_preview.preview_widget.set_image(original_preview)

            # 效果预览
            style_name = self.style_combo.currentText()
            style = self.style_manager.load_style(style_name)

            extractor = TimeExtractor(
                primary=self.config.get('time_source', {}).get('primary', 'exif'),
                fallback_enabled=self.config.get('time_source', {}).get('fallback_enabled', True),
                fallback_to=self.config.get('time_source', {}).get('fallback_to', 'file_modified')
            )
            timestamp = extractor.extract(filepath)

            renderer = WatermarkRenderer(style, self.style_manager.fonts_dir)
            result_preview = renderer.render_preview(image, timestamp, (4800, 3600))  # 原来是 1600x1200
            self.result_preview.preview_widget.set_image(result_preview)

        except Exception as e:
            logger.error(f"生成预览失败: {e}")
            self.original_preview.preview_widget.clear_image()
            self.result_preview.preview_widget.clear_image()

    def _clear_files(self):
        """清空文件列表"""
        self.image_list.clear_files()
        self.original_preview.preview_widget.clear_image()
        self.result_preview.preview_widget.clear_image()
        self._update_list_info()
        self._has_unsaved_content = False

    def _select_all_images(self):
        """全选图片"""
        self.image_list.list_widget.selectAll()

    def _remove_selected(self):
        """移除选中图片"""
        self.image_list.remove_selected()
        self._update_list_info()

    def _update_list_info(self):
        """更新列表信息"""
        count = self.image_list.get_count()
        self.list_info_label.setText(t("image_count", count=count))

    def _start_processing(self):
        """开始处理"""
        selected = self.image_list.get_selected_files()
        if not selected:
            # 如果没有选中，处理全部
            selected = self.image_list.get_all_files()

        if not selected:
            QMessageBox.warning(self, t("app_name"), t("msg_no_images"))
            return

        style_name = self.style_combo.currentText()

        processor = BatchProcessor(self.config, self.style_manager)

        self.processing_thread = ProcessingThread(processor, selected, style_name)
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.preview.connect(self._on_processing_preview)
        self.processing_thread.finished.connect(self._on_finished)
        self.processing_thread.error.connect(self._on_error)

        self._set_processing_state(True)
        self.processing_thread.start()

    def _cancel_processing(self):
        """取消处理"""
        if self.processing_thread:
            self.processing_thread.cancel()
            self.statusBar().showMessage(t("cancelling"))

    def _on_progress(self, current: int, total: int, filename: str):
        """更新进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(t("processing_progress", current=current, total=total, filename=filename))
        self.statusBar().showMessage(t("processing_progress", current=current, total=total, filename=filename))

    def _on_processing_preview(self, filepath: str, image: Image.Image):
        """处理时更新预览"""
        self.result_preview.preview_widget.set_image(image)

    def _on_finished(self, results: dict):
        """处理完成"""
        self._set_processing_state(False)

        success = results.get('success', 0)
        failed = results.get('failed', 0)

        self.statusBar().showMessage(t("msg_process_complete", success=success, failed=failed))

        if failed > 0:
            errors = results.get('errors', [])
            error_text = '\n'.join(errors[:10])
            if len(errors) > 10:
                error_text += '\n' + t("msg_more_errors", count=len(errors) - 10)

            QMessageBox.warning(
                self,
                t("app_name"),
                f"{t('msg_partial_success', success=success, failed=failed)}\n\n{t('msg_error_details')}:\n{error_text}"
            )
        else:
            QMessageBox.information(self, t("app_name"), t("msg_success", count=success))

    def _on_error(self, error: str):
        """处理错误"""
        self._set_processing_state(False)
        self.statusBar().showMessage(t("msg_process_error"))
        QMessageBox.critical(self, t("app_name"), f"{t('msg_process_error')}: {error}")

    def _set_processing_state(self, processing: bool):
        """设置处理状态"""
        self.process_btn.setVisible(not processing)
        self.progress_widget.setVisible(processing)
        self.import_btn.setEnabled(not processing)
        self.clear_btn.setEnabled(not processing)
        self.style_combo.setEnabled(not processing)
        self.settings_btn.setEnabled(not processing)

        if not processing:
            self.progress_bar.setValue(0)

    def _update_ui_texts(self):
        """更新所有 UI 文本（语言切换时）"""
        self.setWindowTitle(t("app_name"))

        # 更新面板标题（需要查找所有 PanelTitle 标签）
        self.import_btn.setText(t("btn_add_images"))
        self.clear_btn.setText(t("btn_clear_list"))
        self.process_btn.setText(t("btn_process_selected"))
        self.cancel_btn.setText(t("btn_cancel"))
        self.progress_label.setText(t("processing"))

        # 更新图片列表
        self.image_list.update_texts()
        self._update_list_info()

        # 更新预览面板标题
        if hasattr(self.original_preview, 'title_label'):
            self.original_preview.title_label.setText(t("preview_original"))
        if hasattr(self.result_preview, 'title_label'):
            self.result_preview.title_label.setText(t("preview_result"))

        # 更新工具提示
        self.import_btn.setToolTip(t("tooltip_import"))
        self.clear_btn.setToolTip(t("tooltip_clear"))
        self.process_btn.setToolTip(t("tooltip_process"))
        self.settings_btn.setToolTip(t("tooltip_settings"))

        self.statusBar().showMessage(t("msg_ready"))

    def _load_ui_state(self):
        """加载UI状态"""
        geometry = self.config.get('ui', {}).get('window_geometry', '')
        if geometry:
            try:
                self.restoreGeometry(bytes.fromhex(geometry))
            except:
                pass

    def _save_ui_state(self):
        """保存UI状态"""
        self.config['ui']['window_geometry'] = self.saveGeometry().toHex().data().decode()
        self.config_manager.save(self.config)

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 检查是否正在处理
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self,
                t("msg_confirm_exit"),
                t("msg_exit_processing"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.processing_thread.cancel()
            self.processing_thread.wait()

        # 检查是否有未保存的内容
        elif self._has_unsaved_content and self.image_list.get_count() > 0:
            reply = QMessageBox.question(
                self,
                t("msg_confirm_exit"),
                t("msg_exit_unsaved"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        self._save_ui_state()
        event.accept()


def run_app():
    """运行应用程序"""
    app = QApplication(sys.argv)
    app.setApplicationName("Photo Timestamper")
    app.setOrganizationName("PhotoTimestamper")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
# ui.py
"""
Photo-Timestamper PyQt6 用户界面
Lightroom 风格专业界面 - 重构版 v1.2
"""

import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QMessageBox,
    QCheckBox, QLineEdit, QSpinBox, QGroupBox, QDialog,
    QAbstractItemView, QMenu, QScrollArea, QSizePolicy,
    QTabWidget, QRadioButton, QButtonGroup
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

LIGHTROOM_BLUE = "#0a84ff"
LIGHTROOM_BLUE_HOVER = "#409cff"
LIGHTROOM_BLUE_PRESSED = "#0066cc"
CHECK_GREEN = "#34c759"

LIGHTROOM_STYLE = f"""
/* 主窗口背景 */
QMainWindow {{
    background-color: #1e1e1e;
}}

QWidget {{
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Microsoft YaHei", "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 12px;
}}

/* 菜单栏 */
QMenuBar {{
    background-color: #2d2d2d;
    border-bottom: 1px solid #3d3d3d;
    padding: 2px 0;
    spacing: 0;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
    margin: 2px 2px;
}}

QMenuBar::item:selected {{
    background-color: #404040;
}}

QMenuBar::item:pressed {{
    background-color: {LIGHTROOM_BLUE};
}}

QMenu {{
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 32px 8px 12px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {LIGHTROOM_BLUE};
}}

QMenu::separator {{
    height: 1px;
    background-color: #3d3d3d;
    margin: 6px 8px;
}}

/* 分割器 */
QSplitter::handle {{
    background-color: #3d3d3d;
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

/* 左侧面板 */
#LeftPanel {{
    background-color: #252525;
    border-right: 1px solid #3d3d3d;
}}

/* 面板标题 */
#PanelTitle {{
    color: #909090;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 8px 0 6px 0;
    background-color: transparent;
}}

/* 分组框 */
QGroupBox {{
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
    font-size: 11px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #a0a0a0;
    background-color: #2d2d2d;
}}

/* 标签页 */
QTabWidget::pane {{
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    padding: 12px;
}}

QTabBar::tab {{
    background-color: #353535;
    border: 1px solid #3d3d3d;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 8px 20px;
    margin-right: 2px;
    color: #a0a0a0;
}}

QTabBar::tab:selected {{
    background-color: #2d2d2d;
    color: #ffffff;
}}

QTabBar::tab:hover:!selected {{
    background-color: #404040;
}}

/* 按钮样式 */
QPushButton {{
    background-color: #3d3d3d;
    border: 1px solid #4d4d4d;
    border-radius: 4px;
    padding: 6px 12px;
    color: #e0e0e0;
    font-weight: 500;
    min-height: 20px;
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

/* 主要操作按钮 */
QPushButton#PrimaryButton {{
    background-color: {LIGHTROOM_BLUE};
    border: none;
    color: white;
    font-weight: 600;
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

/* 小型按钮 */
QPushButton#SmallButton {{
    padding: 4px 10px;
    font-size: 11px;
    min-height: 18px;
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
    border-radius: 4px;
    padding: 6px 10px;
    padding-right: 28px;
    color: #e0e0e0;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: #5d5d5d;
}}

QComboBox:focus {{
    border-color: {LIGHTROOM_BLUE};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #808080;
    margin-right: 8px;
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
    padding: 8px 12px;
    min-height: 24px;
    border-radius: 4px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: #404040;
}}

/* 列表控件 */
QListWidget {{
    background-color: #2a2a2a;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    outline: none;
    padding: 4px;
}}

QListWidget::item {{
    background-color: transparent;
    border-radius: 4px;
    padding: 2px 4px;
    margin: 1px 0;
}}

QListWidget::item:hover {{
    background-color: #353535;
}}

QListWidget::item:selected {{
    background-color: #404040;
}}

/* 滚动条 */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: #4d4d4d;
    min-height: 30px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #5d5d5d;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: #4d4d4d;
    min-width: 30px;
    border-radius: 5px;
    margin: 2px;
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
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {LIGHTROOM_BLUE};
    border-radius: 4px;
}}

/* 复选框 */
QCheckBox {{
    spacing: 8px;
    color: #e0e0e0;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #4d4d4d;
    background-color: #2d2d2d;
}}

QCheckBox::indicator:hover {{
    border-color: #5d5d5d;
}}

QCheckBox::indicator:checked {{
    background-color: {LIGHTROOM_BLUE};
    border-color: {LIGHTROOM_BLUE};
}}

/* 单选框 */
QRadioButton {{
    spacing: 8px;
    color: #e0e0e0;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1px solid #4d4d4d;
    background-color: #2d2d2d;
}}

QRadioButton::indicator:hover {{
    border-color: #5d5d5d;
}}

QRadioButton::indicator:checked {{
    background-color: {LIGHTROOM_BLUE};
    border-color: {LIGHTROOM_BLUE};
}}

/* 输入框 */
QLineEdit {{
    background-color: #2d2d2d;
    border: 1px solid #4d4d4d;
    border-radius: 4px;
    padding: 6px 10px;
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
    border-radius: 4px;
    padding: 6px 10px;
    color: #e0e0e0;
    min-height: 20px;
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
    width: 20px;
    border-radius: 2px;
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

/* 预览区域 */
#PreviewPanel {{
    background-color: #1a1a1a;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
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
    padding: 4px 12px;
    font-size: 11px;
}}

/* 工具提示 */
QToolTip {{
    background-color: #3d3d3d;
    border: 1px solid #4d4d4d;
    border-radius: 4px;
    padding: 6px 10px;
    color: #e0e0e0;
}}

/* 搜索框样式 */
#SearchBox {{
    background-color: #2d2d2d;
    border: 1px solid #4d4d4d;
    border-radius: 4px;
    padding: 6px 10px;
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


# ==================== 自定义勾选框绘制 ====================

class CheckmarkWidget(QWidget):
    """自定义勾选标记组件"""
    
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def is_checked(self) -> bool:
        return self._checked
    
    def set_checked(self, checked: bool):
        self._checked = checked
        self.update()
    
    def toggle(self):
        self._checked = not self._checked
        self.update()
        self.clicked.emit()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制圆形背景
        rect = self.rect().adjusted(2, 2, -2, -2)
        
        if self._checked:
            # 已勾选：绿色填充
            painter.setBrush(QBrush(QColor(CHECK_GREEN)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(rect)
            
            # 绘制白色勾号
            painter.setPen(QPen(QColor("#ffffff"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            
            # 勾号路径
            cx, cy = rect.center().x(), rect.center().y()
            # 勾号的三个点
            p1_x, p1_y = cx - 5, cy
            p2_x, p2_y = cx - 1, cy + 4
            p3_x, p3_y = cx + 6, cy - 4
            
            painter.drawLine(int(p1_x), int(p1_y), int(p2_x), int(p2_y))
            painter.drawLine(int(p2_x), int(p2_y), int(p3_x), int(p3_y))
        else:
            # 未勾选：空心圆
            painter.setBrush(QBrush(QColor("#3d3d3d")))
            painter.setPen(QPen(QColor("#5d5d5d"), 2))
            painter.drawEllipse(rect)


# ==================== 列表项组件 ====================

class ImageListItem(QWidget):
    """图片列表项 - 带明显的勾选状态"""

    checked_changed = pyqtSignal(str, bool)

    def __init__(self, filename: str, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.filename = filename
        self._thumbnail: QPixmap | None = None

        self.setFixedHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        # 勾选标记
        self.checkmark = CheckmarkWidget()
        self.checkmark.clicked.connect(self._on_checkmark_clicked)
        layout.addWidget(self.checkmark)

        # 缩略图
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(72, 54)
        self.thumb_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border-radius: 3px;
                border: 1px solid #3d3d3d;
            }
        """)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumb_label)

        # 文件名
        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        self.name_label.setWordWrap(False)
        layout.addWidget(self.name_label, stretch=1)

    def set_thumbnail(self, pixmap: QPixmap):
        """设置缩略图"""
        self._thumbnail = pixmap
        scaled = pixmap.scaled(
            70, 52,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.thumb_label.setPixmap(scaled)

    def is_checked(self) -> bool:
        return self.checkmark.is_checked()

    def set_checked(self, checked: bool):
        if self.checkmark.is_checked() != checked:
            self.checkmark.set_checked(checked)
            self.checked_changed.emit(self.filepath, checked)

    def toggle_checked(self):
        self.checkmark.toggle()

    def _on_checkmark_clicked(self):
        self.checked_changed.emit(self.filepath, self.checkmark.is_checked())


# ==================== 图片列表组件 ====================

class ImageListWidget(QFrame):
    """图片列表组件"""

    files_dropped = pyqtSignal(list)
    selection_changed = pyqtSignal(list)
    check_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("ImageListWidget")

        self._file_items: dict[str, QListWidgetItem] = {}
        self._item_widgets: dict[str, ImageListItem] = {}
        self._thumbnails: dict[str, QPixmap] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

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
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.setSpacing(1)
        layout.addWidget(self.list_widget)

        # 空状态提示
        self.empty_label = QLabel(t("drop_hint"))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #606060;
                font-size: 13px;
                padding: 40px;
                line-height: 1.8;
            }
        """)
        layout.addWidget(self.empty_label)

        self._update_empty_state()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"#ImageListWidget {{ border: 2px dashed {LIGHTROOM_BLUE}; border-radius: 6px; }}")

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
        """添加文件到列表"""
        existing = set(self._file_items.keys())
        added = 0
        duplicates = 0

        for filepath in files:
            filename = Path(filepath).name

            if filepath in existing or filename in [Path(p).name for p in existing]:
                duplicates += 1
                continue

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, filepath)
            item.setSizeHint(QSize(0, 66))

            item_widget = ImageListItem(filename, filepath)
            item_widget.checked_changed.connect(self._on_item_checked)

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)

            self._file_items[filepath] = item
            self._item_widgets[filepath] = item_widget
            existing.add(filepath)
            added += 1

            # 延迟加载缩略图
            QTimer.singleShot(30 * added, lambda fp=filepath, w=item_widget: self._load_thumbnail(fp, w))

        self._update_empty_state()
        return added, duplicates

    def _load_thumbnail(self, filepath: str, widget: ImageListItem):
        """异步加载缩略图"""
        try:
            if filepath in self._thumbnails:
                widget.set_thumbnail(self._thumbnails[filepath])
                return

            image = Image.open(filepath)
            image.thumbnail((144, 108), Image.Resampling.LANCZOS)

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
        """项目勾选状态变化"""
        self.check_changed.emit()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击切换勾选状态"""
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if filepath in self._item_widgets:
            self._item_widgets[filepath].toggle_checked()

    def get_all_files(self) -> list[str]:
        """获取所有文件路径"""
        return [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
            if not self.list_widget.item(i).isHidden()
        ]

    def get_checked_files(self) -> list[str]:
        """获取已勾选的文件"""
        checked = []
        for filepath, widget in self._item_widgets.items():
            if widget.is_checked():
                checked.append(filepath)
        return checked

    def get_selected_files(self) -> list[str]:
        """获取选中的文件（用于预览）"""
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.list_widget.selectedItems()
        ]

    def get_checked_count(self) -> int:
        """获取已勾选数量"""
        return len(self.get_checked_files())

    def check_all(self):
        """勾选所有"""
        for widget in self._item_widgets.values():
            widget.set_checked(True)
        self.check_changed.emit()

    def uncheck_all(self):
        """取消所有勾选"""
        for widget in self._item_widgets.values():
            widget.set_checked(False)
        self.check_changed.emit()

    def check_selected(self):
        """勾选选中项"""
        for item in self.list_widget.selectedItems():
            filepath = item.data(Qt.ItemDataRole.UserRole)
            if filepath in self._item_widgets:
                self._item_widgets[filepath].set_checked(True)
        self.check_changed.emit()

    def uncheck_selected(self):
        """取消勾选选中项"""
        for item in self.list_widget.selectedItems():
            filepath = item.data(Qt.ItemDataRole.UserRole)
            if filepath in self._item_widgets:
                self._item_widgets[filepath].set_checked(False)
        self.check_changed.emit()

    def clear_files(self):
        """清空列表"""
        self.list_widget.clear()
        self._file_items.clear()
        self._item_widgets.clear()
        self._thumbnails.clear()
        self._update_empty_state()

    def remove_selected(self):
        """移除选中项"""
        for item in self.list_widget.selectedItems():
            filepath = item.data(Qt.ItemDataRole.UserRole)
            self._file_items.pop(filepath, None)
            self._item_widgets.pop(filepath, None)
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

        # 勾选操作
        check_action = QAction(t("ctx_check_selected"), self)
        check_action.triggered.connect(self.check_selected)
        menu.addAction(check_action)

        uncheck_action = QAction(t("ctx_uncheck_selected"), self)
        uncheck_action.triggered.connect(self.uncheck_selected)
        menu.addAction(uncheck_action)

        menu.addSeparator()

        # 选择操作
        select_all_action = QAction(t("ctx_select_all"), self)
        select_all_action.triggered.connect(self.list_widget.selectAll)
        menu.addAction(select_all_action)

        deselect_action = QAction(t("ctx_deselect_all"), self)
        deselect_action.triggered.connect(self.list_widget.clearSelection)
        menu.addAction(deselect_action)

        menu.addSeparator()

        # 文件操作
        item = self.list_widget.itemAt(pos)
        if item:
            filepath = item.data(Qt.ItemDataRole.UserRole)

            open_file_action = QAction(t("ctx_open_file"), self)
            open_file_action.triggered.connect(lambda: self._open_file(filepath))
            menu.addAction(open_file_action)

            open_folder_action = QAction(t("ctx_open_folder"), self)
            open_folder_action.triggered.connect(lambda: self._open_folder(filepath))
            menu.addAction(open_folder_action)

            menu.addSeparator()

        remove_action = QAction(t("ctx_remove_selected"), self)
        remove_action.triggered.connect(self.remove_selected)
        menu.addAction(remove_action)

        clear_action = QAction(t("ctx_clear_all"), self)
        clear_action.triggered.connect(self.clear_files)
        menu.addAction(clear_action)

        menu.exec(self.list_widget.mapToGlobal(pos))

    def _open_file(self, filepath: str):
        """打开文件"""
        try:
            if sys.platform == 'win32':
                os.startfile(filepath)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filepath])
            else:
                subprocess.run(['xdg-open', filepath])
        except Exception as e:
            logger.error(f"打开文件失败: {e}")

    def _open_folder(self, filepath: str):
        """打开所在文件夹"""
        try:
            folder = str(Path(filepath).parent)
            if sys.platform == 'win32':
                subprocess.run(['explorer', '/select,', filepath])
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', filepath])
            else:
                subprocess.run(['xdg-open', folder])
        except Exception as e:
            logger.error(f"打开文件夹失败: {e}")

    def update_texts(self):
        """更新界面文本"""
        self.search_box.setPlaceholderText(t("search_placeholder"))
        self.empty_label.setText(t("drop_hint"))


# ==================== 预览组件 ====================

class PreviewWidget(QFrame):
    """图片预览组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewPanel")
        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border-radius: 8px;
                color: #606060;
                font-size: 12px;
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
            target_size = QSize(available_size.width() - 16, available_size.height() - 16)
            scaled = self._original_pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)

    def _show_placeholder(self):
        """显示占位符"""
        self.preview_label.setText(t("preview_no_image"))
        self.preview_label.setPixmap(QPixmap())


# ==================== 语言选择对话框 ====================

class LanguageSelectDialog(QDialog):
    """首次运行语言选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("language_select_title"))
        self.setFixedSize(380, 260)
        self.setStyleSheet(LIGHTROOM_STYLE)
        self.selected_language = "zh-CN"

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Select Language / 选择语言")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        desc = QLabel(t("language_select_desc"))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(desc)

        layout.addSpacing(8)

        self.language_combo = QComboBox()
        self.language_combo.setMinimumHeight(38)
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, code)
        layout.addWidget(self.language_combo)

        layout.addStretch()

        confirm_btn = QPushButton(t("language_confirm"))
        confirm_btn.setObjectName("PrimaryButton")
        confirm_btn.setMinimumHeight(38)
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
        self.setMinimumSize(480, 520)
        self.setStyleSheet(LIGHTROOM_STYLE)

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget, stretch=1)

        # 常规标签页
        general_tab = self._create_general_tab()
        tab_widget.addTab(general_tab, t("settings_tab_general"))

        # 输出标签页
        output_tab = self._create_output_tab()
        tab_widget.addTab(output_tab, t("settings_tab_output"))

        # 高级标签页
        advanced_tab = self._create_advanced_tab()
        tab_widget.addTab(advanced_tab, t("settings_tab_advanced"))

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.reset_btn = QPushButton(t("settings_reset"))
        self.reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton(t("settings_cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton(t("settings_save"))
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setMinimumWidth(90)
        self.save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        """创建常规设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # 语言设置
        lang_group = QGroupBox(t("settings_language"))
        lang_layout = QVBoxLayout(lang_group)

        self.language_combo = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, code)
        lang_layout.addWidget(self.language_combo)

        layout.addWidget(lang_group)

        # 会话设置
        session_group = QGroupBox(t("settings_tab_general"))
        session_layout = QVBoxLayout(session_group)

        self.restore_session_check = QCheckBox(t("settings_restore_session"))
        session_layout.addWidget(self.restore_session_check)

        layout.addWidget(session_group)

        layout.addStretch()
        return widget

    def _create_output_tab(self) -> QWidget:
        """创建输出设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # 输出目录
        dir_group = QGroupBox(t("settings_output"))
        dir_layout = QVBoxLayout(dir_group)

        self.same_dir_radio = QRadioButton(t("settings_same_dir"))
        self.custom_dir_radio = QRadioButton(t("settings_custom_dir"))

        dir_btn_group = QButtonGroup(self)
        dir_btn_group.addButton(self.same_dir_radio)
        dir_btn_group.addButton(self.custom_dir_radio)

        dir_layout.addWidget(self.same_dir_radio)
        dir_layout.addWidget(self.custom_dir_radio)

        path_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(t("settings_output_dir"))
        self.output_dir_edit.setEnabled(False)
        path_layout.addWidget(self.output_dir_edit)

        self.browse_btn = QPushButton(t("settings_browse"))
        self.browse_btn.setEnabled(False)
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_output_dir)
        path_layout.addWidget(self.browse_btn)
        dir_layout.addLayout(path_layout)

        self.same_dir_radio.toggled.connect(self._on_dir_option_changed)
        self.custom_dir_radio.toggled.connect(self._on_dir_option_changed)

        layout.addWidget(dir_group)

        # 文件名设置
        filename_group = QGroupBox(t("settings_filename_pattern"))
        filename_layout = QVBoxLayout(filename_group)

        self.filename_pattern_edit = QLineEdit()
        self.filename_pattern_edit.setText("{original}_stamped")
        self.filename_pattern_edit.setToolTip(t("settings_filename_tooltip"))
        filename_layout.addWidget(self.filename_pattern_edit)

        hint_label = QLabel(t("settings_filename_tooltip"))
        hint_label.setStyleSheet("color: #808080; font-size: 10px;")
        hint_label.setWordWrap(True)
        filename_layout.addWidget(hint_label)

        layout.addWidget(filename_group)

        # JPEG质量
        quality_group = QGroupBox(t("settings_jpeg_quality"))
        quality_layout = QHBoxLayout(quality_group)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setSuffix(" %")
        self.quality_spin.setFixedWidth(100)
        quality_layout.addWidget(self.quality_spin)
        quality_layout.addStretch()

        layout.addWidget(quality_group)

        # 其他选项
        self.preserve_exif_check = QCheckBox(t("settings_preserve_exif"))
        self.preserve_exif_check.setChecked(True)
        layout.addWidget(self.preserve_exif_check)

        self.overwrite_check = QCheckBox(t("settings_overwrite"))
        layout.addWidget(self.overwrite_check)

        layout.addStretch()
        return widget

    def _create_advanced_tab(self) -> QWidget:
        """创建高级设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # 时间源设置
        time_group = QGroupBox(t("settings_time_source"))
        time_layout = QVBoxLayout(time_group)

        time_layout.addWidget(QLabel(t("settings_primary_source")))

        self.time_exif_radio = QRadioButton(t("settings_exif"))
        self.time_modified_radio = QRadioButton(t("settings_file_modified"))
        self.time_created_radio = QRadioButton(t("settings_file_created"))

        time_btn_group = QButtonGroup(self)
        time_btn_group.addButton(self.time_exif_radio)
        time_btn_group.addButton(self.time_modified_radio)
        time_btn_group.addButton(self.time_created_radio)

        time_layout.addWidget(self.time_exif_radio)
        time_layout.addWidget(self.time_modified_radio)
        time_layout.addWidget(self.time_created_radio)

        time_layout.addSpacing(8)

        self.fallback_check = QCheckBox(t("settings_fallback"))
        self.fallback_check.setChecked(True)
        time_layout.addWidget(self.fallback_check)

        layout.addWidget(time_group)

        layout.addStretch()
        return widget

    def _load_settings(self):
        """加载设置"""
        # 语言
        current_lang = self.config.get('general', {}).get('language', 'zh-CN')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break

        # 会话恢复
        self.restore_session_check.setChecked(
            self.config.get('general', {}).get('restore_last_session', False)
        )

        # 时间源
        primary = self.config.get('time_source', {}).get('primary', 'exif')
        if primary == 'exif':
            self.time_exif_radio.setChecked(True)
        elif primary == 'file_modified':
            self.time_modified_radio.setChecked(True)
        else:
            self.time_created_radio.setChecked(True)

        self.fallback_check.setChecked(
            self.config.get('time_source', {}).get('fallback_enabled', True)
        )

        # 输出设置
        output = self.config.get('output', {})
        if output.get('same_directory', True):
            self.same_dir_radio.setChecked(True)
        else:
            self.custom_dir_radio.setChecked(True)

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
        self.config['general']['restore_last_session'] = self.restore_session_check.isChecked()
        I18n.set_language(new_lang)

        # 时间源
        if self.time_exif_radio.isChecked():
            primary = 'exif'
        elif self.time_modified_radio.isChecked():
            primary = 'file_modified'
        else:
            primary = 'file_created'

        self.config['time_source'] = {
            'primary': primary,
            'fallback_enabled': self.fallback_check.isChecked(),
            'fallback_to': 'file_modified'
        }

        # 输出设置
        self.config['output'] = {
            'same_directory': self.same_dir_radio.isChecked(),
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

    def _on_dir_option_changed(self):
        """目录选项变化"""
        enabled = self.custom_dir_radio.isChecked()
        self.output_dir_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)

    def _browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, t("settings_browse"))
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def get_config(self) -> dict:
        return self.config


# ==================== 关于对话框 ====================

class AboutDialog(QDialog):
    """关于对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("about_title"))
        self.setFixedSize(420, 480)
        self.setStyleSheet(LIGHTROOM_STYLE)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedHeight(100)
        logo_path = get_base_path() / "assets" / "logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(
                QSize(80, 80),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("📷")
            logo_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(logo_label)

        layout.addSpacing(16)

        # 软件名称
        name_label = QLabel("Photo Timestamper")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        layout.addWidget(name_label)

        layout.addSpacing(4)

        # 版本
        version_label = QLabel(t("about_version", version=__version__))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(version_label)

        layout.addSpacing(12)

        # 描述
        desc_label = QLabel(t("about_description"))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: #808080; font-size: 11px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addSpacing(20)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3d3d3d;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        layout.addSpacing(20)

        # 作者
        author_title = QLabel(t("about_author"))
        author_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_title.setStyleSheet("color: #808080; font-size: 10px;")
        layout.addWidget(author_title)

        author_name = QLabel(__author__)
        author_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_name.setStyleSheet("color: #c0c0c0; font-size: 13px;")
        layout.addWidget(author_name)

        layout.addSpacing(12)

        # 协作者
        collab_title = QLabel(t("about_collaborators"))
        collab_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collab_title.setStyleSheet("color: #808080; font-size: 10px;")
        layout.addWidget(collab_title)

        collab_names = QLabel(" · ".join(__collaborators__))
        collab_names.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collab_names.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(collab_names)

        layout.addSpacing(12)

        # 许可证
        license_title = QLabel(t("about_license"))
        license_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_title.setStyleSheet("color: #808080; font-size: 10px;")
        layout.addWidget(license_title)

        license_type = QLabel(t("about_license_type"))
        license_type.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_type.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(license_type)

        layout.addStretch()

        # GitHub 按钮
        github_btn = QPushButton(t("about_github"))
        github_btn.setObjectName("PrimaryButton")
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.setFixedHeight(36)
        github_btn.clicked.connect(self._open_github)
        layout.addWidget(github_btn)

        layout.addSpacing(8)

        # 关闭按钮
        close_btn = QPushButton(t("about_close"))
        close_btn.setFixedHeight(36)
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
        self.setFixedSize(380, 220)
        self.setStyleSheet(LIGHTROOM_STYLE)

        self.selected_files: list[str] = []
        self.recursive = True

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        info_label = QLabel(t("import_desc"))
        info_label.setStyleSheet("font-size: 13px; color: #e0e0e0;")
        layout.addWidget(info_label)

        self.recursive_check = QCheckBox(t("import_recursive"))
        self.recursive_check.setChecked(True)
        layout.addWidget(self.recursive_check)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.file_btn = QPushButton(t("import_select_files"))
        self.file_btn.setMinimumHeight(36)
        self.file_btn.clicked.connect(self._select_files)
        btn_layout.addWidget(self.file_btn)

        self.folder_btn = QPushButton(t("import_select_folder"))
        self.folder_btn.setObjectName("PrimaryButton")
        self.folder_btn.setMinimumHeight(36)
        self.folder_btn.clicked.connect(self._select_folder)
        btn_layout.addWidget(self.folder_btn)

        layout.addLayout(btn_layout)

        cancel_btn = QPushButton(t("import_cancel"))
        cancel_btn.setMinimumHeight(32)
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
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.style_manager = StyleManager()

        # 设置语言
        saved_lang = self.config.get('general', {}).get('language', 'zh-CN')
        if saved_lang:
            I18n.set_language(saved_lang)

        self.processing_thread: ProcessingThread | None = None
        self._menu_created = False

        self._init_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._load_ui_state()

        # 首次运行检查
        if self.config_manager.is_first_run():
            QTimer.singleShot(100, self._show_language_selection)
        else:
            # 恢复上次会话
            if self.config.get('general', {}).get('restore_last_session', False):
                QTimer.singleShot(200, self._restore_last_session)

    def _init_ui(self):
        self.setWindowTitle(t("app_name"))
        self.setMinimumSize(1200, 700)

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
        splitter.setSizes([280, 460, 460])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        # 状态栏
        self.statusBar().showMessage(t("msg_ready"))

    def _setup_menu(self):
        """设置菜单栏"""
        # 清除现有菜单
        menubar = self.menuBar()
        menubar.clear()

        # 文件菜单
        file_menu = menubar.addMenu(t("menu_file"))

        import_action = QAction(t("menu_import"), self)
        import_action.setShortcut("Ctrl+O")
        import_action.triggered.connect(self._show_import_dialog)
        file_menu.addAction(import_action)

        import_folder_action = QAction(t("menu_import_folder"), self)
        import_folder_action.setShortcut("Ctrl+Shift+O")
        import_folder_action.triggered.connect(self._import_folder)
        file_menu.addAction(import_folder_action)

        file_menu.addSeparator()

        clear_action = QAction(t("menu_clear_list"), self)
        clear_action.setShortcut("Ctrl+Shift+Delete")
        clear_action.triggered.connect(self._clear_files)
        file_menu.addAction(clear_action)

        file_menu.addSeparator()

        exit_action = QAction(t("menu_exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu(t("menu_edit"))

        select_all_action = QAction(t("menu_select_all"), self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self._select_all)
        edit_menu.addAction(select_all_action)

        deselect_action = QAction(t("menu_deselect_all"), self)
        deselect_action.triggered.connect(self._deselect_all)
        edit_menu.addAction(deselect_action)

        edit_menu.addSeparator()

        remove_action = QAction(t("menu_remove_selected"), self)
        remove_action.setShortcut("Delete")
        remove_action.triggered.connect(self._remove_selected)
        edit_menu.addAction(remove_action)

        edit_menu.addSeparator()

        settings_action = QAction(t("menu_settings"), self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        edit_menu.addAction(settings_action)

        # 帮助菜单
        help_menu = menubar.addMenu(t("menu_help"))

        about_action = QAction(t("menu_about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        self._menu_created = True

    def _setup_shortcuts(self):
        """设置快捷键"""
        # 处理 Ctrl+Enter
        process_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        process_shortcut.activated.connect(self._start_processing)

    def _create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        panel.setObjectName("LeftPanel")
        panel.setFixedWidth(280)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 图片列表标题和信息
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        list_label = QLabel(t("panel_image_list"))
        list_label.setObjectName("PanelTitle")
        header_layout.addWidget(list_label)

        header_layout.addStretch()

        self.list_info_label = QLabel(t("image_count", count=0))
        self.list_info_label.setStyleSheet("color: #606060; font-size: 10px;")
        header_layout.addWidget(self.list_info_label)

        layout.addLayout(header_layout)

        # 图片列表
        self.image_list = ImageListWidget()
        self.image_list.files_dropped.connect(self._on_files_dropped)
        self.image_list.selection_changed.connect(self._on_selection_changed)
        self.image_list.check_changed.connect(self._update_list_info)
        layout.addWidget(self.image_list, stretch=1)

        # 列表操作按钮
        list_btn_layout = QHBoxLayout()
        list_btn_layout.setSpacing(6)

        self.add_btn = QPushButton(t("btn_add_images"))
        self.add_btn.setObjectName("SmallButton")
        self.add_btn.setToolTip(t("tooltip_add_images"))
        self.add_btn.clicked.connect(self._show_import_dialog)
        list_btn_layout.addWidget(self.add_btn)

        self.select_all_btn = QPushButton(t("btn_select_all"))
        self.select_all_btn.setObjectName("SmallButton")
        self.select_all_btn.clicked.connect(self.image_list.check_all)
        list_btn_layout.addWidget(self.select_all_btn)

        self.clear_btn = QPushButton(t("btn_clear_list"))
        self.clear_btn.setObjectName("SmallButton")
        self.clear_btn.clicked.connect(self._clear_files)
        list_btn_layout.addWidget(self.clear_btn)

        layout.addLayout(list_btn_layout)

        layout.addSpacing(6)

        # 水印样式
        style_label = QLabel(t("panel_watermark_style"))
        style_label.setObjectName("PanelTitle")
        layout.addWidget(style_label)

        self.style_combo = QComboBox()
        self.style_combo.setMinimumHeight(34)
        self.style_combo.setToolTip(t("tooltip_style"))
        self._populate_styles()
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        layout.addWidget(self.style_combo)

        layout.addSpacing(8)

        # 处理进度
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        self.progress_label = QLabel(t("processing"))
        self.progress_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton(t("btn_cancel"))
        self.cancel_btn.setObjectName("DangerButton")
        self.cancel_btn.setMinimumHeight(34)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        progress_layout.addWidget(self.cancel_btn)

        self.progress_widget.setVisible(False)
        layout.addWidget(self.progress_widget)

        # 执行按钮
        self.process_btn = QPushButton(t("btn_process"))
        self.process_btn.setObjectName("PrimaryButton")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.setToolTip(t("tooltip_process"))
        self.process_btn.clicked.connect(self._start_processing)
        layout.addWidget(self.process_btn)

        return panel

    def _create_preview_panel(self, title: str) -> QWidget:
        """创建预览面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("PanelTitle")
        layout.addWidget(title_label)

        panel.title_label = title_label

        preview = PreviewWidget()
        layout.addWidget(preview, stretch=1)

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
                self._add_files(files)

    def _import_folder(self):
        """直接导入文件夹"""
        folder = QFileDialog.getExistingDirectory(self, t("import_select_folder"))
        if folder:
            files = scan_images(folder, recursive=True)
            if files:
                self._add_files(files)

    def _add_files(self, files: list[str]):
        """添加文件"""
        added, duplicates = self.image_list.add_files(files)
        self._update_list_info()

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
            self.statusBar().showMessage(t("msg_settings_saved"))

    def _show_about(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _on_files_dropped(self, files: list[str]):
        """处理拖放的文件"""
        self._add_files(files)

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
        """更新预览"""
        try:
            image = Image.open(filepath)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # 原图预览
            original_preview = image.copy()
            original_preview.thumbnail((3600, 2700), Image.Resampling.LANCZOS)
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
            result_preview = renderer.render_preview(image, timestamp, (3600, 2700))
            self.result_preview.preview_widget.set_image(result_preview)

        except Exception as e:
            logger.error(f"生成预览失败: {e}")
            self.original_preview.preview_widget.clear_image()
            self.result_preview.preview_widget.clear_image()

    def _clear_files(self):
        """清空文件列表"""
        if self.image_list.get_count() > 0:
            self.image_list.clear_files()
            self.original_preview.preview_widget.clear_image()
            self.result_preview.preview_widget.clear_image()
            self._update_list_info()
            self.statusBar().showMessage(t("msg_cleared"))

    def _select_all(self):
        """全选"""
        self.image_list.list_widget.selectAll()

    def _deselect_all(self):
        """取消全选"""
        self.image_list.list_widget.clearSelection()

    def _remove_selected(self):
        """移除选中图片"""
        count = len(self.image_list.get_selected_files())
        if count > 0:
            self.image_list.remove_selected()
            self._update_list_info()
            self.statusBar().showMessage(t("msg_removed", count=count))

    def _update_list_info(self):
        """更新列表信息"""
        total = self.image_list.get_count()
        checked = self.image_list.get_checked_count()

        if checked > 0:
            self.list_info_label.setText(t("image_selected_count", selected=checked, total=total))
            self.process_btn.setText(t("btn_process_selected"))
        else:
            self.list_info_label.setText(t("image_count", count=total))
            self.process_btn.setText(t("btn_process"))

    def _start_processing(self):
        """开始处理"""
        # 优先处理勾选的，没有勾选则处理全部
        checked = self.image_list.get_checked_files()
        if checked:
            files_to_process = checked
        else:
            files_to_process = self.image_list.get_all_files()

        if not files_to_process:
            QMessageBox.warning(self, t("app_name"), t("msg_no_images"))
            return

        style_name = self.style_combo.currentText()

        processor = BatchProcessor(self.config, self.style_manager)

        self.processing_thread = ProcessingThread(processor, files_to_process, style_name)
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
        QMessageBox.critical(self, t("error_title"), f"{t('msg_process_error')}: {error}")

    def _set_processing_state(self, processing: bool):
        """设置处理状态"""
        self.process_btn.setVisible(not processing)
        self.progress_widget.setVisible(processing)
        self.add_btn.setEnabled(not processing)
        self.clear_btn.setEnabled(not processing)
        self.select_all_btn.setEnabled(not processing)
        self.style_combo.setEnabled(not processing)

        if not processing:
            self.progress_bar.setValue(0)

    def _update_ui_texts(self):
        """更新所有 UI 文本"""
        self.setWindowTitle(t("app_name"))

        # 重新创建菜单
        self._setup_menu()

        # 更新左侧面板
        self.add_btn.setText(t("btn_add_images"))
        self.select_all_btn.setText(t("btn_select_all"))
        self.clear_btn.setText(t("btn_clear_list"))
        self.process_btn.setText(t("btn_process"))
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
        self.add_btn.setToolTip(t("tooltip_add_images"))
        self.clear_btn.setToolTip(t("tooltip_clear"))
        self.process_btn.setToolTip(t("tooltip_process"))
        self.style_combo.setToolTip(t("tooltip_style"))

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

    def _restore_last_session(self):
        """恢复上次会话"""
        files = self.config_manager.get_last_session_files()
        if files:
            # 过滤掉不存在的文件
            existing_files = [f for f in files if Path(f).exists()]
            if existing_files:
                self._add_files(existing_files)

    def _save_session(self):
        """保存当前会话"""
        if self.config.get('general', {}).get('restore_last_session', False):
            files = self.image_list.get_all_files()
            self.config_manager.save_session_files(files)
        else:
            self.config_manager.clear_session_files()

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

        # 保存会话和UI状态
        self._save_session()
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
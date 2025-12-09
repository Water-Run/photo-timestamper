"""
Photo-Timestamper PyQt6 用户界面
"""

import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QMessageBox,
    QCheckBox, QLineEdit, QSpinBox, QTabWidget, QGroupBox,
    QScrollArea, QSizePolicy, QAbstractItemView, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QMimeData, QUrl
from PyQt6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QIcon, QAction

from PIL import Image
from PIL.ImageQt import ImageQt

from .core import (
    ConfigManager, StyleManager, BatchProcessor, TimeExtractor,
    WatermarkRenderer, scan_images, get_base_path, logger
)


class ProcessingThread(QThread):
    """后台处理线程"""

    progress = pyqtSignal(int, int, str)  # current, total, filename
    preview = pyqtSignal(str, object)  # filepath, PIL.Image
    finished = pyqtSignal(dict)  # results
    error = pyqtSignal(str)

    def __init__(self, processor: BatchProcessor, image_paths: list[str],
                 style_name: str):
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


class DropArea(QFrame):
    """支持拖放的文件列表区域"""

    files_dropped = pyqtSignal(list)  # 文件路径列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)

        # 文件列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

        # 提示标签（当列表为空时显示）
        self.hint_label = QLabel("拖放图片或文件夹到此处\n或点击「添加图片」按钮")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(self.hint_label)

        self._update_hint_visibility()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("DropArea { border: 2px dashed #4CAF50; }")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                # 扫描目录
                files.extend(scan_images(path, recursive=True))
            elif path.lower().endswith(('.jpg', '.jpeg')):
                files.append(path)

        if files:
            self.files_dropped.emit(files)
        self._update_hint_visibility()

    def add_files(self, files: list[str]):
        """添加文件到列表"""
        existing = set(self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                       for i in range(self.list_widget.count()))

        for filepath in files:
            if filepath not in existing:
                item = QListWidgetItem(Path(filepath).name)
                item.setData(Qt.ItemDataRole.UserRole, filepath)
                item.setToolTip(filepath)
                self.list_widget.addItem(item)

        self._update_hint_visibility()

    def get_all_files(self) -> list[str]:
        """获取所有文件路径"""
        return [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list_widget.count())]

    def clear_files(self):
        """清空文件列表"""
        self.list_widget.clear()
        self._update_hint_visibility()

    def remove_selected(self):
        """移除选中的文件"""
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self._update_hint_visibility()

    def _update_hint_visibility(self):
        """更新提示标签显示状态"""
        has_items = self.list_widget.count() > 0
        self.hint_label.setVisible(not has_items)
        self.list_widget.setVisible(has_items)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)

        remove_action = QAction("移除选中", self)
        remove_action.triggered.connect(self.remove_selected)
        menu.addAction(remove_action)

        clear_action = QAction("清空列表", self)
        clear_action.triggered.connect(self.clear_files)
        menu.addAction(clear_action)

        menu.exec(self.list_widget.mapToGlobal(pos))


class PreviewWidget(QLabel):
    """图片预览控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("""
            PreviewWidget {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        self.setText("预览区域\n选择图片后显示预览")
        self.setStyleSheet(self.styleSheet() + "color: #888;")

        self._original_pixmap: Optional[QPixmap] = None

    def set_image(self, image: Image.Image):
        """设置预览图片"""
        # PIL Image 转 QPixmap
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
        self.setText("预览区域\n选择图片后显示预览")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._original_pixmap:
            self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        """更新缩放后的图片"""
        if self._original_pixmap:
            scaled = self._original_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)


class SettingsTab(QWidget):
    """设置选项卡"""

    settings_changed = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config = config_manager.load()

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 时间源设置
        time_group = QGroupBox("时间来源")
        time_layout = QVBoxLayout(time_group)

        self.time_source_combo = QComboBox()
        self.time_source_combo.addItems([
            "EXIF 拍摄时间（推荐）",
            "文件修改时间",
            "文件创建时间"
        ])
        time_layout.addWidget(QLabel("主时间源："))
        time_layout.addWidget(self.time_source_combo)

        self.fallback_check = QCheckBox("EXIF不可用时自动降级使用文件时间")
        self.fallback_check.setChecked(True)
        time_layout.addWidget(self.fallback_check)

        layout.addWidget(time_group)

        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QVBoxLayout(output_group)

        self.same_dir_check = QCheckBox("保存到原图所在目录")
        self.same_dir_check.setChecked(True)
        self.same_dir_check.toggled.connect(self._on_same_dir_toggled)
        output_layout.addWidget(self.same_dir_check)

        dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("自定义输出目录...")
        self.output_dir_edit.setEnabled(False)
        dir_layout.addWidget(self.output_dir_edit)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(self.browse_btn)
        output_layout.addLayout(dir_layout)

        # 文件名模式
        output_layout.addWidget(QLabel("输出文件名格式："))
        self.filename_pattern_edit = QLineEdit()
        self.filename_pattern_edit.setText("{original}_stamped")
        self.filename_pattern_edit.setToolTip(
            "可用变量：\n"
            "{original} - 原文件名\n"
            "{date} - 日期 (YYYYMMDD)\n"
            "{time} - 时间 (HHMMSS)\n"
            "{index} - 序号 (001, 002, ...)"
        )
        output_layout.addWidget(self.filename_pattern_edit)

        # JPEG 质量
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("JPEG 质量："))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setSuffix(" %")
        quality_layout.addWidget(self.quality_spin)
        quality_layout.addStretch()
        output_layout.addLayout(quality_layout)

        self.preserve_exif_check = QCheckBox("保留原始 EXIF 信息")
        self.preserve_exif_check.setChecked(True)
        output_layout.addWidget(self.preserve_exif_check)

        self.overwrite_check = QCheckBox("覆盖已存在的文件")
        self.overwrite_check.setChecked(False)
        output_layout.addWidget(self.overwrite_check)

        layout.addWidget(output_group)

        # 扫描设置
        scan_group = QGroupBox("文件扫描")
        scan_layout = QVBoxLayout(scan_group)

        self.recursive_check = QCheckBox("递归扫描子文件夹")
        self.recursive_check.setChecked(True)
        scan_layout.addWidget(self.recursive_check)

        layout.addWidget(scan_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.reset_btn = QPushButton("恢复默认")
        self.reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(self.reset_btn)

        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _load_settings(self):
        """从配置加载设置"""
        # 时间源
        primary = self.config.get('time_source', {}).get('primary', 'exif')
        source_map = {'exif': 0, 'file_modified': 1, 'file_created': 2}
        self.time_source_combo.setCurrentIndex(source_map.get(primary, 0))

        self.fallback_check.setChecked(
            self.config.get('time_source', {}).get('fallback_enabled', True)
        )

        # 输出
        output = self.config.get('output', {})
        self.same_dir_check.setChecked(output.get('same_directory', True))
        self.output_dir_edit.setText(output.get('custom_directory', ''))
        self.filename_pattern_edit.setText(output.get('filename_pattern', '{original}_stamped'))
        self.quality_spin.setValue(output.get('jpeg_quality', 95))
        self.preserve_exif_check.setChecked(output.get('preserve_exif', True))
        self.overwrite_check.setChecked(output.get('overwrite_existing', False))

        # 扫描
        self.recursive_check.setChecked(
            self.config.get('general', {}).get('recursive_scan', True)
        )

    def _save_settings(self):
        """保存设置到配置文件"""
        # 时间源
        source_map = {0: 'exif', 1: 'file_modified', 2: 'file_created'}
        self.config['time_source'] = {
            'primary': source_map.get(self.time_source_combo.currentIndex(), 'exif'),
            'fallback_enabled': self.fallback_check.isChecked(),
            'fallback_to': 'file_modified'
        }

        # 输出
        self.config['output'] = {
            'same_directory': self.same_dir_check.isChecked(),
            'custom_directory': self.output_dir_edit.text(),
            'filename_pattern': self.filename_pattern_edit.text() or '{original}_stamped',
            'jpeg_quality': self.quality_spin.value(),
            'preserve_exif': self.preserve_exif_check.isChecked(),
            'overwrite_existing': self.overwrite_check.isChecked()
        }

        # 扫描
        self.config['general'] = {
            'recursive_scan': self.recursive_check.isChecked(),
            'language': 'zh-CN'
        }

        self.config_manager.save(self.config)
        self.settings_changed.emit()

        QMessageBox.information(self, "设置", "设置已保存")

    def _reset_settings(self):
        """恢复默认设置"""
        self.config = self.config_manager.get_default()
        self._load_settings()
        QMessageBox.information(self, "设置", "已恢复默认设置（点击「保存设置」生效）")

    def _on_same_dir_toggled(self, checked: bool):
        """切换输出目录选项"""
        self.output_dir_edit.setEnabled(not checked)
        self.browse_btn.setEnabled(not checked)

    def _browse_output_dir(self):
        """浏览选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def get_current_config(self) -> dict:
        """获取当前设置（未保存）"""
        source_map = {0: 'exif', 1: 'file_modified', 2: 'file_created'}

        return {
            'general': {
                'recursive_scan': self.recursive_check.isChecked(),
                'language': 'zh-CN'
            },
            'time_source': {
                'primary': source_map.get(self.time_source_combo.currentIndex(), 'exif'),
                'fallback_enabled': self.fallback_check.isChecked(),
                'fallback_to': 'file_modified'
            },
            'output': {
                'same_directory': self.same_dir_check.isChecked(),
                'custom_directory': self.output_dir_edit.text(),
                'filename_pattern': self.filename_pattern_edit.text() or '{original}_stamped',
                'jpeg_quality': self.quality_spin.value(),
                'preserve_exif': self.preserve_exif_check.isChecked(),
                'overwrite_existing': self.overwrite_check.isChecked()
            },
            'ui': self.config.get('ui', {})
        }


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.style_manager = StyleManager()

        self.processing_thread: Optional[ProcessingThread] = None

        self._init_ui()
        self._load_ui_state()

    def _init_ui(self):
        self.setWindowTitle("Photo Timestamper - 照片时间戳工具")
        self.setMinimumSize(1000, 700)

        # 设置应用图标
        icon_path = get_base_path() / "assets" / "logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 处理选项卡
        process_tab = QWidget()
        self.tab_widget.addTab(process_tab, "处理")
        self._init_process_tab(process_tab)

        # 设置选项卡
        self.settings_tab = SettingsTab(self.config_manager)
        self.settings_tab.settings_changed.connect(self._on_settings_changed)
        self.tab_widget.addTab(self.settings_tab, "设置")

        # 底部状态栏
        self._init_status_bar()

    def _init_process_tab(self, tab: QWidget):
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        # 上半部分：文件列表和预览
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # 左侧：文件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 添加按钮
        btn_layout = QHBoxLayout()

        self.add_files_btn = QPushButton("添加图片")
        self.add_files_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self.add_files_btn)

        self.add_folder_btn = QPushButton("添加文件夹")
        self.add_folder_btn.clicked.connect(self._add_folder)
        btn_layout.addWidget(self.add_folder_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear_files)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()
        left_layout.addLayout(btn_layout)

        # 拖放区域
        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self._on_files_dropped)
        self.drop_area.list_widget.currentItemChanged.connect(self._on_file_selected)
        left_layout.addWidget(self.drop_area)

        splitter.addWidget(left_widget)

        # 右侧：预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("预览效果"))

        self.preview_widget = PreviewWidget()
        right_layout.addWidget(self.preview_widget)

        splitter.addWidget(right_widget)

        # 设置分割比例
        splitter.setSizes([400, 600])

        # 下半部分：样式选择和操作按钮
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 10, 0, 0)

        # 样式选择
        bottom_layout.addWidget(QLabel("水印样式："))

        self.style_combo = QComboBox()
        self.style_combo.setMinimumWidth(150)
        self._populate_styles()
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        bottom_layout.addWidget(self.style_combo)

        bottom_layout.addStretch()

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumWidth(200)
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        bottom_layout.addWidget(self.progress_label)

        bottom_layout.addStretch()

        # 操作按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        bottom_layout.addWidget(self.cancel_btn)

        self.start_btn = QPushButton("开始处理")
        self.start_btn.setMinimumWidth(120)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_btn.clicked.connect(self._start_processing)
        bottom_layout.addWidget(self.start_btn)

        layout.addWidget(bottom_widget)

    def _init_status_bar(self):
        self.statusBar().showMessage("就绪")

    def _populate_styles(self):
        """填充样式下拉列表"""
        styles = self.style_manager.list_styles()
        self.style_combo.clear()
        self.style_combo.addItems(styles)

        # 恢复上次选择的样式
        last_style = self.config.get('ui', {}).get('last_style', '佳能')
        if last_style in styles:
            self.style_combo.setCurrentText(last_style)

    def _add_files(self):
        """添加图片文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            "",
            "JPEG 图片 (*.jpg *.jpeg *.JPG *.JPEG)"
        )
        if files:
            self.drop_area.add_files(files)
            self._update_status()

    def _add_folder(self):
        """添加文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            recursive = self.config.get('general', {}).get('recursive_scan', True)
            files = scan_images(folder, recursive=recursive)
            self.drop_area.add_files(files)
            self._update_status()

    def _clear_files(self):
        """清空文件列表"""
        self.drop_area.clear_files()
        self.preview_widget.clear_image()
        self._update_status()

    def _on_files_dropped(self, files: list[str]):
        """处理拖放的文件"""
        self.drop_area.add_files(files)
        self._update_status()

    def _on_file_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """文件选择变化时更新预览"""
        if current is None:
            self.preview_widget.clear_image()
            return

        filepath = current.data(Qt.ItemDataRole.UserRole)
        self._update_preview(filepath)

    def _on_style_changed(self, style_name: str):
        """样式变化时更新预览"""
        # 保存样式选择
        self.config['ui']['last_style'] = style_name
        self.config_manager.save(self.config)

        # 更新当前预览
        current_item = self.drop_area.list_widget.currentItem()
        if current_item:
            filepath = current_item.data(Qt.ItemDataRole.UserRole)
            self._update_preview(filepath)

    def _update_preview(self, filepath: str):
        """更新预览图"""
        try:
            style_name = self.style_combo.currentText()
            style = self.style_manager.load_style(style_name)

            image = Image.open(filepath)

            # 提取时间
            config = self.settings_tab.get_current_config()
            extractor = TimeExtractor(
                primary=config['time_source']['primary'],
                fallback_enabled=config['time_source']['fallback_enabled'],
                fallback_to=config['time_source']['fallback_to']
            )
            timestamp = extractor.extract(filepath)

            # 渲染水印预览
            renderer = WatermarkRenderer(style, self.style_manager.fonts_dir)
            preview = renderer.render_preview(image, timestamp, (800, 600))

            self.preview_widget.set_image(preview)

        except Exception as e:
            logger.error(f"生成预览失败: {e}")
            self.preview_widget.clear_image()

    def _start_processing(self):
        """开始处理"""
        files = self.drop_area.get_all_files()
        if not files:
            QMessageBox.warning(self, "提示", "请先添加图片")
            return

        style_name = self.style_combo.currentText()
        config = self.settings_tab.get_current_config()

        # 创建处理器
        processor = BatchProcessor(config, self.style_manager)

        # 创建处理线程
        self.processing_thread = ProcessingThread(processor, files, style_name)
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.preview.connect(self._on_processing_preview)
        self.processing_thread.finished.connect(self._on_finished)
        self.processing_thread.error.connect(self._on_error)

        # 更新UI状态
        self._set_processing_state(True)

        # 开始处理
        self.processing_thread.start()

    def _cancel_processing(self):
        """取消处理"""
        if self.processing_thread:
            self.processing_thread.cancel()
            self.statusBar().showMessage("正在取消...")

    def _on_progress(self, current: int, total: int, filename: str):
        """更新进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"{current}/{total}")
        self.statusBar().showMessage(f"正在处理: {filename}")

    def _on_processing_preview(self, filepath: str, image: Image.Image):
        """处理时更新预览"""
        self.preview_widget.set_image(image)

    def _on_finished(self, results: dict):
        """处理完成"""
        self._set_processing_state(False)

        success = results.get('success', 0)
        failed = results.get('failed', 0)

        self.statusBar().showMessage(f"处理完成: 成功 {success}, 失败 {failed}")

        if failed > 0:
            errors = results.get('errors', [])
            error_text = '\n'.join(errors[:10])
            if len(errors) > 10:
                error_text += f'\n... 还有 {len(errors) - 10} 个错误'

            QMessageBox.warning(
                self,
                "处理完成",
                f"成功处理 {success} 张图片\n失败 {failed} 张\n\n错误信息:\n{error_text}"
            )
        else:
            QMessageBox.information(
                self,
                "处理完成",
                f"成功处理 {success} 张图片"
            )

    def _on_error(self, error: str):
        """处理错误"""
        self._set_processing_state(False)
        self.statusBar().showMessage("处理出错")
        QMessageBox.critical(self, "错误", f"处理出错: {error}")

    def _set_processing_state(self, processing: bool):
        """设置处理状态相关的UI"""
        self.start_btn.setEnabled(not processing)
        self.add_files_btn.setEnabled(not processing)
        self.add_folder_btn.setEnabled(not processing)
        self.clear_btn.setEnabled(not processing)
        self.style_combo.setEnabled(not processing)

        self.cancel_btn.setVisible(processing)
        self.progress_bar.setVisible(processing)
        self.progress_label.setVisible(processing)

        if not processing:
            self.progress_bar.setValue(0)

    def _update_status(self):
        """更新状态栏"""
        count = self.drop_area.list_widget.count()
        self.statusBar().showMessage(f"已添加 {count} 张图片")

    def _on_settings_changed(self):
        """设置变化时重新加载配置"""
        self.config = self.config_manager.load()

    def _load_ui_state(self):
        """加载UI状态"""
        geometry = self.config.get('ui', {}).get('window_geometry')
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
        # 如果正在处理，询问是否取消
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "确认退出",
                "正在处理中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.processing_thread.cancel()
            self.processing_thread.wait()

        self._save_ui_state()
        event.accept()


def run_app():
    """运行应用程序"""
    app = QApplication(sys.argv)

    # 设置应用信息
    app.setApplicationName("Photo Timestamper")
    app.setOrganizationName("PhotoTimestamper")

    # 设置默认字体（支持中文）
    # app.setFont(QFont("Microsoft YaHei", 9))

    # 创建主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
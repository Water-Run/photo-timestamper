"""
Photo-Timestamper PyQt6 User Interface&用户界面
Lightroom Style Professional Interface - QtWebEngine Version v2.1
"""

import sys
import os
import subprocess
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional
from io import BytesIO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QDialog, QLabel, QPushButton,
    QComboBox, QSplitter, QGroupBox, QRadioButton, QButtonGroup,
    QCheckBox, QLineEdit, QSpinBox, QDateTimeEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, pyqtSlot, QObject, QTimer, QDateTime
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from PIL import Image

from .core import (
    ConfigManager, StyleManager, BatchProcessor, TimeExtractor,
    WatermarkRenderer, scan_images, get_base_path, logger,
    LocalizationManager, L
)
from . import __version__, __author__, __collaborators__


# ==================== Processing Thread&处理线程 ====================

class ProcessingThread(QThread):
    """Background processing thread&后台处理线程"""

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
            logger.error(f"Processing thread exception&处理线程异常: {e}")
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, filename: str):
        self.progress.emit(current, total, filename)

    def _on_preview(self, filepath: str, image: Image.Image):
        self.preview.emit(filepath, image)

    def cancel(self):
        self.processor.cancel()


# ==================== Web Bridge ====================

class WebBridge(QObject):
    """Python to JavaScript bridge&Python与JavaScript的桥接对象"""

    filesAdded = pyqtSignal(str)
    previewUpdated = pyqtSignal(str, str)
    progressUpdated = pyqtSignal(int, int, str)
    processingFinished = pyqtSignal(str)
    processingError = pyqtSignal(str)
    statusMessage = pyqtSignal(str)
    uiTextsUpdated = pyqtSignal(str)
    showProgressOverlay = pyqtSignal(bool)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._file_list: list[dict] = []
        self._thumbnail_queue: list[str] = []
        self._is_loading_thumbnails = False

    @pyqtSlot(result=str)
    def getTranslations(self) -> str:
        """Get all translation texts&获取所有翻译文本"""
        translations = {
            "app_name": L("Photo Timestamper&照片时间戳"),
            "panel_image_list": L("Image List&图片列表"),
            "panel_watermark_style": L("Watermark Style&水印样式"),
            "search_placeholder": L("Search images...&搜索图片..."),
            "image_count": L("{count} images&共 {count} 张图片"),
            "btn_add_images": L("Add Images&添加图片"),
            "btn_add_folder": L("Add Folder&添加文件夹"),
            "btn_clear_list": L("Clear&清空"),
            "btn_select_all": L("Select All&全选"),
            "btn_process": L("Start Processing&开始处理"),
            "btn_process_selected": L("Process Selected&处理选中"),
            "btn_cancel": L("Cancel&取消"),
            "preview_original": L("Original&原图"),
            "preview_result": L("Preview&效果预览"),
            "preview_no_image": L("Select an image to preview&选择图片以预览"),
            "drop_hint": L("Drop images or folders here\\nor click button below to add&将图片或文件夹拖放到此处\\n或点击下方按钮添加"),
            "processing": L("Processing...&处理中..."),
            "exporting": L("Exporting {current}/{total}&导出第 {current}/{total} 张"),
            "msg_ready": L("Ready&就绪"),
            "ctx_check_selected": L("Check Selected&勾选选中项"),
            "ctx_uncheck_selected": L("Uncheck Selected&取消勾选选中项"),
            "ctx_select_all": L("Select All&全选"),
            "ctx_deselect_all": L("Deselect All&取消全选"),
            "ctx_open_file": L("Open File&打开文件"),
            "ctx_open_folder": L("Open Containing Folder&打开所在文件夹"),
            "ctx_remove_selected": L("Remove Selected&移除选中项"),
            "ctx_clear_all": L("Clear All&清空所有"),
            "error_title": L("Error&错误"),
        }
        return json.dumps(translations, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getStyles(self) -> str:
        """Get available style list&获取可用样式列表"""
        styles = self.main_window.style_manager.list_styles()
        last_style = self.main_window.config.get('ui', {}).get('last_style', 'CANON&佳能')
        
        # Create display names
        style_data = []
        for style in styles:
            style_data.append({
                "value": style,
                "display": L(style)
            })
        
        current = last_style if last_style in styles else (styles[0] if styles else "")
        return json.dumps({
            "styles": style_data,
            "current": current,
            "currentDisplay": L(current) if current else ""
        }, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getFileList(self) -> str:
        """Get file list&获取文件列表"""
        return json.dumps(self._file_list, ensure_ascii=False)

    @pyqtSlot()
    def requestAddFiles(self):
        """Request to add files&请求添加文件"""
        self.main_window._show_import_dialog()

    @pyqtSlot()
    def requestAddFolder(self):
        """Request to add folder&请求添加文件夹"""
        self.main_window._import_folder()

    @pyqtSlot()
    def requestClearFiles(self):
        """Request to clear files&请求清空文件"""
        self._file_list.clear()
        self._thumbnail_queue.clear()
        self.filesAdded.emit(json.dumps(self._file_list))
        self.statusMessage.emit(L("Image list cleared&已清空图片列表"))

    @pyqtSlot(str)
    def setFileChecked(self, data: str):
        """Set file checked state&设置文件勾选状态"""
        info = json.loads(data)
        path = info.get('path')
        checked = info.get('checked', False)
        for item in self._file_list:
            if item['path'] == path:
                item['checked'] = checked
                break

    @pyqtSlot()
    def checkAll(self):
        """Check all&全选"""
        for item in self._file_list:
            item['checked'] = True
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot()
    def uncheckAll(self):
        """Uncheck all&取消全选"""
        for item in self._file_list:
            item['checked'] = False
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot(str)
    def checkSelected(self, selected_json: str):
        """Check selected items&勾选选中项"""
        selected = set(json.loads(selected_json))
        for item in self._file_list:
            if item['path'] in selected:
                item['checked'] = True
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot(str)
    def uncheckSelected(self, selected_json: str):
        """Uncheck selected items&取消勾选选中项"""
        selected = set(json.loads(selected_json))
        for item in self._file_list:
            if item['path'] in selected:
                item['checked'] = False
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot(str)
    def removeSelected(self, selected_json: str):
        """Remove selected items&移除选中项"""
        selected = set(json.loads(selected_json))
        self._file_list = [item for item in self._file_list if item['path'] not in selected]
        self.filesAdded.emit(json.dumps(self._file_list))
        self.statusMessage.emit(L("Removed {count} images&已移除 {count} 张图片").replace("{count}", str(len(selected))))

    @pyqtSlot(str)
    def selectFile(self, filepath: str):
        """Select file for preview&选择文件进行预览"""
        self.main_window._update_preview(filepath)

    @pyqtSlot(str)
    def setStyle(self, style_name: str):
        """Set current style&设置当前样式"""
        self.main_window.config['ui']['last_style'] = style_name
        self.main_window.config_manager.save(self.main_window.config)

    @pyqtSlot(str)
    def startProcessing(self, style_name: str):
        """Start processing&开始处理"""
        checked = [item['path'] for item in self._file_list if item.get('checked')]
        if checked:
            files = checked
        else:
            files = [item['path'] for item in self._file_list]

        if not files:
            QMessageBox.warning(self.main_window, L("Photo Timestamper&照片时间戳"), 
                              L("Please add images first&请先添加图片"))
            return

        self.main_window._start_processing_with_files(files, style_name)

    @pyqtSlot()
    def cancelProcessing(self):
        """Cancel processing&取消处理"""
        self.main_window._cancel_processing()

    @pyqtSlot(str)
    def openFile(self, filepath: str):
        """Open file&打开文件"""
        try:
            if sys.platform == 'win32':
                os.startfile(filepath)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filepath])
            else:
                subprocess.run(['xdg-open', filepath])
        except Exception as e:
            logger.error(f"Failed to open file&打开文件失败: {e}")

    @pyqtSlot(str)
    def openFolder(self, filepath: str):
        """Open containing folder&打开所在文件夹"""
        try:
            folder = str(Path(filepath).parent)
            if sys.platform == 'win32':
                subprocess.run(['explorer', '/select,', filepath])
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', filepath])
            else:
                subprocess.run(['xdg-open', folder])
        except Exception as e:
            logger.error(f"Failed to open folder&打开文件夹失败: {e}")

    @pyqtSlot()
    def showSettings(self):
        """Show settings&显示设置"""
        self.main_window._show_settings()

    @pyqtSlot()
    def showAbout(self):
        """Show about&显示关于"""
        self.main_window._show_about()

    def add_files(self, files: list[str]) -> tuple[int, int]:
        """Add files to list&添加文件到列表"""
        existing = {item['path'] for item in self._file_list}
        added = 0
        duplicates = 0

        for filepath in files:
            if filepath in existing:
                duplicates += 1
                continue

            filename = Path(filepath).name
            self._file_list.append({
                'path': filepath,
                'name': filename,
                'checked': False,
                'thumbnail': ''
            })
            existing.add(filepath)
            added += 1
            self._thumbnail_queue.append(filepath)

        self.filesAdded.emit(json.dumps(self._file_list))
        
        # Start loading thumbnails
        if not self._is_loading_thumbnails and self._thumbnail_queue:
            self._load_next_thumbnail()
        
        return added, duplicates

    def _load_next_thumbnail(self):
        """Load next thumbnail in queue&加载队列中的下一个缩略图"""
        if not self._thumbnail_queue:
            self._is_loading_thumbnails = False
            return
        
        self._is_loading_thumbnails = True
        filepath = self._thumbnail_queue.pop(0)
        QTimer.singleShot(10, lambda: self._load_thumbnail(filepath))

    def _load_thumbnail(self, filepath: str):
        """Load single thumbnail&加载单个缩略图"""
        try:
            # Check if file still in list
            file_item = None
            for item in self._file_list:
                if item['path'] == filepath:
                    file_item = item
                    break
            
            if not file_item or file_item['thumbnail']:
                self._load_next_thumbnail()
                return

            image = Image.open(filepath)
            
            # Calculate thumbnail size maintaining aspect ratio
            max_size = (144, 108)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)

            if image.mode != 'RGB':
                image = image.convert('RGB')

            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=75)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            thumbnail_data = f"data:image/jpeg;base64,{b64}"

            # Update file item
            for item in self._file_list:
                if item['path'] == filepath:
                    item['thumbnail'] = thumbnail_data
                    break

            self.filesAdded.emit(json.dumps(self._file_list))

        except Exception as e:
            logger.debug(f"Failed to load thumbnail&加载缩略图失败: {e}")
        
        # Continue loading next
        self._load_next_thumbnail()

    def get_all_files(self) -> list[str]:
        """Get all files&获取所有文件"""
        return [item['path'] for item in self._file_list]

    def get_checked_count(self) -> int:
        """Get checked count&获取勾选数量"""
        return sum(1 for item in self._file_list if item.get('checked'))


# ==================== HTML Template&HTML模板 ====================

def get_html_content() -> str:
    """Generate complete HTML content&生成完整的HTML内容"""
    return r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Timestamper</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --bg-primary: #1e1e1e;
            --bg-secondary: #252525;
            --bg-tertiary: #2d2d2d;
            --bg-hover: #353535;
            --bg-active: #404040;
            --border-color: #3d3d3d;
            --text-primary: #e0e0e0;
            --text-secondary: #a0a0a0;
            --text-muted: #606060;
            --accent-blue: #0a84ff;
            --accent-blue-hover: #409cff;
            --accent-green: #34c759;
            --accent-orange: #ff9500;
            --accent-red: #ff3b30;
            --status-height: 22px;
        }

        body {
            font-family: "Microsoft YaHei", "Segoe UI", "SF Pro Display", sans-serif;
            font-size: 12px;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            overflow: hidden;
            height: 100vh;
            user-select: none;
        }

        .main-container {
            display: flex;
            height: calc(100vh - var(--status-height));
        }

        .left-panel {
            width: 280px;
            min-width: 280px;
            background-color: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            padding: 12px;
        }

        .panel-title {
            color: var(--text-secondary);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 8px 0 6px 0;
        }

        .list-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }

        .list-info {
            color: var(--text-muted);
            font-size: 10px;
        }

        .search-box {
            background-color: var(--bg-tertiary);
            border: 1px solid #4d4d4d;
            border-radius: 4px;
            padding: 8px 12px;
            color: var(--text-primary);
            font-size: 12px;
            width: 100%;
            margin-bottom: 8px;
            outline: none;
        }

        .search-box:focus {
            border-color: var(--accent-blue);
        }

        .search-box::placeholder {
            color: var(--text-muted);
        }

        .file-list-container {
            flex: 1;
            background-color: #2a2a2a;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .file-list {
            flex: 1;
            overflow-y: auto;
            padding: 4px;
        }

        .file-list::-webkit-scrollbar {
            width: 8px;
        }

        .file-list::-webkit-scrollbar-track {
            background: transparent;
        }

        .file-list::-webkit-scrollbar-thumb {
            background-color: #4d4d4d;
            border-radius: 4px;
        }

        .file-list::-webkit-scrollbar-thumb:hover {
            background-color: #5d5d5d;
        }

        .empty-hint {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-muted);
            font-size: 13px;
            text-align: center;
            line-height: 1.8;
            padding: 40px;
        }

        .file-item {
            display: flex;
            align-items: center;
            padding: 6px;
            border-radius: 4px;
            cursor: pointer;
            margin-bottom: 2px;
            gap: 10px;
        }

        .file-item:hover {
            background-color: var(--bg-hover);
        }

        .file-item.selected {
            background-color: var(--bg-active);
        }

        .checkmark {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            border: 2px solid #5d5d5d;
            background-color: var(--bg-tertiary);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
            transition: all 0.15s ease;
        }

        .checkmark:hover {
            border-color: #7d7d7d;
        }

        .checkmark.checked {
            background-color: var(--accent-green);
            border-color: var(--accent-green);
        }

        .checkmark.checked::after {
            content: '';
            width: 6px;
            height: 10px;
            border: solid white;
            border-width: 0 2px 2px 0;
            transform: rotate(45deg);
            margin-top: -2px;
        }

        .thumbnail {
            width: 72px;
            height: 54px;
            background-color: #1a1a1a;
            border-radius: 3px;
            border: 1px solid var(--border-color);
            overflow: hidden;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .thumbnail img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }

        .thumbnail-placeholder {
            color: var(--text-muted);
            font-size: 10px;
        }

        .file-name {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 12px;
        }

        .button-group {
            display: flex;
            gap: 6px;
            margin-top: 8px;
        }

        .btn {
            background-color: var(--bg-tertiary);
            border: 1px solid #4d4d4d;
            border-radius: 4px;
            padding: 6px 12px;
            color: var(--text-primary);
            font-size: 11px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            flex: 1;
        }

        .btn:hover {
            background-color: #4d4d4d;
            border-color: #5d5d5d;
        }

        .btn:active {
            background-color: var(--bg-tertiary);
        }

        .btn:disabled {
            background-color: var(--bg-tertiary);
            color: var(--text-muted);
            cursor: not-allowed;
        }

        .btn-primary {
            background-color: var(--accent-blue);
            border: none;
            color: white;
            font-weight: 600;
        }

        .btn-primary:hover {
            background-color: var(--accent-blue-hover);
        }

        .btn-primary:disabled {
            background-color: #404040;
            color: #808080;
        }

        .btn-danger {
            background-color: var(--accent-red);
            border: none;
            color: white;
        }

        .btn-danger:hover {
            background-color: #ff5a52;
        }

        .btn-large {
            padding: 10px 16px;
            font-size: 13px;
            min-height: 40px;
        }

        .style-section {
            margin-top: 12px;
        }

        .style-select {
            width: 100%;
            background-color: var(--bg-tertiary);
            border: 1px solid #4d4d4d;
            border-radius: 4px;
            padding: 8px 12px;
            color: var(--text-primary);
            font-size: 12px;
            cursor: pointer;
            outline: none;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23808080' d='M2 4l4 4 4-4'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 10px center;
        }

        .style-select:hover {
            border-color: #5d5d5d;
        }

        .style-select:focus {
            border-color: var(--accent-blue);
        }

        .process-section {
            margin-top: auto;
            padding-top: 12px;
        }

        .preview-container {
            flex: 1;
            display: flex;
            gap: 0;
        }

        .preview-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 12px;
            min-width: 0;
        }

        .preview-panel:first-child {
            border-right: 1px solid var(--border-color);
        }

        .preview-area {
            flex: 1;
            background-color: #1a1a1a;
            border: 1px solid var(--bg-tertiary);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            position: relative;
        }

        .preview-area img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }

        .preview-placeholder {
            color: var(--text-muted);
            font-size: 12px;
        }

        .context-menu {
            position: fixed;
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 6px;
            min-width: 180px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            z-index: 1000;
            display: none;
        }

        .context-menu.visible {
            display: block;
        }

        .context-menu-item {
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }

        .context-menu-item:hover {
            background-color: var(--accent-blue);
        }

        .context-menu-separator {
            height: 1px;
            background-color: var(--border-color);
            margin: 6px 8px;
        }

        .drop-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(10, 132, 255, 0.1);
            border: 3px dashed var(--accent-blue);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 999;
            pointer-events: none;
        }

        .drop-overlay.visible {
            display: flex;
        }

        .drop-overlay-text {
            background-color: var(--bg-tertiary);
            padding: 20px 40px;
            border-radius: 8px;
            font-size: 16px;
            color: var(--accent-blue);
        }

        /* Progress Overlay - LR Style */
        .progress-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.7);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 2000;
        }

        .progress-overlay.visible {
            display: flex;
        }

        .progress-dialog {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 24px 32px;
            min-width: 400px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
        }

        .progress-title {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text-primary);
        }

        .progress-bar-container {
            height: 20px;
            background-color: var(--bg-tertiary);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 12px;
            position: relative;
        }

        .progress-bar-fill {
            height: 100%;
            background: repeating-linear-gradient(
                -45deg,
                var(--accent-orange),
                var(--accent-orange) 10px,
                #cc7a00 10px,
                #cc7a00 20px
            );
            background-size: 28px 100%;
            animation: progress-stripe 0.5s linear infinite;
            border-radius: 10px;
            transition: width 0.3s ease;
        }

        @keyframes progress-stripe {
            0% { background-position: 0 0; }
            100% { background-position: 28px 0; }
        }

        .progress-text {
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }

        .progress-error {
            background-color: rgba(255, 59, 48, 0.1);
            border: 1px solid var(--accent-red);
            border-radius: 4px;
            padding: 12px;
            margin-top: 12px;
            color: var(--accent-red);
            font-size: 12px;
            display: none;
        }

        .progress-error.visible {
            display: block;
        }

        .progress-buttons {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 16px;
        }

        .status-bar {
            height: var(--status-height);
            background-color: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            padding: 0 10px;
            font-size: 11px;
            color: var(--text-muted);
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 5;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="left-panel">
            <div class="list-header">
                <span class="panel-title" id="panelTitle">图片列表</span>
                <span class="list-info" id="listInfo">共 0 张图片</span>
            </div>

            <input type="text" class="search-box" id="searchBox" placeholder="搜索图片...">

            <div class="file-list-container">
                <div class="file-list" id="fileList">
                    <div class="empty-hint" id="emptyHint">
                        将图片或文件夹拖放到此处<br>或点击下方按钮添加
                    </div>
                </div>
            </div>

            <div class="button-group">
                <button class="btn" id="btnAdd" onclick="bridge.requestAddFiles()">添加图片</button>
                <button class="btn" id="btnSelectAll" onclick="selectAllFiles()">全选</button>
                <button class="btn" id="btnClear" onclick="bridge.requestClearFiles()">清空</button>
            </div>

            <div class="style-section">
                <span class="panel-title" id="styleTitle">水印样式</span>
                <select class="style-select" id="styleSelect" onchange="onStyleChange()">
                </select>
            </div>

            <div class="process-section" id="processSection">
                <button class="btn btn-primary btn-large" id="btnProcess" onclick="startProcessing()">开始处理</button>
            </div>
        </div>

        <div class="preview-container">
            <div class="preview-panel">
                <span class="panel-title" id="originalTitle">原图</span>
                <div class="preview-area" id="originalPreview">
                    <span class="preview-placeholder" id="originalPlaceholder">选择图片以预览</span>
                    <img id="originalImage" style="display: none;">
                </div>
            </div>
            <div class="preview-panel">
                <span class="panel-title" id="resultTitle">效果预览</span>
                <div class="preview-area" id="resultPreview">
                    <span class="preview-placeholder" id="resultPlaceholder">选择图片以预览</span>
                    <img id="resultImage" style="display: none;">
                </div>
            </div>
        </div>
    </div>

    <div class="context-menu" id="contextMenu">
        <div class="context-menu-item" id="menuCheckSelected" onclick="checkSelectedItems()">勾选选中项</div>
        <div class="context-menu-item" id="menuUncheckSelected" onclick="uncheckSelectedItems()">取消勾选选中项</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" id="menuSelectAll" onclick="selectAllItems()">全选</div>
        <div class="context-menu-item" id="menuDeselectAll" onclick="deselectAllItems()">取消全选</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" id="menuOpenFile" onclick="openCurrentFile()">打开文件</div>
        <div class="context-menu-item" id="menuOpenFolder" onclick="openCurrentFolder()">打开所在文件夹</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" id="menuRemoveSelected" onclick="removeSelectedItems()">移除选中项</div>
        <div class="context-menu-item" id="menuClearAll" onclick="bridge.requestClearFiles()">清空所有</div>
    </div>

    <div class="drop-overlay" id="dropOverlay">
        <div class="drop-overlay-text">释放以添加图片</div>
    </div>

    <!-- Progress Overlay -->
    <div class="progress-overlay" id="progressOverlay">
        <div class="progress-dialog">
            <div class="progress-title" id="progressTitle">导出中...</div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" id="progressFill" style="width: 0%;"></div>
            </div>
            <div class="progress-text" id="progressText">准备中...</div>
            <div class="progress-error" id="progressError"></div>
            <div class="progress-buttons">
                <button class="btn btn-danger" id="btnCancelProgress" onclick="cancelProcessing()">取消</button>
            </div>
        </div>
    </div>

    <div class="status-bar" id="statusBar">就绪</div>

    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        let bridge = null;
        let fileList = [];
        let selectedPaths = new Set();
        let currentContextPath = null;
        let isProcessing = false;
        let currentStyleValue = '';

        const $ = (id) => document.getElementById(id);

        document.addEventListener('DOMContentLoaded', () => {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                bridge = channel.objects.bridge;
                
                bridge.filesAdded.connect(function(jsonData) {
                    fileList = JSON.parse(jsonData);
                    renderFileList();
                });

                bridge.previewUpdated.connect(function(original, result) {
                    updatePreview(original, result);
                });

                bridge.progressUpdated.connect(function(current, total, filename) {
                    updateProgress(current, total, filename);
                });

                bridge.processingFinished.connect(function(resultJson) {
                    onProcessingFinished(JSON.parse(resultJson));
                });

                bridge.processingError.connect(function(errorMsg) {
                    onProcessingError(errorMsg);
                });

                bridge.statusMessage.connect(function(message) {
                    const bar = $('statusBar');
                    if (bar) bar.textContent = message;
                });

                bridge.uiTextsUpdated.connect(function(textsJson) {
                    updateUITexts(JSON.parse(textsJson));
                });

                bridge.showProgressOverlay.connect(function(show) {
                    const overlay = $('progressOverlay');
                    if (overlay) {
                        if (show) {
                            overlay.classList.add('visible');
                            isProcessing = true;
                        } else {
                            overlay.classList.remove('visible');
                            isProcessing = false;
                        }
                    }
                });

                initializeUI().catch(console.error);
            });
        });

        async function initializeUI() {
            const textsJson = await bridge.getTranslations();
            const texts = JSON.parse(textsJson);
            updateUITexts(texts);

            const stylesJson = await bridge.getStyles();
            const stylesData = JSON.parse(stylesJson);
            const styleSelect = $('styleSelect');
            if (styleSelect) {
                styleSelect.innerHTML = '';
                stylesData.styles.forEach(style => {
                    const option = document.createElement('option');
                    option.value = style.value;
                    option.textContent = style.display;
                    if (style.value === stylesData.current) {
                        option.selected = true;
                        currentStyleValue = style.value;
                    }
                    styleSelect.appendChild(option);
                });
            }

            const fileListJson = await bridge.getFileList();
            fileList = JSON.parse(fileListJson);
            renderFileList();
        }

        function updateUITexts(texts) {
            $('panelTitle') && ($('panelTitle').textContent = texts.panel_image_list || '图片列表');
            $('searchBox') && ($('searchBox').placeholder = texts.search_placeholder || '搜索图片...');
            $('btnAdd') && ($('btnAdd').textContent = texts.btn_add_images || '添加图片');
            $('btnSelectAll') && ($('btnSelectAll').textContent = texts.btn_select_all || '全选');
            $('btnClear') && ($('btnClear').textContent = texts.btn_clear_list || '清空');
            $('styleTitle') && ($('styleTitle').textContent = texts.panel_watermark_style || '水印样式');
            $('btnProcess') && ($('btnProcess').textContent = texts.btn_process || '开始处理');
            $('btnCancelProgress') && ($('btnCancelProgress').textContent = texts.btn_cancel || '取消');
            $('originalTitle') && ($('originalTitle').textContent = texts.preview_original || '原图');
            $('resultTitle') && ($('resultTitle').textContent = texts.preview_result || '效果预览');
            $('originalPlaceholder') && ($('originalPlaceholder').textContent = texts.preview_no_image || '选择图片以预览');
            $('resultPlaceholder') && ($('resultPlaceholder').textContent = texts.preview_no_image || '选择图片以预览');
            if ($('emptyHint')) {
                $('emptyHint').innerHTML = (texts.drop_hint || '将图片或文件夹拖放到此处<br>或点击下方按钮添加').replace(/\\n/g, '<br>');
            }
            $('statusBar') && ($('statusBar').textContent = texts.msg_ready || '就绪');
            
            // Context menu
            $('menuCheckSelected') && ($('menuCheckSelected').textContent = texts.ctx_check_selected || '勾选选中项');
            $('menuUncheckSelected') && ($('menuUncheckSelected').textContent = texts.ctx_uncheck_selected || '取消勾选选中项');
            $('menuSelectAll') && ($('menuSelectAll').textContent = texts.ctx_select_all || '全选');
            $('menuDeselectAll') && ($('menuDeselectAll').textContent = texts.ctx_deselect_all || '取消全选');
            $('menuOpenFile') && ($('menuOpenFile').textContent = texts.ctx_open_file || '打开文件');
            $('menuOpenFolder') && ($('menuOpenFolder').textContent = texts.ctx_open_folder || '打开所在文件夹');
            $('menuRemoveSelected') && ($('menuRemoveSelected').textContent = texts.ctx_remove_selected || '移除选中项');
            $('menuClearAll') && ($('menuClearAll').textContent = texts.ctx_clear_all || '清空所有');
        }

        function renderFileList() {
            const container = $('fileList');
            const emptyHint = $('emptyHint');
            const searchBox = $('searchBox');
            const searchText = (searchBox ? searchBox.value : '').toLowerCase();

            if (!container || !emptyHint) return;

            container.innerHTML = '';

            if (fileList.length === 0) {
                container.appendChild(emptyHint);
                emptyHint.style.display = 'flex';
                updateListInfo();
                return;
            }

            emptyHint.style.display = 'none';

            fileList.forEach(file => {
                if (searchText && !file.name.toLowerCase().includes(searchText)) {
                    return;
                }

                const item = document.createElement('div');
                item.className = 'file-item' + (selectedPaths.has(file.path) ? ' selected' : '');
                item.dataset.path = file.path;

                const thumbnailHtml = file.thumbnail 
                    ? `<img src="${file.thumbnail}" alt="">` 
                    : '<span class="thumbnail-placeholder">...</span>';

                item.innerHTML = `
                    <div class="checkmark ${file.checked ? 'checked' : ''}" data-path="${encodeURIComponent(file.path)}"></div>
                    <div class="thumbnail">${thumbnailHtml}</div>
                    <span class="file-name">${escapeHtml(file.name)}</span>
                `;

                item.addEventListener('click', (e) => onItemClick(e, file.path));
                item.addEventListener('dblclick', (e) => onItemDoubleClick(e, file.path));
                item.addEventListener('contextmenu', (e) => onItemContextMenu(e, file.path));

                const checkmark = item.querySelector('.checkmark');
                if (checkmark) {
                    checkmark.addEventListener('click', (e) => {
                        e.stopPropagation();
                        toggleCheck(e, file.path);
                    });
                }

                container.appendChild(item);
            });

            updateListInfo();
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function toggleCheck(event, path) {
            event.stopPropagation();
            const file = fileList.find(f => f.path === path);
            if (file) {
                file.checked = !file.checked;
                if (bridge && bridge.setFileChecked) {
                    bridge.setFileChecked(JSON.stringify({path: path, checked: file.checked}));
                }
                renderFileList();
            }
        }

        function onItemClick(event, path) {
            if (event.ctrlKey || event.metaKey) {
                if (selectedPaths.has(path)) {
                    selectedPaths.delete(path);
                } else {
                    selectedPaths.add(path);
                }
            } else if (event.shiftKey && selectedPaths.size > 0) {
                const paths = fileList.map(f => f.path);
                const lastSelected = Array.from(selectedPaths).pop();
                const startIdx = paths.indexOf(lastSelected);
                const endIdx = paths.indexOf(path);
                const [minIdx, maxIdx] = [Math.min(startIdx, endIdx), Math.max(startIdx, endIdx)];
                for (let i = minIdx; i <= maxIdx; i++) {
                    selectedPaths.add(paths[i]);
                }
            } else {
                selectedPaths.clear();
                selectedPaths.add(path);
            }
            renderFileList();
            if (bridge && bridge.selectFile) {
                bridge.selectFile(path);
            }
        }

        function onItemDoubleClick(event, path) {
            const file = fileList.find(f => f.path === path);
            if (file) {
                file.checked = !file.checked;
                if (bridge && bridge.setFileChecked) {
                    bridge.setFileChecked(JSON.stringify({path: path, checked: file.checked}));
                }
                renderFileList();
            }
        }

        function onItemContextMenu(event, path) {
            event.preventDefault();
            currentContextPath = path;
            
            if (!selectedPaths.has(path)) {
                selectedPaths.clear();
                selectedPaths.add(path);
                renderFileList();
            }

            const menu = $('contextMenu');
            if (menu) {
                menu.style.left = event.clientX + 'px';
                menu.style.top = event.clientY + 'px';
                menu.classList.add('visible');
            }
        }

        function selectAllFiles() {
            if (bridge && bridge.checkAll) bridge.checkAll();
        }

        function selectAllItems() {
            fileList.forEach(f => selectedPaths.add(f.path));
            renderFileList();
            hideContextMenu();
        }

        function deselectAllItems() {
            selectedPaths.clear();
            renderFileList();
            hideContextMenu();
        }

        function checkSelectedItems() {
            if (bridge && bridge.checkSelected) {
                bridge.checkSelected(JSON.stringify(Array.from(selectedPaths)));
            }
            hideContextMenu();
        }

        function uncheckSelectedItems() {
            if (bridge && bridge.uncheckSelected) {
                bridge.uncheckSelected(JSON.stringify(Array.from(selectedPaths)));
            }
            hideContextMenu();
        }

        function removeSelectedItems() {
            if (bridge && bridge.removeSelected) {
                bridge.removeSelected(JSON.stringify(Array.from(selectedPaths)));
            }
            selectedPaths.clear();
            hideContextMenu();
        }

        function openCurrentFile() {
            if (currentContextPath && bridge && bridge.openFile) {
                bridge.openFile(currentContextPath);
            }
            hideContextMenu();
        }

        function openCurrentFolder() {
            if (currentContextPath && bridge && bridge.openFolder) {
                bridge.openFolder(currentContextPath);
            }
            hideContextMenu();
        }

        function hideContextMenu() {
            const menu = $('contextMenu');
            if (menu) menu.classList.remove('visible');
        }

        function onStyleChange() {
            const styleSelect = $('styleSelect');
            if (!styleSelect) return;
            currentStyleValue = styleSelect.value;
            if (bridge && bridge.setStyle) {
                bridge.setStyle(currentStyleValue);
            }
            if (selectedPaths.size === 1 && bridge && bridge.selectFile) {
                bridge.selectFile(Array.from(selectedPaths)[0]);
            }
        }

        function startProcessing() {
            if (bridge && bridge.startProcessing) {
                bridge.startProcessing(currentStyleValue);
            }
        }

        function cancelProcessing() {
            if (bridge && bridge.cancelProcessing) {
                bridge.cancelProcessing();
            }
        }

        function showProgressOverlay(show) {
            const overlay = $('progressOverlay');
            const error = $('progressError');
            if (overlay) {
                if (show) {
                    overlay.classList.add('visible');
                    if (error) {
                        error.classList.remove('visible');
                        error.textContent = '';
                    }
                    isProcessing = true;
                } else {
                    overlay.classList.remove('visible');
                    isProcessing = false;
                }
            }
        }

        function updateProgress(current, total, filename) {
            showProgressOverlay(true);
            const percent = (current / total) * 100;
            const fill = $('progressFill');
            const text = $('progressText');
            const title = $('progressTitle');
            if (fill) fill.style.width = percent + '%';
            if (text) text.textContent = filename;
            if (title) title.textContent = `导出第 ${current}/${total} 张`;
        }

        function onProcessingFinished(result) {
            showProgressOverlay(false);
        }

        function onProcessingError(errorMsg) {
            const error = $('progressError');
            const btn = $('btnCancelProgress');
            if (error) {
                error.textContent = errorMsg;
                error.classList.add('visible');
            }
            if (btn) {
                btn.textContent = '关闭';
                btn.onclick = function() {
                    showProgressOverlay(false);
                    btn.textContent = '取消';
                    btn.onclick = cancelProcessing;
                };
            }
        }

        function updatePreview(originalBase64, resultBase64) {
            const originalImg = $('originalImage');
            const originalPlaceholder = $('originalPlaceholder');
            const resultImg = $('resultImage');
            const resultPlaceholder = $('resultPlaceholder');

            if (originalImg && originalPlaceholder) {
                if (originalBase64) {
                    originalImg.src = originalBase64;
                    originalImg.style.display = 'block';
                    originalPlaceholder.style.display = 'none';
                } else {
                    originalImg.style.display = 'none';
                    originalPlaceholder.style.display = 'block';
                }
            }

            if (resultImg && resultPlaceholder) {
                if (resultBase64) {
                    resultImg.src = resultBase64;
                    resultImg.style.display = 'block';
                    resultPlaceholder.style.display = 'none';
                } else {
                    resultImg.style.display = 'none';
                    resultPlaceholder.style.display = 'block';
                }
            }
        }

        function updateListInfo() {
            const total = fileList.length;
            const checked = fileList.filter(f => f.checked).length;
            const info = $('listInfo');
            const btn = $('btnProcess');
            
            if (info) {
                if (checked > 0) {
                    info.textContent = `已选择 ${checked} / ${total} 张`;
                } else {
                    info.textContent = `共 ${total} 张图片`;
                }
            }
            if (btn) {
                btn.textContent = checked > 0 ? '处理选中' : '开始处理';
            }
        }

        const searchBoxEl = $('searchBox');
        if (searchBoxEl) {
            searchBoxEl.addEventListener('input', function() {
                renderFileList();
            });
        }

        document.addEventListener('click', function(e) {
            if (!e.target.closest('.context-menu')) {
                hideContextMenu();
            }
        });

        document.addEventListener('dragenter', function(e) {
            e.preventDefault();
            if (!isProcessing) {
                const overlay = $('dropOverlay');
                if (overlay) overlay.classList.add('visible');
            }
        });

        document.addEventListener('dragleave', function(e) {
            const overlay = $('dropOverlay');
            if (overlay && e.target === overlay) {
                overlay.classList.remove('visible');
            }
        });

        document.addEventListener('dragover', function(e) {
            e.preventDefault();
        });

        document.addEventListener('drop', function(e) {
            e.preventDefault();
            const overlay = $('dropOverlay');
            if (overlay) overlay.classList.remove('visible');
        });

        document.addEventListener('keydown', function(e) {
            if (isProcessing) return;
            
            if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                selectAllItems();
            } else if (e.key === 'Delete') {
                if (selectedPaths.size > 0) {
                    removeSelectedItems();
                }
            } else if (e.key === 'Escape') {
                hideContextMenu();
                deselectAllItems();
            }
        });
    </script>
</body>
</html>'''


# ==================== Settings Dialog&设置对话框 ====================

class SettingsDialog(QDialog):
    """Settings Dialog&设置对话框"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config = config_manager.load()

        self.setWindowTitle(L("Settings&设置"))
        self.setMinimumSize(500, 560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Language Section
        lang_group = QGroupBox(L("Language&语言"))
        lang_layout = QVBoxLayout(lang_group)
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("简体中文", "zh")
        current_lang = self.config.get('general', {}).get('language', 'zh')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break
        lang_layout.addWidget(self.language_combo)
        layout.addWidget(lang_group)

        # Session Section
        self.restore_session_check = QCheckBox(L("Restore images from last session on startup&启动时恢复上次打开的图片"))
        self.restore_session_check.setChecked(
            self.config.get('general', {}).get('restore_last_session', True)
        )
        layout.addWidget(self.restore_session_check)

        # Output Section
        output_group = QGroupBox(L("Output Settings&输出设置"))
        output_layout = QVBoxLayout(output_group)

        self.same_dir_radio = QRadioButton(L("Save to original directory&保存到原图所在目录"))
        self.custom_dir_radio = QRadioButton(L("Custom output directory&自定义输出目录"))
        dir_btn_group = QButtonGroup(self)
        dir_btn_group.addButton(self.same_dir_radio)
        dir_btn_group.addButton(self.custom_dir_radio)
        output_layout.addWidget(self.same_dir_radio)
        output_layout.addWidget(self.custom_dir_radio)

        path_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(L("Output directory...&输出目录..."))
        self.output_dir_edit.setEnabled(False)
        path_layout.addWidget(self.output_dir_edit)

        self.browse_btn = QPushButton(L("Browse...&浏览..."))
        self.browse_btn.setEnabled(False)
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_output_dir)
        path_layout.addWidget(self.browse_btn)
        output_layout.addLayout(path_layout)

        self.same_dir_radio.toggled.connect(self._on_dir_option_changed)

        output_config = self.config.get('output', {})
        if output_config.get('same_directory', True):
            self.same_dir_radio.setChecked(True)
        else:
            self.custom_dir_radio.setChecked(True)
        self.output_dir_edit.setText(output_config.get('custom_directory', ''))

        # Filename pattern
        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel(L("Filename pattern&文件名格式:")))
        self.filename_pattern_edit = QLineEdit()
        self.filename_pattern_edit.setText(output_config.get('filename_pattern', '{original}_stamped'))
        self.filename_pattern_edit.setToolTip(L("Variables: {original}=original name, {date}=date, {time}=time, {index}=index&可用变量：{original}=原文件名, {date}=日期, {time}=时间, {index}=序号"))
        pattern_layout.addWidget(self.filename_pattern_edit)
        output_layout.addLayout(pattern_layout)

        # JPEG quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel(L("JPEG Quality&JPEG质量:")))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(output_config.get('jpeg_quality', 95))
        self.quality_spin.setSuffix(" %")
        quality_layout.addWidget(self.quality_spin)
        quality_layout.addStretch()
        output_layout.addLayout(quality_layout)

        self.preserve_exif_check = QCheckBox(L("Preserve original EXIF data&保留原始EXIF信息"))
        self.preserve_exif_check.setChecked(output_config.get('preserve_exif', True))
        output_layout.addWidget(self.preserve_exif_check)

        self.overwrite_check = QCheckBox(L("Overwrite existing files&覆盖已存在的文件"))
        self.overwrite_check.setChecked(output_config.get('overwrite_existing', False))
        output_layout.addWidget(self.overwrite_check)

        layout.addWidget(output_group)

        # Time Source Section
        time_group = QGroupBox(L("Time Source&时间源"))
        time_layout = QVBoxLayout(time_group)
        
        time_layout.addWidget(QLabel(L("Primary source&主时间源:")))

        self.time_exif_radio = QRadioButton(L("EXIF Date Taken (Recommended)&EXIF拍摄时间（推荐）"))
        self.time_modified_radio = QRadioButton(L("File Modified Time&文件修改时间"))
        self.time_created_radio = QRadioButton(L("File Created Time&文件创建时间"))
        self.time_custom_radio = QRadioButton(L("Custom Time&自定义时间"))

        time_btn_group = QButtonGroup(self)
        time_btn_group.addButton(self.time_exif_radio)
        time_btn_group.addButton(self.time_modified_radio)
        time_btn_group.addButton(self.time_created_radio)
        time_btn_group.addButton(self.time_custom_radio)

        time_layout.addWidget(self.time_exif_radio)
        time_layout.addWidget(self.time_modified_radio)
        time_layout.addWidget(self.time_created_radio)
        
        custom_time_layout = QHBoxLayout()
        custom_time_layout.addWidget(self.time_custom_radio)
        self.custom_time_edit = QDateTimeEdit()
        self.custom_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.custom_time_edit.setDateTime(QDateTime.currentDateTime())
        self.custom_time_edit.setEnabled(False)
        custom_time_layout.addWidget(self.custom_time_edit)
        time_layout.addLayout(custom_time_layout)

        time_config = self.config.get('time_source', {})
        primary = time_config.get('primary', 'exif')
        if primary == 'exif':
            self.time_exif_radio.setChecked(True)
        elif primary == 'file_modified':
            self.time_modified_radio.setChecked(True)
        elif primary == 'file_created':
            self.time_created_radio.setChecked(True)
        elif primary == 'custom':
            self.time_custom_radio.setChecked(True)
            self.custom_time_edit.setEnabled(True)
            custom_time_str = time_config.get('custom_time', '')
            if custom_time_str:
                try:
                    dt = datetime.strptime(custom_time_str, "%Y-%m-%d %H:%M:%S")
                    self.custom_time_edit.setDateTime(QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second))
                except:
                    pass

        self.time_custom_radio.toggled.connect(lambda checked: self.custom_time_edit.setEnabled(checked))

        time_layout.addSpacing(8)
        
        fallback_layout = QHBoxLayout()
        fallback_layout.addWidget(QLabel(L("When EXIF unavailable&当EXIF不可用时:")))
        self.fallback_combo = QComboBox()
        self.fallback_combo.addItem(L("Throw error and abort&抛出异常并中止"), "error")
        self.fallback_combo.addItem(L("Use file modified time&使用文件修改时间"), "file_modified")
        self.fallback_combo.addItem(L("Use file created time&使用文件创建时间"), "file_created")
        self.fallback_combo.addItem(L("Use custom time&使用自定义时间"), "custom")
        
        fallback_mode = time_config.get('fallback_mode', 'error')
        for i in range(self.fallback_combo.count()):
            if self.fallback_combo.itemData(i) == fallback_mode:
                self.fallback_combo.setCurrentIndex(i)
                break
        
        fallback_layout.addWidget(self.fallback_combo)
        time_layout.addLayout(fallback_layout)

        layout.addWidget(time_group)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        reset_btn = QPushButton(L("Reset to Default&恢复默认"))
        reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton(L("Cancel&取消"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(L("Save&保存"))
        save_btn.setMinimumWidth(90)
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_dir_option_changed(self):
        enabled = self.custom_dir_radio.isChecked()
        self.output_dir_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)

    def _browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, L("Browse&浏览"))
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _reset_settings(self):
        self.config = self.config_manager.get_default()
        # Could reload UI here
        self.language_combo.setCurrentIndex(1)  # zh
        self.restore_session_check.setChecked(True)
        self.same_dir_radio.setChecked(True)
        self.filename_pattern_edit.setText("{original}_stamped")
        self.quality_spin.setValue(95)
        self.preserve_exif_check.setChecked(True)
        self.overwrite_check.setChecked(False)
        self.time_exif_radio.setChecked(True)
        self.fallback_combo.setCurrentIndex(0)

    def _save_and_close(self):
        new_lang = self.language_combo.currentData()
        self.config['general']['language'] = new_lang
        self.config['general']['restore_last_session'] = self.restore_session_check.isChecked()
        LocalizationManager.set_language(new_lang)

        if self.time_exif_radio.isChecked():
            primary = 'exif'
        elif self.time_modified_radio.isChecked():
            primary = 'file_modified'
        elif self.time_created_radio.isChecked():
            primary = 'file_created'
        else:
            primary = 'custom'

        custom_time = ""
        if self.time_custom_radio.isChecked():
            dt = self.custom_time_edit.dateTime().toPyDateTime()
            custom_time = dt.strftime("%Y-%m-%d %H:%M:%S")

        self.config['time_source'] = {
            'primary': primary,
            'fallback_mode': self.fallback_combo.currentData(),
            'custom_time': custom_time
        }

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

    def get_config(self) -> dict:
        return self.config


# ==================== About Dialog&关于对话框 ====================

class AboutDialog(QDialog):
    """About Dialog&关于对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(L("About Photo Timestamper&关于照片时间戳"))
        self.setFixedSize(420, 480)

        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QSize

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedHeight(100)
        logo_path = get_base_path() / "assets" / "logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled = pixmap.scaled(
                QSize(80, 80),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(scaled)
        else:
            logo_label.setText("📷")
            logo_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(logo_label)

        layout.addSpacing(16)

        name_label = QLabel("Photo Timestamper")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(name_label)

        layout.addSpacing(4)

        version_label = QLabel(L("Version {version}&版本 {version}").replace("{version}", __version__))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(12)

        desc_label = QLabel(L("A professional tool for adding timestamp watermarks to photos&为照片添加仿相机原厂风格的时间戳水印工具"))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addSpacing(20)

        author_title = QLabel(L("Author&作者"))
        author_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_title.setStyleSheet("color: #888;")
        layout.addWidget(author_title)

        author_name = QLabel(__author__)
        author_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_name)

        layout.addSpacing(12)

        collab_title = QLabel(L("Collaborators&协作"))
        collab_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collab_title.setStyleSheet("color: #888;")
        layout.addWidget(collab_title)

        collab_names = QLabel(" · ".join(__collaborators__))
        collab_names.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(collab_names)

        layout.addStretch()

        license_label = QLabel("GPL-3.0")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setStyleSheet("color: #888;")
        layout.addWidget(license_label)

        layout.addSpacing(12)

        github_btn = QPushButton(L("GitHub Repository&GitHub仓库"))
        github_btn.setFixedHeight(36)
        github_btn.clicked.connect(self._open_github)
        layout.addWidget(github_btn)

        layout.addSpacing(8)

        close_btn = QPushButton(L("Close&关闭"))
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _open_github(self):
        import webbrowser
        webbrowser.open("https://github.com/Water-Run/photo-timestamper")


# ==================== Import Dialog&导入对话框 ====================

class ImportDialog(QDialog):
    """Import Images Dialog&导入图片对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(L("Import Images&导入图片"))
        self.setFixedSize(380, 220)

        self.selected_files: list[str] = []
        self.recursive = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        info_label = QLabel(L("Select import method:&选择导入方式："))
        layout.addWidget(info_label)

        self.recursive_check = QCheckBox(L("Scan subfolders recursively&递归扫描子文件夹"))
        self.recursive_check.setChecked(True)
        layout.addWidget(self.recursive_check)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        file_btn = QPushButton(L("Select Image Files&选择图片文件"))
        file_btn.setMinimumHeight(36)
        file_btn.clicked.connect(self._select_files)
        btn_layout.addWidget(file_btn)

        folder_btn = QPushButton(L("Select Folder&选择文件夹"))
        folder_btn.setMinimumHeight(36)
        folder_btn.clicked.connect(self._select_folder)
        btn_layout.addWidget(folder_btn)

        layout.addLayout(btn_layout)

        cancel_btn = QPushButton(L("Cancel&取消"))
        cancel_btn.setMinimumHeight(32)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            L("Select Image Files&选择图片文件"),
            "",
            L("JPEG Images (*.jpg *.jpeg *.JPG *.JPEG)&JPEG图片 (*.jpg *.jpeg *.JPG *.JPEG)")
        )
        if files:
            self.selected_files = files
            self.recursive = self.recursive_check.isChecked()
            self.accept()

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, L("Select Folder&选择文件夹"))
        if folder:
            recursive = self.recursive_check.isChecked()
            self.selected_files = scan_images(folder, recursive=recursive)
            self.recursive = recursive
            self.accept()

    def get_files(self) -> list[str]:
        return self.selected_files


# ==================== Language Selection Dialog&语言选择对话框 ====================

class LanguageSelectDialog(QDialog):
    """First Run Language Selection Dialog&首次运行语言选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Language / 选择语言")
        self.setFixedSize(380, 240)
        self.selected_language = "zh"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Select Language / 选择语言")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("Please select your preferred language:\n请选择您偏好的语言：")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(8)

        self.language_combo = QComboBox()
        self.language_combo.setMinimumHeight(38)
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("简体中文", "zh")
        self.language_combo.setCurrentIndex(1)  # Default to Chinese
        layout.addWidget(self.language_combo)

        layout.addStretch()

        confirm_btn = QPushButton("Confirm / 确定")
        confirm_btn.setMinimumHeight(38)
        confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(confirm_btn)

    def _confirm(self):
        self.selected_language = self.language_combo.currentData()
        self.accept()

    def get_selected_language(self) -> str:
        return self.selected_language


# ==================== Main Window&主窗口 ====================

class MainWindow(QMainWindow):
    """Main Window - QtWebEngine Version&主窗口 - QtWebEngine版本"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.style_manager = StyleManager()

        # Set language
        saved_lang = self.config.get('general', {}).get('language', 'zh')
        if saved_lang:
            LocalizationManager.set_language(saved_lang)

        self.processing_thread: ProcessingThread | None = None

        self._init_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._load_ui_state()

        # First run check
        if self.config_manager.is_first_run():
            QTimer.singleShot(100, self._show_language_selection)
        else:
            if self.config.get('general', {}).get('restore_last_session', True):
                QTimer.singleShot(500, self._restore_last_session)

    def _init_ui(self):
        self.setWindowTitle(L("Photo Timestamper&照片时间戳"))
        self.setMinimumSize(1200, 700)

        # Set application icon
        icon_path = get_base_path() / "assets" / "logo.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            icon_path = get_base_path() / "assets" / "logo.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))

        # Create WebEngine view
        self.web_view = QWebEngineView()

        # Create WebChannel and Bridge
        self.bridge = WebBridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Load HTML
        self.web_view.setHtml(get_html_content())

        # Set as central widget
        self.setCentralWidget(self.web_view)

        # Status bar
        self.statusBar().showMessage(L("Ready&就绪"))

    def _setup_menu(self):
        """Setup menu bar&设置菜单栏"""
        from PyQt6.QtGui import QAction

        menubar = self.menuBar()
        menubar.clear()

        # Images Menu (renamed from File)
        images_menu = menubar.addMenu(L("Images&图片"))

        import_action = QAction(L("Import Images...&导入图片..."), self)
        import_action.setShortcut("Ctrl+O")
        import_action.triggered.connect(self._show_import_dialog)
        images_menu.addAction(import_action)

        import_folder_action = QAction(L("Import Folder...&导入文件夹..."), self)
        import_folder_action.setShortcut("Ctrl+Shift+O")
        import_folder_action.triggered.connect(self._import_folder)
        images_menu.addAction(import_folder_action)

        images_menu.addSeparator()

        clear_action = QAction(L("Clear List&清空列表"), self)
        clear_action.setShortcut("Ctrl+Shift+Delete")
        clear_action.triggered.connect(self._clear_files)
        images_menu.addAction(clear_action)

        images_menu.addSeparator()

        exit_action = QAction(L("Exit&退出"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        images_menu.addAction(exit_action)

        # Software Menu (merged Edit + Help)
        software_menu = menubar.addMenu(L("Software&软件"))

        settings_action = QAction(L("Settings...&设置..."), self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        software_menu.addAction(settings_action)

        software_menu.addSeparator()

        about_action = QAction(L("About&关于"), self)
        about_action.triggered.connect(self._show_about)
        software_menu.addAction(about_action)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts&设置快捷键"""
        process_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        process_shortcut.activated.connect(self._start_processing)

    def _show_language_selection(self):
        """Show language selection dialog&显示语言选择对话框"""
        dialog = LanguageSelectDialog(self)
        if dialog.exec():
            selected_lang = dialog.get_selected_language()
            LocalizationManager.set_language(selected_lang)
            self.config['general']['language'] = selected_lang
            self.config_manager.save(self.config)
            self.config_manager.set_first_run_complete()
            self._update_ui_texts()

    def _show_import_dialog(self):
        """Show import dialog&显示导入对话框"""
        dialog = ImportDialog(self)
        if dialog.exec():
            files = dialog.get_files()
            if files:
                self._add_files(files)

    def _import_folder(self):
        """Import folder directly&直接导入文件夹"""
        folder = QFileDialog.getExistingDirectory(self, L("Select Folder&选择文件夹"))
        if folder:
            files = scan_images(folder, recursive=True)
            if files:
                self._add_files(files)

    def _add_files(self, files: list[str]):
        """Add files&添加文件"""
        added, duplicates = self.bridge.add_files(files)

        if duplicates > 0:
            self.statusBar().showMessage(
                L("Added {count} images&已添加 {count} 张图片").replace("{count}", str(added)) + 
                " | " + 
                L("Skipped {count} duplicate images&跳过 {count} 张重复图片").replace("{count}", str(duplicates))
            )
        else:
            self.statusBar().showMessage(L("Added {count} images&已添加 {count} 张图片").replace("{count}", str(added)))

    def _clear_files(self):
        """Clear files&清空文件"""
        self.bridge.requestClearFiles()

    def _show_settings(self):
        """Show settings dialog&显示设置对话框"""
        dialog = SettingsDialog(self.config_manager, self)
        if dialog.exec():
            self.config = self.config_manager.load()
            self._update_ui_texts()
            self.statusBar().showMessage(L("Settings saved&设置已保存"))

    def _show_about(self):
        """Show about dialog&显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _update_preview(self, filepath: str):
        """Update preview&更新预览"""
        try:
            image = Image.open(filepath)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Original preview
            original_copy = image.copy()
            original_copy.thumbnail((1800, 1350), Image.Resampling.LANCZOS)
            original_buffer = BytesIO()
            original_copy.save(original_buffer, format='JPEG', quality=85)
            original_b64 = f"data:image/jpeg;base64,{base64.b64encode(original_buffer.getvalue()).decode('utf-8')}"

            # Effect preview
            style_name = self.config.get('ui', {}).get('last_style', 'CANON&佳能')
            style = self.style_manager.load_style(style_name)

            time_config = self.config.get('time_source', {})
            extractor = TimeExtractor(
                primary=time_config.get('primary', 'exif'),
                fallback_mode=time_config.get('fallback_mode', 'error'),
                custom_time=time_config.get('custom_time', '')
            )
            
            try:
                timestamp = extractor.extract(filepath)
            except:
                timestamp = datetime.now()

            renderer = WatermarkRenderer(style, self.style_manager.fonts_dir)
            result = renderer.render_preview(image, timestamp, (1800, 1350))

            result_buffer = BytesIO()
            result.save(result_buffer, format='JPEG', quality=85)
            result_b64 = f"data:image/jpeg;base64,{base64.b64encode(result_buffer.getvalue()).decode('utf-8')}"

            self.bridge.previewUpdated.emit(original_b64, result_b64)

        except Exception as e:
            logger.error(f"Failed to generate preview&生成预览失败: {e}")
            self.bridge.previewUpdated.emit('', '')

    def _start_processing(self):
        """Start processing (from menu or shortcut)&开始处理（从菜单或快捷键）"""
        checked = [item['path'] for item in self.bridge._file_list if item.get('checked')]
        if checked:
            files = checked
        else:
            files = self.bridge.get_all_files()

        if not files:
            QMessageBox.warning(self, L("Photo Timestamper&照片时间戳"), L("Please add images first&请先添加图片"))
            return

        style_name = self.config.get('ui', {}).get('last_style', 'CANON&佳能')
        self._start_processing_with_files(files, style_name)

    def _start_processing_with_files(self, files: list[str], style_name: str):
        """Start processing with specified files&使用指定文件开始处理"""
        processor = BatchProcessor(self.config, self.style_manager)

        self.processing_thread = ProcessingThread(processor, files, style_name)
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.preview.connect(self._on_processing_preview)
        self.processing_thread.finished.connect(self._on_finished)
        self.processing_thread.error.connect(self._on_error)

        self.bridge.showProgressOverlay.emit(True)
        self.processing_thread.start()

    def _cancel_processing(self):
        """Cancel processing&取消处理"""
        if self.processing_thread:
            self.processing_thread.cancel()
            self.statusBar().showMessage(L("Cancelling...&正在取消..."))

    def _on_progress(self, current: int, total: int, filename: str):
        """Update progress&更新进度"""
        self.bridge.progressUpdated.emit(current, total, filename)
        self.statusBar().showMessage(
            L("Exporting {current}/{total}&导出第 {current}/{total} 张").replace("{current}", str(current)).replace("{total}", str(total)) + 
            f": {filename}"
        )

    def _on_processing_preview(self, filepath: str, image: Image.Image):
        """Update preview during processing&处理时更新预览"""
        try:
            buffer = BytesIO()
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(buffer, format='JPEG', quality=85)
            result_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
            self.bridge.previewUpdated.emit('', result_b64)
        except Exception as e:
            logger.debug(f"Preview update failed&预览更新失败: {e}")

    def _on_finished(self, results: dict):
        """Processing finished&处理完成"""
        self.bridge.showProgressOverlay.emit(False)

        success = results.get('success', 0)
        failed = results.get('failed', 0)

        self.statusBar().showMessage(
            L("Complete: {success} succeeded, {failed} failed&处理完成：成功 {success} 张，失败 {failed} 张")
            .replace("{success}", str(success))
            .replace("{failed}", str(failed))
        )

        if failed == 0:
            QMessageBox.information(
                self, 
                L("Photo Timestamper&照片时间戳"), 
                L("Successfully processed {count} images&成功处理 {count} 张图片").replace("{count}", str(success))
            )

    def _on_error(self, error: str):
        """Processing error&处理错误"""
        self.bridge.processingError.emit(L(error))
        self.statusBar().showMessage(L("Processing error&处理出错"))

    def _update_ui_texts(self):
        """Update all UI texts&更新所有UI文本"""
        self.setWindowTitle(L("Photo Timestamper&照片时间戳"))
        self._setup_menu()

        # Notify web to update texts
        translations = json.dumps({
            "app_name": L("Photo Timestamper&照片时间戳"),
            "panel_image_list": L("Image List&图片列表"),
            "panel_watermark_style": L("Watermark Style&水印样式"),
            "search_placeholder": L("Search images...&搜索图片..."),
            "btn_add_images": L("Add Images&添加图片"),
            "btn_select_all": L("Select All&全选"),
            "btn_clear_list": L("Clear&清空"),
            "btn_process": L("Start Processing&开始处理"),
            "btn_cancel": L("Cancel&取消"),
            "preview_original": L("Original&原图"),
            "preview_result": L("Preview&效果预览"),
            "preview_no_image": L("Select an image to preview&选择图片以预览"),
            "drop_hint": L("Drop images or folders here\\nor click button below to add&将图片或文件夹拖放到此处\\n或点击下方按钮添加"),
            "msg_ready": L("Ready&就绪"),
            "ctx_check_selected": L("Check Selected&勾选选中项"),
            "ctx_uncheck_selected": L("Uncheck Selected&取消勾选选中项"),
            "ctx_select_all": L("Select All&全选"),
            "ctx_deselect_all": L("Deselect All&取消全选"),
            "ctx_open_file": L("Open File&打开文件"),
            "ctx_open_folder": L("Open Containing Folder&打开所在文件夹"),
            "ctx_remove_selected": L("Remove Selected&移除选中项"),
            "ctx_clear_all": L("Clear All&清空所有"),
        }, ensure_ascii=False)
        self.bridge.uiTextsUpdated.emit(translations)

        self.statusBar().showMessage(L("Ready&就绪"))

    def _load_ui_state(self):
        """Load UI state&加载UI状态"""
        geometry = self.config.get('ui', {}).get('window_geometry', '')
        if geometry:
            try:
                self.restoreGeometry(bytes.fromhex(geometry))
            except:
                pass

    def _save_ui_state(self):
        """Save UI state&保存UI状态"""
        self.config['ui']['window_geometry'] = self.saveGeometry().toHex().data().decode()
        self.config_manager.save(self.config)

    def _restore_last_session(self):
        """Restore last session&恢复上次会话"""
        files = self.config_manager.get_last_session_files()
        if files:
            existing_files = [f for f in files if Path(f).exists()]
            if existing_files:
                self._add_files(existing_files)

    def _save_session(self):
        """Save current session&保存当前会话"""
        if self.config.get('general', {}).get('restore_last_session', True):
            files = self.bridge.get_all_files()
            self.config_manager.save_session_files(files)
        else:
            self.config_manager.clear_session_files()

    def closeEvent(self, event):
        """Window close event&窗口关闭事件"""
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self,
                L("Confirm Exit&确认退出"),
                L("Processing in progress. Are you sure you want to exit?&正在处理图片，确定要退出吗？"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.processing_thread.cancel()
            self.processing_thread.wait()

        self._save_session()
        self._save_ui_state()
        event.accept()


def run_app():
    """Run application&运行应用程序"""
    app = QApplication(sys.argv)
    app.setApplicationName("Photo Timestamper")
    app.setOrganizationName("PhotoTimestamper")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
    
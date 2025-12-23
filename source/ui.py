# ui.py
"""
Photo-Timestamper PyQt6 用户界面
Lightroom 风格专业界面 - QtWebEngine 版本 v2.0
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
    QComboBox, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, pyqtSlot, QObject, QTimer
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from PIL import Image

from .core import (
    ConfigManager, StyleManager, BatchProcessor, TimeExtractor,
    WatermarkRenderer, scan_images, get_base_path, logger
)
from .i18n import I18n, t, LANGUAGE_NAMES
from . import __version__, __author__, __collaborators__


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


# ==================== Web Bridge ====================

class WebBridge(QObject):
    """Python 与 JavaScript 的桥接对象"""

    # 信号定义
    filesAdded = pyqtSignal(str)  # JSON string
    previewUpdated = pyqtSignal(str, str)  # original, result (base64)
    progressUpdated = pyqtSignal(int, int, str)
    processingFinished = pyqtSignal(str)  # JSON result
    statusMessage = pyqtSignal(str)
    uiTextsUpdated = pyqtSignal(str)  # JSON translations

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._file_list: list[dict] = []  # {path, name, checked, thumbnail}
        self._thumbnails: dict[str, str] = {}  # path -> base64

    @pyqtSlot(result=str)
    def getTranslations(self) -> str:
        """获取所有翻译文本"""
        translations = {
            "app_name": t("app_name"),
            "panel_image_list": t("panel_image_list"),
            "panel_watermark_style": t("panel_watermark_style"),
            "search_placeholder": t("search_placeholder"),
            "image_count": t("image_count", count=0),
            "btn_add_images": t("btn_add_images"),
            "btn_add_folder": t("btn_add_folder"),
            "btn_clear_list": t("btn_clear_list"),
            "btn_select_all": t("btn_select_all"),
            "btn_process": t("btn_process"),
            "btn_process_selected": t("btn_process_selected"),
            "btn_cancel": t("btn_cancel"),
            "preview_original": t("preview_original"),
            "preview_result": t("preview_result"),
            "preview_no_image": t("preview_no_image"),
            "drop_hint": t("drop_hint"),
            "processing": t("processing"),
            "msg_ready": t("msg_ready"),
            "ctx_check_selected": t("ctx_check_selected"),
            "ctx_uncheck_selected": t("ctx_uncheck_selected"),
            "ctx_select_all": t("ctx_select_all"),
            "ctx_deselect_all": t("ctx_deselect_all"),
            "ctx_open_file": t("ctx_open_file"),
            "ctx_open_folder": t("ctx_open_folder"),
            "ctx_remove_selected": t("ctx_remove_selected"),
            "ctx_clear_all": t("ctx_clear_all"),
        }
        return json.dumps(translations, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getStyles(self) -> str:
        """获取可用样式列表"""
        styles = self.main_window.style_manager.list_styles()
        last_style = self.main_window.config.get('ui', {}).get('last_style', '佳能')
        return json.dumps({
            "styles": styles,
            "current": last_style if last_style in styles else (styles[0] if styles else "")
        }, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getFileList(self) -> str:
        """获取文件列表"""
        return json.dumps(self._file_list, ensure_ascii=False)

    @pyqtSlot()
    def requestAddFiles(self):
        """请求添加文件"""
        self.main_window._show_import_dialog()

    @pyqtSlot()
    def requestAddFolder(self):
        """请求添加文件夹"""
        self.main_window._import_folder()

    @pyqtSlot()
    def requestClearFiles(self):
        """请求清空文件"""
        self._file_list.clear()
        self._thumbnails.clear()
        self.filesAdded.emit(json.dumps(self._file_list))
        self.statusMessage.emit(t("msg_cleared"))

    @pyqtSlot(str)
    def setFileChecked(self, data: str):
        """设置文件勾选状态"""
        info = json.loads(data)
        path = info.get('path')
        checked = info.get('checked', False)
        for item in self._file_list:
            if item['path'] == path:
                item['checked'] = checked
                break

    @pyqtSlot()
    def checkAll(self):
        """全选"""
        for item in self._file_list:
            item['checked'] = True
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot()
    def uncheckAll(self):
        """取消全选"""
        for item in self._file_list:
            item['checked'] = False
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot(str)
    def checkSelected(self, selected_json: str):
        """勾选选中项"""
        selected = set(json.loads(selected_json))
        for item in self._file_list:
            if item['path'] in selected:
                item['checked'] = True
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot(str)
    def uncheckSelected(self, selected_json: str):
        """取消勾选选中项"""
        selected = set(json.loads(selected_json))
        for item in self._file_list:
            if item['path'] in selected:
                item['checked'] = False
        self.filesAdded.emit(json.dumps(self._file_list))

    @pyqtSlot(str)
    def removeSelected(self, selected_json: str):
        """移除选中项"""
        selected = set(json.loads(selected_json))
        self._file_list = [item for item in self._file_list if item['path'] not in selected]
        for path in selected:
            self._thumbnails.pop(path, None)
        self.filesAdded.emit(json.dumps(self._file_list))
        self.statusMessage.emit(t("msg_removed", count=len(selected)))

    @pyqtSlot(str)
    def selectFile(self, filepath: str):
        """选择文件进行预览"""
        self.main_window._update_preview(filepath)

    @pyqtSlot(str)
    def setStyle(self, style_name: str):
        """设置当前样式"""
        self.main_window.config['ui']['last_style'] = style_name
        self.main_window.config_manager.save(self.main_window.config)

    @pyqtSlot(str)
    def startProcessing(self, style_name: str):
        """开始处理"""
        checked = [item['path'] for item in self._file_list if item.get('checked')]
        if checked:
            files = checked
        else:
            files = [item['path'] for item in self._file_list]

        if not files:
            QMessageBox.warning(self.main_window, t("app_name"), t("msg_no_images"))
            return

        self.main_window._start_processing_with_files(files, style_name)

    @pyqtSlot()
    def cancelProcessing(self):
        """取消处理"""
        self.main_window._cancel_processing()

    @pyqtSlot(str)
    def openFile(self, filepath: str):
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

    @pyqtSlot(str)
    def openFolder(self, filepath: str):
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

    @pyqtSlot()
    def showSettings(self):
        """显示设置"""
        self.main_window._show_settings()

    @pyqtSlot()
    def showAbout(self):
        """显示关于"""
        self.main_window._show_about()

    def add_files(self, files: list[str]) -> tuple[int, int]:
        """添加文件到列表"""
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

        # 异步加载缩略图
        for item in self._file_list:
            if not item['thumbnail'] and item['path'] not in self._thumbnails:
                QTimer.singleShot(50, lambda p=item['path']: self._load_thumbnail(p))

        self.filesAdded.emit(json.dumps(self._file_list))
        return added, duplicates

    def _load_thumbnail(self, filepath: str):
        """加载缩略图"""
        try:
            if filepath in self._thumbnails:
                return

            image = Image.open(filepath)
            image.thumbnail((144, 108), Image.Resampling.LANCZOS)

            if image.mode != 'RGB':
                image = image.convert('RGB')

            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=80)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            self._thumbnails[filepath] = f"data:image/jpeg;base64,{b64}"

            # 更新列表中的缩略图
            for item in self._file_list:
                if item['path'] == filepath:
                    item['thumbnail'] = self._thumbnails[filepath]
                    break

            self.filesAdded.emit(json.dumps(self._file_list))

        except Exception as e:
            logger.debug(f"加载缩略图失败: {e}")

    def get_all_files(self) -> list[str]:
        """获取所有文件"""
        return [item['path'] for item in self._file_list]

    def get_checked_count(self) -> int:
        """获取勾选数量"""
        return sum(1 for item in self._file_list if item.get('checked'))


# ==================== HTML 模板 ====================

def get_html_content() -> str:
    """生成完整的 HTML 内容"""
    return '''<!DOCTYPE html>
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
            --accent-red: #d32f2f;
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

        /* 主布局 */
        .main-container {
            display: flex;
            height: 100vh;
        }

        /* 左侧面板 */
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

        /* 列表头部 */
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

        /* 搜索框 */
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

        /* 文件列表 */
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

        /* 空状态提示 */
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

        /* 文件项 */
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

        .file-item.drag-over {
            border: 2px dashed var(--accent-blue);
        }

        /* 勾选标记 */
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

        /* 缩略图 */
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

        /* 文件名 */
        .file-name {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 12px;
        }

        /* 按钮组 */
        .button-group {
            display: flex;
            gap: 6px;
            margin-top: 8px;
        }

        /* 按钮 */
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
            background-color: #e53935;
        }

        .btn-large {
            padding: 10px 16px;
            font-size: 13px;
            min-height: 40px;
        }

        /* 样式选择器 */
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

        /* 进度区域 */
        .progress-section {
            display: none;
            margin-top: 12px;
        }

        .progress-section.visible {
            display: block;
        }

        .progress-label {
            color: var(--text-secondary);
            font-size: 11px;
            margin-bottom: 6px;
        }

        .progress-bar {
            height: 8px;
            background-color: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 10px;
        }

        .progress-fill {
            height: 100%;
            background-color: var(--accent-blue);
            border-radius: 4px;
            transition: width 0.3s ease;
            width: 0%;
        }

        /* 处理按钮区域 */
        .process-section {
            margin-top: auto;
            padding-top: 12px;
        }

        /* 预览区域 */
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

        /* 右键菜单 */
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

        /* 拖放覆盖层 */
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

        /* 状态栏 */
        .status-bar {
            height: 28px;
            background-color: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            padding: 0 12px;
            font-size: 11px;
            color: var(--text-muted);
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <!-- 左侧面板 -->
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

            <div class="progress-section" id="progressSection">
                <div class="progress-label" id="progressLabel">处理中...</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <button class="btn btn-danger btn-large" id="btnCancel" onclick="bridge.cancelProcessing()">取消</button>
            </div>

            <div class="process-section" id="processSection">
                <button class="btn btn-primary btn-large" id="btnProcess" onclick="startProcessing()">开始处理</button>
            </div>
        </div>

        <!-- 预览区域 -->
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

    <!-- 右键菜单 -->
    <div class="context-menu" id="contextMenu">
        <div class="context-menu-item" onclick="checkSelectedItems()">勾选选中项</div>
        <div class="context-menu-item" onclick="uncheckSelectedItems()">取消勾选选中项</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" onclick="selectAllItems()">全选</div>
        <div class="context-menu-item" onclick="deselectAllItems()">取消全选</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" id="menuOpenFile" onclick="openCurrentFile()">打开文件</div>
        <div class="context-menu-item" id="menuOpenFolder" onclick="openCurrentFolder()">打开所在文件夹</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" onclick="removeSelectedItems()">移除选中项</div>
        <div class="context-menu-item" onclick="bridge.requestClearFiles()">清空所有</div>
    </div>

    <!-- 拖放覆盖层 -->
    <div class="drop-overlay" id="dropOverlay">
        <div class="drop-overlay-text">释放以添加图片</div>
    </div>

    <!-- 状态栏 -->
    <div class="status-bar" id="statusBar">就绪</div>

    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        let bridge = null;
        let fileList = [];
        let selectedPaths = new Set();
        let currentContextPath = null;
        let isProcessing = false;

        // 初始化 WebChannel
        new QWebChannel(qt.webChannelTransport, function(channel) {
            bridge = channel.objects.bridge;
            
            // 连接信号
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

            bridge.statusMessage.connect(function(message) {
                document.getElementById('statusBar').textContent = message;
            });

            bridge.uiTextsUpdated.connect(function(textsJson) {
                updateUITexts(JSON.parse(textsJson));
            });

            // 初始化
            initializeUI();
        });

        function initializeUI() {
            // 获取翻译
            const texts = JSON.parse(bridge.getTranslations());
            updateUITexts(texts);

            // 获取样式
            const stylesData = JSON.parse(bridge.getStyles());
            const styleSelect = document.getElementById('styleSelect');
            styleSelect.innerHTML = '';
            stylesData.styles.forEach(style => {
                const option = document.createElement('option');
                option.value = style;
                option.textContent = style;
                if (style === stylesData.current) {
                    option.selected = true;
                }
                styleSelect.appendChild(option);
            });

            // 获取文件列表
            fileList = JSON.parse(bridge.getFileList());
            renderFileList();
        }

        function updateUITexts(texts) {
            document.getElementById('panelTitle').textContent = texts.panel_image_list || '图片列表';
            document.getElementById('searchBox').placeholder = texts.search_placeholder || '搜索图片...';
            document.getElementById('btnAdd').textContent = texts.btn_add_images || '添加图片';
            document.getElementById('btnSelectAll').textContent = texts.btn_select_all || '全选';
            document.getElementById('btnClear').textContent = texts.btn_clear_list || '清空';
            document.getElementById('styleTitle').textContent = texts.panel_watermark_style || '水印样式';
            document.getElementById('btnProcess').textContent = texts.btn_process || '开始处理';
            document.getElementById('btnCancel').textContent = texts.btn_cancel || '取消';
            document.getElementById('originalTitle').textContent = texts.preview_original || '原图';
            document.getElementById('resultTitle').textContent = texts.preview_result || '效果预览';
            document.getElementById('originalPlaceholder').textContent = texts.preview_no_image || '选择图片以预览';
            document.getElementById('resultPlaceholder').textContent = texts.preview_no_image || '选择图片以预览';
            document.getElementById('emptyHint').innerHTML = (texts.drop_hint || '将图片或文件夹拖放到此处<br>或点击下方按钮添加').replace('\\n', '<br>');
            document.getElementById('statusBar').textContent = texts.msg_ready || '就绪';
        }

        function renderFileList() {
            const container = document.getElementById('fileList');
            const emptyHint = document.getElementById('emptyHint');
            const searchBox = document.getElementById('searchBox');
            const searchText = searchBox.value.toLowerCase();

            // 清空现有内容
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

                item.innerHTML = `
                    <div class="checkmark ${file.checked ? 'checked' : ''}" onclick="toggleCheck(event, '${escapeHtml(file.path)}')"></div>
                    <div class="thumbnail">
                        ${file.thumbnail ? `<img src="${file.thumbnail}">` : '<span class="thumbnail-placeholder">...</span>'}
                    </div>
                    <span class="file-name">${escapeHtml(file.name)}</span>
                `;

                item.addEventListener('click', (e) => onItemClick(e, file.path));
                item.addEventListener('dblclick', (e) => onItemDoubleClick(e, file.path));
                item.addEventListener('contextmenu', (e) => onItemContextMenu(e, file.path));

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
                bridge.setFileChecked(JSON.stringify({path: path, checked: file.checked}));
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
                // Shift 多选
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
                bridge.selectFile(path);
            }
            renderFileList();
        }

        function onItemDoubleClick(event, path) {
            const file = fileList.find(f => f.path === path);
            if (file) {
                file.checked = !file.checked;
                bridge.setFileChecked(JSON.stringify({path: path, checked: file.checked}));
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

            const menu = document.getElementById('contextMenu');
            menu.style.left = event.clientX + 'px';
            menu.style.top = event.clientY + 'px';
            menu.classList.add('visible');
        }

        function selectAllFiles() {
            bridge.checkAll();
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
            bridge.checkSelected(JSON.stringify(Array.from(selectedPaths)));
            hideContextMenu();
        }

        function uncheckSelectedItems() {
            bridge.uncheckSelected(JSON.stringify(Array.from(selectedPaths)));
            hideContextMenu();
        }

        function removeSelectedItems() {
            bridge.removeSelected(JSON.stringify(Array.from(selectedPaths)));
            selectedPaths.clear();
            hideContextMenu();
        }

        function openCurrentFile() {
            if (currentContextPath) {
                bridge.openFile(currentContextPath);
            }
            hideContextMenu();
        }

        function openCurrentFolder() {
            if (currentContextPath) {
                bridge.openFolder(currentContextPath);
            }
            hideContextMenu();
        }

        function hideContextMenu() {
            document.getElementById('contextMenu').classList.remove('visible');
        }

        function onStyleChange() {
            const style = document.getElementById('styleSelect').value;
            bridge.setStyle(style);
            // 如果有选中的文件，更新预览
            if (selectedPaths.size === 1) {
                bridge.selectFile(Array.from(selectedPaths)[0]);
            }
        }

        function startProcessing() {
            const style = document.getElementById('styleSelect').value;
            bridge.startProcessing(style);
        }

        function setProcessingState(processing) {
            isProcessing = processing;
            document.getElementById('processSection').style.display = processing ? 'none' : 'block';
            document.getElementById('progressSection').classList.toggle('visible', processing);
            document.getElementById('btnAdd').disabled = processing;
            document.getElementById('btnClear').disabled = processing;
            document.getElementById('btnSelectAll').disabled = processing;
            document.getElementById('styleSelect').disabled = processing;
        }

        function updateProgress(current, total, filename) {
            setProcessingState(true);
            const percent = (current / total) * 100;
            document.getElementById('progressFill').style.width = percent + '%';
            document.getElementById('progressLabel').textContent = `处理中 ${current}/${total}: ${filename}`;
        }

        function onProcessingFinished(result) {
            setProcessingState(false);
            document.getElementById('progressFill').style.width = '0%';
        }

        function updatePreview(originalBase64, resultBase64) {
            const originalImg = document.getElementById('originalImage');
            const originalPlaceholder = document.getElementById('originalPlaceholder');
            const resultImg = document.getElementById('resultImage');
            const resultPlaceholder = document.getElementById('resultPlaceholder');

            if (originalBase64) {
                originalImg.src = originalBase64;
                originalImg.style.display = 'block';
                originalPlaceholder.style.display = 'none';
            } else {
                originalImg.style.display = 'none';
                originalPlaceholder.style.display = 'block';
            }

            if (resultBase64) {
                resultImg.src = resultBase64;
                resultImg.style.display = 'block';
                resultPlaceholder.style.display = 'none';
            } else {
                resultImg.style.display = 'none';
                resultPlaceholder.style.display = 'block';
            }
        }

        function updateListInfo() {
            const total = fileList.length;
            const checked = fileList.filter(f => f.checked).length;
            const info = document.getElementById('listInfo');
            const btn = document.getElementById('btnProcess');
            
            if (checked > 0) {
                info.textContent = `已选择 ${checked} / ${total} 张`;
                btn.textContent = '处理选中';
            } else {
                info.textContent = `共 ${total} 张图片`;
                btn.textContent = '开始处理';
            }
        }

        // 搜索过滤
        document.getElementById('searchBox').addEventListener('input', function() {
            renderFileList();
        });

        // 点击空白处关闭右键菜单
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.context-menu')) {
                hideContextMenu();
            }
        });

        // 拖放处理
        document.addEventListener('dragenter', function(e) {
            e.preventDefault();
            document.getElementById('dropOverlay').classList.add('visible');
        });

        document.addEventListener('dragleave', function(e) {
            if (e.target === document.getElementById('dropOverlay')) {
                document.getElementById('dropOverlay').classList.remove('visible');
            }
        });

        document.addEventListener('dragover', function(e) {
            e.preventDefault();
        });

        document.addEventListener('drop', function(e) {
            e.preventDefault();
            document.getElementById('dropOverlay').classList.remove('visible');
            // 拖放处理由 Python 端处理
        });

        // 键盘快捷键
        document.addEventListener('keydown', function(e) {
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


# ==================== 设置对话框 ====================

class SettingsDialog(QDialog):
    """设置对话框 - 保持原有实现"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config = config_manager.load()

        self.setWindowTitle(t("settings_title"))
        self.setMinimumSize(480, 520)

        from PyQt6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
            QGroupBox, QRadioButton, QButtonGroup, QCheckBox,
            QLineEdit, QSpinBox, QLabel, QPushButton, QComboBox
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget, stretch=1)

        # 常规标签页
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(12, 12, 12, 12)

        lang_group = QGroupBox(t("settings_language"))
        lang_layout = QVBoxLayout(lang_group)
        self.language_combo = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, code)
        current_lang = self.config.get('general', {}).get('language', 'zh-CN')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break
        lang_layout.addWidget(self.language_combo)
        general_layout.addWidget(lang_group)

        session_group = QGroupBox(t("settings_tab_general"))
        session_layout = QVBoxLayout(session_group)
        self.restore_session_check = QCheckBox(t("settings_restore_session"))
        self.restore_session_check.setChecked(
            self.config.get('general', {}).get('restore_last_session', False)
        )
        session_layout.addWidget(self.restore_session_check)
        general_layout.addWidget(session_group)
        general_layout.addStretch()
        tab_widget.addTab(general_tab, t("settings_tab_general"))

        # 输出标签页
        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        output_layout.setContentsMargins(12, 12, 12, 12)

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
        output_layout.addWidget(dir_group)

        output_config = self.config.get('output', {})
        if output_config.get('same_directory', True):
            self.same_dir_radio.setChecked(True)
        else:
            self.custom_dir_radio.setChecked(True)
        self.output_dir_edit.setText(output_config.get('custom_directory', ''))

        filename_group = QGroupBox(t("settings_filename_pattern"))
        filename_layout = QVBoxLayout(filename_group)
        self.filename_pattern_edit = QLineEdit()
        self.filename_pattern_edit.setText(output_config.get('filename_pattern', '{original}_stamped'))
        filename_layout.addWidget(self.filename_pattern_edit)
        hint_label = QLabel(t("settings_filename_tooltip"))
        hint_label.setWordWrap(True)
        filename_layout.addWidget(hint_label)
        output_layout.addWidget(filename_group)

        quality_group = QGroupBox(t("settings_jpeg_quality"))
        quality_layout = QHBoxLayout(quality_group)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(output_config.get('jpeg_quality', 95))
        self.quality_spin.setSuffix(" %")
        quality_layout.addWidget(self.quality_spin)
        quality_layout.addStretch()
        output_layout.addWidget(quality_group)

        self.preserve_exif_check = QCheckBox(t("settings_preserve_exif"))
        self.preserve_exif_check.setChecked(output_config.get('preserve_exif', True))
        output_layout.addWidget(self.preserve_exif_check)

        self.overwrite_check = QCheckBox(t("settings_overwrite"))
        self.overwrite_check.setChecked(output_config.get('overwrite_existing', False))
        output_layout.addWidget(self.overwrite_check)

        output_layout.addStretch()
        tab_widget.addTab(output_tab, t("settings_tab_output"))

        # 高级标签页
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setContentsMargins(12, 12, 12, 12)

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

        primary = self.config.get('time_source', {}).get('primary', 'exif')
        if primary == 'exif':
            self.time_exif_radio.setChecked(True)
        elif primary == 'file_modified':
            self.time_modified_radio.setChecked(True)
        else:
            self.time_created_radio.setChecked(True)

        time_layout.addSpacing(8)
        self.fallback_check = QCheckBox(t("settings_fallback"))
        self.fallback_check.setChecked(
            self.config.get('time_source', {}).get('fallback_enabled', True)
        )
        time_layout.addWidget(self.fallback_check)
        advanced_layout.addWidget(time_group)
        advanced_layout.addStretch()
        tab_widget.addTab(advanced_tab, t("settings_tab_advanced"))

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        reset_btn = QPushButton(t("settings_reset"))
        reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton(t("settings_cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(t("settings_save"))
        save_btn.setMinimumWidth(90)
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_dir_option_changed(self):
        enabled = self.custom_dir_radio.isChecked()
        self.output_dir_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)

    def _browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, t("settings_browse"))
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _reset_settings(self):
        self.config = self.config_manager.get_default()
        # 重新加载 UI

    def _save_and_close(self):
        new_lang = self.language_combo.currentData()
        self.config['general']['language'] = new_lang
        self.config['general']['restore_last_session'] = self.restore_session_check.isChecked()
        I18n.set_language(new_lang)

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


# ==================== 关于对话框 ====================

class AboutDialog(QDialog):
    """关于对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("about_title"))
        self.setFixedSize(420, 480)

        from PyQt6.QtWidgets import QVBoxLayout, QLabel, QPushButton
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
        layout.addWidget(logo_label)

        layout.addSpacing(16)

        name_label = QLabel("Photo Timestamper")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        layout.addSpacing(4)

        version_label = QLabel(t("about_version", version=__version__))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(12)

        desc_label = QLabel(t("about_description"))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addSpacing(20)

        author_title = QLabel(t("about_author"))
        author_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_title)

        author_name = QLabel(__author__)
        author_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_name)

        layout.addSpacing(12)

        collab_title = QLabel(t("about_collaborators"))
        collab_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(collab_title)

        collab_names = QLabel(" · ".join(__collaborators__))
        collab_names.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(collab_names)

        layout.addStretch()

        github_btn = QPushButton(t("about_github"))
        github_btn.setFixedHeight(36)
        github_btn.clicked.connect(self._open_github)
        layout.addWidget(github_btn)

        layout.addSpacing(8)

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

        from PyQt6.QtWidgets import QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout

        self.selected_files: list[str] = []
        self.recursive = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        info_label = QLabel(t("import_desc"))
        layout.addWidget(info_label)

        self.recursive_check = QCheckBox(t("import_recursive"))
        self.recursive_check.setChecked(True)
        layout.addWidget(self.recursive_check)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        file_btn = QPushButton(t("import_select_files"))
        file_btn.setMinimumHeight(36)
        file_btn.clicked.connect(self._select_files)
        btn_layout.addWidget(file_btn)

        folder_btn = QPushButton(t("import_select_folder"))
        folder_btn.setMinimumHeight(36)
        folder_btn.clicked.connect(self._select_folder)
        btn_layout.addWidget(folder_btn)

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


# ==================== 语言选择对话框 ====================

class LanguageSelectDialog(QDialog):
    """首次运行语言选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("language_select_title"))
        self.setFixedSize(380, 260)
        self.selected_language = "zh-CN"

        from PyQt6.QtWidgets import QVBoxLayout, QLabel, QComboBox, QPushButton

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Select Language / 选择语言")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(t("language_select_desc"))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(8)

        self.language_combo = QComboBox()
        self.language_combo.setMinimumHeight(38)
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, code)
        layout.addWidget(self.language_combo)

        layout.addStretch()

        confirm_btn = QPushButton(t("language_confirm"))
        confirm_btn.setMinimumHeight(38)
        confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(confirm_btn)

    def _confirm(self):
        self.selected_language = self.language_combo.currentData()
        self.accept()

    def get_selected_language(self) -> str:
        return self.selected_language


# ==================== 主窗口 ====================

class MainWindow(QMainWindow):
    """主窗口 - QtWebEngine 版本"""

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

        self._init_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._load_ui_state()

        # 首次运行检查
        if self.config_manager.is_first_run():
            QTimer.singleShot(100, self._show_language_selection)
        else:
            if self.config.get('general', {}).get('restore_last_session', False):
                QTimer.singleShot(500, self._restore_last_session)

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

        # 创建 WebEngine 视图
        self.web_view = QWebEngineView()

        # 创建 WebChannel 和 Bridge
        self.bridge = WebBridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # 加载 HTML
        self.web_view.setHtml(get_html_content())

        # 设置为中央部件
        self.setCentralWidget(self.web_view)

        # 状态栏
        self.statusBar().showMessage(t("msg_ready"))

    def _setup_menu(self):
        """设置菜单栏"""
        from PyQt6.QtGui import QAction

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

        settings_action = QAction(t("menu_settings"), self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        edit_menu.addAction(settings_action)

        # 帮助菜单
        help_menu = menubar.addMenu(t("menu_help"))

        about_action = QAction(t("menu_about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_shortcuts(self):
        """设置快捷键"""
        process_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        process_shortcut.activated.connect(self._start_processing)

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
        added, duplicates = self.bridge.add_files(files)

        if duplicates > 0:
            self.statusBar().showMessage(
                f"{t('msg_added_images', count=added)} | {t('msg_duplicate_skipped', count=duplicates)}"
            )
        else:
            self.statusBar().showMessage(t('msg_added_images', count=added))

    def _clear_files(self):
        """清空文件"""
        self.bridge.requestClearFiles()

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

    def _update_preview(self, filepath: str):
        """更新预览"""
        try:
            image = Image.open(filepath)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # 原图预览
            original_copy = image.copy()
            original_copy.thumbnail((1800, 1350), Image.Resampling.LANCZOS)
            original_buffer = BytesIO()
            original_copy.save(original_buffer, format='JPEG', quality=85)
            original_b64 = f"data:image/jpeg;base64,{base64.b64encode(original_buffer.getvalue()).decode('utf-8')}"

            # 效果预览
            style_name = self.config.get('ui', {}).get('last_style', '佳能')
            style = self.style_manager.load_style(style_name)

            extractor = TimeExtractor(
                primary=self.config.get('time_source', {}).get('primary', 'exif'),
                fallback_enabled=self.config.get('time_source', {}).get('fallback_enabled', True),
                fallback_to=self.config.get('time_source', {}).get('fallback_to', 'file_modified')
            )
            timestamp = extractor.extract(filepath)

            renderer = WatermarkRenderer(style, self.style_manager.fonts_dir)
            result = renderer.render_preview(image, timestamp, (1800, 1350))

            result_buffer = BytesIO()
            result.save(result_buffer, format='JPEG', quality=85)
            result_b64 = f"data:image/jpeg;base64,{base64.b64encode(result_buffer.getvalue()).decode('utf-8')}"

            self.bridge.previewUpdated.emit(original_b64, result_b64)

        except Exception as e:
            logger.error(f"生成预览失败: {e}")
            self.bridge.previewUpdated.emit('', '')

    def _start_processing(self):
        """开始处理（从菜单或快捷键）"""
        checked = [item['path'] for item in self.bridge._file_list if item.get('checked')]
        if checked:
            files = checked
        else:
            files = self.bridge.get_all_files()

        if not files:
            QMessageBox.warning(self, t("app_name"), t("msg_no_images"))
            return

        style_name = self.config.get('ui', {}).get('last_style', '佳能')
        self._start_processing_with_files(files, style_name)

    def _start_processing_with_files(self, files: list[str], style_name: str):
        """使用指定文件开始处理"""
        processor = BatchProcessor(self.config, self.style_manager)

        self.processing_thread = ProcessingThread(processor, files, style_name)
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.preview.connect(self._on_processing_preview)
        self.processing_thread.finished.connect(self._on_finished)
        self.processing_thread.error.connect(self._on_error)

        self.processing_thread.start()

    def _cancel_processing(self):
        """取消处理"""
        if self.processing_thread:
            self.processing_thread.cancel()
            self.statusBar().showMessage(t("cancelling"))

    def _on_progress(self, current: int, total: int, filename: str):
        """更新进度"""
        self.bridge.progressUpdated.emit(current, total, filename)
        self.statusBar().showMessage(t("processing_progress", current=current, total=total, filename=filename))

    def _on_processing_preview(self, filepath: str, image: Image.Image):
        """处理时更新预览"""
        try:
            buffer = BytesIO()
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(buffer, format='JPEG', quality=85)
            result_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
            self.bridge.previewUpdated.emit('', result_b64)
        except Exception as e:
            logger.debug(f"预览更新失败: {e}")

    def _on_finished(self, results: dict):
        """处理完成"""
        self.bridge.processingFinished.emit(json.dumps(results))

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
        self.bridge.processingFinished.emit(json.dumps({"success": 0, "failed": 0}))
        self.statusBar().showMessage(t("msg_process_error"))
        QMessageBox.critical(self, t("error_title"), f"{t('msg_process_error')}: {error}")

    def _update_ui_texts(self):
        """更新所有 UI 文本"""
        self.setWindowTitle(t("app_name"))
        self._setup_menu()

        # 通知 Web 端更新文本
        translations = json.dumps({
            "app_name": t("app_name"),
            "panel_image_list": t("panel_image_list"),
            "panel_watermark_style": t("panel_watermark_style"),
            "search_placeholder": t("search_placeholder"),
            "btn_add_images": t("btn_add_images"),
            "btn_select_all": t("btn_select_all"),
            "btn_clear_list": t("btn_clear_list"),
            "btn_process": t("btn_process"),
            "btn_cancel": t("btn_cancel"),
            "preview_original": t("preview_original"),
            "preview_result": t("preview_result"),
            "preview_no_image": t("preview_no_image"),
            "drop_hint": t("drop_hint"),
            "msg_ready": t("msg_ready"),
        }, ensure_ascii=False)
        self.bridge.uiTextsUpdated.emit(translations)

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
            existing_files = [f for f in files if Path(f).exists()]
            if existing_files:
                self._add_files(existing_files)

    def _save_session(self):
        """保存当前会话"""
        if self.config.get('general', {}).get('restore_last_session', False):
            files = self.bridge.get_all_files()
            self.config_manager.save_session_files(files)
        else:
            self.config_manager.clear_session_files()

    def closeEvent(self, event):
        """窗口关闭事件"""
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
"""
Photo-Timestamper PyQt6 User Interface
重写版本 - 修复选择逻辑、筛选器、快捷键等问题
"""
import sys
import os
import subprocess
import json
import base64
from pathlib import Path
from datetime import datetime
from io import BytesIO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog,
    QMessageBox, QDialog, QLabel, QPushButton, QComboBox, QGroupBox,
    QRadioButton, QButtonGroup, QCheckBox, QLineEdit, QSpinBox, QDateTimeEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QDateTime, pyqtSlot, QObject
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


# ==================== Processing Thread ====================
class ProcessingThread(QThread):
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
            logger.error(f"Processing thread exception: {e}")
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, filename: str):
        self.progress.emit(current, total, filename)

    def _on_preview(self, filepath: str, image: Image.Image):
        self.preview.emit(filepath, image)

    def cancel(self):
        self.processor.cancel()


# ==================== Web Bridge ====================
class WebBridge(QObject):
    filesUpdated = pyqtSignal(str)
    previewUpdated = pyqtSignal(str, str)
    progressUpdated = pyqtSignal(int, int, str)
    processingFinished = pyqtSignal(str)
    processingError = pyqtSignal(str)
    statusMessage = pyqtSignal(str)
    uiTextsUpdated = pyqtSignal(str)
    showProgressOverlay = pyqtSignal(bool)
    stylesUpdated = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._file_list: list[dict] = []

    # ---------- API to JS ----------
    @pyqtSlot(result=str)
    def getTranslations(self) -> str:
        t = {
            "app_name": L("Photo Timestamper&照片时间水印添加器"),
            "panel_image_list": L("Image List&图片列表"),
            "panel_watermark_style": L("Watermark Style&水印样式"),
            "search_placeholder": L("Search images...&搜索图片..."),
            "image_count": L("{count} images&共 {count} 张图片"),
            "selected_count": L("{selected}/{total} selected&已选择 {selected}/{total} 张"),
            "btn_add_images": L("Add Images&添加图片"),
            "btn_add_folder": L("Add Folder&添加文件夹"),
            "btn_clear_list": L("Clear&清空"),
            "btn_select_all": L("Select All&全选"),
            "btn_deselect_all": L("Deselect All&取消全选"),
            "btn_process": L("Start Processing&开始处理"),
            "btn_process_selected": L("Process Selected ({count})&处理选中 ({count})"),
            "btn_cancel": L("Cancel&取消"),
            "preview_original": L("Original&原图"),
            "preview_result": L("Preview&效果预览"),
            "preview_no_image": L("Select an image to preview&选择图片以预览"),
            "drop_hint": L("Drop images or folders here\\nor click button below to add&将图片或文件夹拖放到此处\\n或点击下方按钮添加"),
            "processing": L("Processing...&处理中..."),
            "exporting": L("Exporting {current}/{total}&导出第 {current}/{total} 张"),
            "msg_ready": L("Ready&就绪"),
            "msg_no_selection": L("Please select images to process&请选择要处理的图片"),
            "ctx_select_all": L("Select All&全选"),
            "ctx_deselect_all": L("Deselect All&取消全选"),
            "ctx_open_file": L("Open File&打开文件"),
            "ctx_open_folder": L("Open Containing Folder&打开所在文件夹"),
            "ctx_remove_selected": L("Remove Selected&移除选中项"),
            "ctx_clear_all": L("Clear All&清空所有"),
            "error_title": L("Error&错误"),
            "close": L("Close&关闭"),
        }
        return json.dumps(t, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getStyles(self) -> str:
        styles = self.main_window.style_manager.list_styles()
        last_style = self.main_window.config.get('ui', {}).get('last_style', 'CANON&佳能')
        style_data = [{"value": s, "display": L(s)} for s in styles]
        current = last_style if last_style in styles else (styles[0] if styles else "")
        return json.dumps({
            "styles": style_data,
            "current": current,
            "currentDisplay": L(current) if current else ""
        }, ensure_ascii=False)

    @pyqtSlot(result=str)
    def getFileList(self) -> str:
        return json.dumps(self._file_list, ensure_ascii=False)

    @pyqtSlot()
    def requestAddFiles(self):
        self.main_window._show_import_dialog()

    @pyqtSlot()
    def requestAddFolder(self):
        self.main_window._import_folder()

    @pyqtSlot()
    def requestClearFiles(self):
        self._file_list.clear()
        self.filesUpdated.emit(json.dumps(self._file_list))
        self.statusMessage.emit(L("Image list cleared&已清空图片列表"))

    @pyqtSlot(str)
    def setFileSelected(self, data: str):
        """设置单个文件的选中状态"""
        info = json.loads(data)
        path = info.get('path')
        selected = info.get('selected', False)
        for item in self._file_list:
            if item['path'] == path:
                item['selected'] = selected
                break

    @pyqtSlot(str)
    def setMultipleSelected(self, data: str):
        """批量设置选中状态"""
        info = json.loads(data)
        paths = set(info.get('paths', []))
        selected = info.get('selected', False)
        for item in self._file_list:
            if item['path'] in paths:
                item['selected'] = selected

    @pyqtSlot()
    def selectAll(self):
        for item in self._file_list:
            item['selected'] = True
        self.filesUpdated.emit(json.dumps(self._file_list))

    @pyqtSlot()
    def deselectAll(self):
        for item in self._file_list:
            item['selected'] = False
        self.filesUpdated.emit(json.dumps(self._file_list))

    @pyqtSlot(str)
    def removeSelected(self, selected_json: str):
        selected = set(json.loads(selected_json))
        before = len(self._file_list)
        self._file_list = [item for item in self._file_list if item['path'] not in selected]
        removed = before - len(self._file_list)
        self.filesUpdated.emit(json.dumps(self._file_list))
        self.statusMessage.emit(
            L("Removed {count} images&已移除 {count} 张图片").replace("{count}", str(removed))
        )

    @pyqtSlot(str)
    def requestPreview(self, filepath: str):
        """请求预览指定图片"""
        self.main_window._update_preview(filepath)

    @pyqtSlot(str)
    def setStyle(self, style_name: str):
        self.main_window.config['ui']['last_style'] = style_name
        self.main_window.config_manager.save(self.main_window.config)

    @pyqtSlot(str)
    def startProcessing(self, data: str):
        """开始处理，data 包含 style_name 和 selected_paths"""
        info = json.loads(data)
        style_name = info.get('style_name', '')
        selected_paths = info.get('selected_paths', [])
        
        if not selected_paths:
            QMessageBox.warning(
                self.main_window,
                L("Photo Timestamper&照片时间水印添加器"),
                L("Please select images to process&请选择要处理的图片")
            )
            return
        
        self.main_window._start_processing_with_files(selected_paths, style_name)

    @pyqtSlot()
    def cancelProcessing(self):
        self.main_window._cancel_processing()

    @pyqtSlot(str)
    def openFile(self, filepath: str):
        try:
            if sys.platform == 'win32':
                os.startfile(filepath)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filepath])
            else:
                subprocess.run(['xdg-open', filepath])
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    @pyqtSlot(str)
    def openFolder(self, filepath: str):
        try:
            folder = str(Path(filepath).parent)
            if sys.platform == 'win32':
                subprocess.run(['explorer', '/select,', filepath])
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', filepath])
            else:
                subprocess.run(['xdg-open', folder])
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    @pyqtSlot()
    def showSettings(self):
        self.main_window._show_settings()

    @pyqtSlot()
    def showAbout(self):
        self.main_window._show_about()

    # ---------- Helpers ----------
    def add_files(self, files: list[str]) -> tuple[int, int]:
        existing = {item['path'] for item in self._file_list}
        added = 0
        duplicates = 0
        for filepath in files:
            if filepath in existing:
                duplicates += 1
                continue
            filename = Path(filepath).name
            thumb = self._make_thumb(filepath, max_size=128, quality=65)
            self._file_list.append({
                'path': filepath,
                'name': filename,
                'selected': False,
                'thumbnail': thumb
            })
            existing.add(filepath)
            added += 1
        self.filesUpdated.emit(json.dumps(self._file_list))
        return added, duplicates

    def _make_thumb(self, path: str, max_size: int = 128, quality: int = 65) -> str:
        try:
            with Image.open(path) as im:
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGB")
                im.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                buf = BytesIO()
                im.save(buf, format="JPEG", quality=quality)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                return f"data:image/jpeg;base64,{b64}"
        except Exception as e:
            logger.debug(f"Thumbnail failed [{path}]: {e}")
            return ""

    def get_all_files(self) -> list[str]:
        return [item['path'] for item in self._file_list]

    def get_selected_files(self) -> list[str]:
        return [item['path'] for item in self._file_list if item.get('selected')]


# ==================== HTML ====================
def get_html_content() -> str:
    return r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Photo Timestamper</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
    --bg-primary: #1e1e1e;
    --bg-secondary: #252525;
    --bg-tertiary: #2d2d2d;
    --bg-hover: #353535;
    --bg-active: #404040;
    --border-color: #3d3d3d;
    --text-primary: #e0e0e0;
    --text-secondary: #a0a0a0;
    --text-muted: #707070;
    --accent-blue: #0a84ff;
    --accent-blue-light: #409cff;
    --accent-green: #34c759;
    --accent-orange: #ff9500;
    --accent-red: #ff3b30;
    --status-height: 22px;
    --selection-bg: rgba(10, 132, 255, 0.25);
    --selection-border: rgba(10, 132, 255, 0.6);
}

body {
    font-family: "Microsoft YaHei", "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 12px;
    background: var(--bg-primary);
    color: var(--text-primary);
    overflow: hidden;
    height: 100vh;
    user-select: none;
}

.main-container {
    display: flex;
    height: calc(100vh - var(--status-height));
}

/* 左侧面板 */
.left-panel {
    width: 300px;
    min-width: 300px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    padding: 12px;
}

.panel-title {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
    padding: 8px 0 6px 0;
    text-transform: uppercase;
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
    background: var(--bg-tertiary);
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
    background: #2a2a2a;
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

.file-list::-webkit-scrollbar-thumb {
    background: #4d4d4d;
    border-radius: 4px;
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

/* 文件项 */
.file-item {
    display: flex;
    align-items: center;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    margin-bottom: 2px;
    gap: 10px;
    border: 2px solid transparent;
    transition: all 0.15s ease;
}

.file-item:hover {
    background: var(--bg-hover);
}

.file-item.selected {
    background: var(--selection-bg);
    border-color: var(--selection-border);
}

.file-item.selected .file-name {
    color: #fff;
    font-weight: 500;
}

.file-item.selected .thumbnail {
    border-color: var(--accent-blue);
    box-shadow: 0 0 0 2px rgba(10, 132, 255, 0.3);
}

.thumbnail {
    width: 72px;
    height: 54px;
    background: #111;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    overflow: hidden;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
}

.thumbnail img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    display: block;
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

/* 按钮 */
.button-group {
    display: flex;
    gap: 6px;
    margin-top: 8px;
}

.btn {
    background: var(--bg-tertiary);
    border: 1px solid #4d4d4d;
    border-radius: 4px;
    padding: 6px 12px;
    color: var(--text-primary);
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s ease;
    flex: 1;
}

.btn:hover {
    background: #4d4d4d;
    border-color: #5d5d5d;
}

.btn:disabled {
    background: var(--bg-tertiary);
    color: var(--text-muted);
    cursor: not-allowed;
}

.btn-primary {
    background: var(--accent-blue);
    border: none;
    color: white;
    font-weight: 600;
}

.btn-primary:hover {
    background: var(--accent-blue-light);
}

.btn-primary:disabled {
    background: #555;
    color: #888;
}

.btn-danger {
    background: var(--accent-red);
    border: none;
    color: white;
}

.btn-danger:hover {
    background: #ff5a52;
}

.btn-large {
    padding: 10px 16px;
    font-size: 13px;
    min-height: 40px;
}

/* 样式选择 */
.style-section {
    margin-top: 12px;
}

.style-select {
    width: 100%;
    background: var(--bg-tertiary);
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
    background: #1a1a1a;
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
    display: block;
}

.preview-placeholder {
    color: var(--text-muted);
    font-size: 12px;
}

/* 右键菜单 */
.context-menu {
    position: fixed;
    background: var(--bg-tertiary);
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
    background: var(--accent-blue);
}

.context-menu-separator {
    height: 1px;
    background: var(--border-color);
    margin: 6px 8px;
}

/* 拖放提示 */
.drop-overlay {
    position: fixed;
    inset: 0;
    background: rgba(10, 132, 255, 0.1);
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
    background: var(--bg-tertiary);
    padding: 20px 40px;
    border-radius: 8px;
    font-size: 16px;
    color: var(--accent-blue);
}

/* 进度对话框 */
.progress-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 2000;
}

.progress-overlay.visible {
    display: flex;
}

.progress-dialog {
    background: var(--bg-secondary);
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
    background: var(--bg-tertiary);
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
    transition: width 0.25s ease;
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
    background: rgba(255, 59, 48, 0.1);
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

/* 状态栏 */
.status-bar {
    height: var(--status-height);
    background: var(--bg-secondary);
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
            <button class="btn" id="btnAdd">添加图片</button>
            <button class="btn" id="btnSelectAll">全选</button>
            <button class="btn" id="btnClear">清空</button>
        </div>

        <div class="style-section">
            <span class="panel-title" id="styleTitle">水印样式</span>
            <select class="style-select" id="styleSelect"></select>
        </div>

        <div class="process-section">
            <button class="btn btn-primary btn-large" id="btnProcess" disabled>开始处理</button>
        </div>
    </div>

    <div class="preview-container">
        <div class="preview-panel">
            <span class="panel-title" id="originalTitle">原图</span>
            <div class="preview-area" id="originalPreview">
                <span class="preview-placeholder" id="originalPlaceholder">选择图片以预览</span>
                <img id="originalImage" style="display:none;">
            </div>
        </div>
        <div class="preview-panel">
            <span class="panel-title" id="resultTitle">效果预览</span>
            <div class="preview-area" id="resultPreview">
                <span class="preview-placeholder" id="resultPlaceholder">选择图片以预览</span>
                <img id="resultImage" style="display:none;">
            </div>
        </div>
    </div>
</div>

<div class="context-menu" id="contextMenu">
    <div class="context-menu-item" id="menuSelectAll">全选</div>
    <div class="context-menu-item" id="menuDeselectAll">取消全选</div>
    <div class="context-menu-separator"></div>
    <div class="context-menu-item" id="menuOpenFile">打开文件</div>
    <div class="context-menu-item" id="menuOpenFolder">打开所在文件夹</div>
    <div class="context-menu-separator"></div>
    <div class="context-menu-item" id="menuRemoveSelected">移除选中项</div>
    <div class="context-menu-item" id="menuClearAll">清空所有</div>
</div>

<div class="drop-overlay" id="dropOverlay">
    <div class="drop-overlay-text">释放以添加图片</div>
</div>

<div class="progress-overlay" id="progressOverlay">
    <div class="progress-dialog">
        <div class="progress-title" id="progressTitle">导出中...</div>
        <div class="progress-bar-container">
            <div class="progress-bar-fill" id="progressFill" style="width: 0%;"></div>
        </div>
        <div class="progress-text" id="progressText">准备中...</div>
        <div class="progress-error" id="progressError"></div>
        <div class="progress-buttons">
            <button class="btn btn-danger" id="btnCancelProgress">取消</button>
        </div>
    </div>
</div>

<div class="status-bar" id="statusBar">就绪</div>

<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
(function() {
    'use strict';

    // 全局状态
    let bridge = null;
    let fileList = [];           // 完整文件列表
    let filteredList = [];       // 筛选后的文件列表
    let selectedPaths = new Set(); // 选中的文件路径
    let lastClickedPath = null;  // 最后点击的路径（用于Shift多选）
    let currentStyleValue = '';
    let isProcessing = false;
    let translations = {};

    // DOM 元素缓存
    const $ = id => document.getElementById(id);
    const elements = {};

    // 初始化
    document.addEventListener('DOMContentLoaded', () => {
        cacheElements();
        
        new QWebChannel(qt.webChannelTransport, function(channel) {
            bridge = channel.objects.bridge;
            bindBridgeEvents();
            bindUIEvents();
            initializeUI();
        });
    });

    function cacheElements() {
        const ids = [
            'panelTitle', 'listInfo', 'searchBox', 'fileList', 'emptyHint',
            'btnAdd', 'btnSelectAll', 'btnClear', 'styleTitle', 'styleSelect',
            'btnProcess', 'originalTitle', 'originalPlaceholder', 'originalImage',
            'resultTitle', 'resultPlaceholder', 'resultImage', 'contextMenu',
            'menuSelectAll', 'menuDeselectAll', 'menuOpenFile', 'menuOpenFolder',
            'menuRemoveSelected', 'menuClearAll', 'dropOverlay', 'progressOverlay',
            'progressTitle', 'progressFill', 'progressText', 'progressError',
            'btnCancelProgress', 'statusBar'
        ];
        ids.forEach(id => elements[id] = $(id));
    }

    function bindBridgeEvents() {
        bridge.filesUpdated.connect(onFilesUpdated);
        bridge.previewUpdated.connect(onPreviewUpdated);
        bridge.progressUpdated.connect(onProgressUpdated);
        bridge.processingFinished.connect(onProcessingFinished);
        bridge.processingError.connect(onProcessingError);
        bridge.statusMessage.connect(onStatusMessage);
        bridge.uiTextsUpdated.connect(onUITextsUpdated);
        bridge.stylesUpdated.connect(onStylesUpdated);
        bridge.showProgressOverlay.connect(onShowProgressOverlay);
    }

    function bindUIEvents() {
        // 按钮事件
        elements.btnAdd.addEventListener('click', () => bridge.requestAddFiles());
        elements.btnSelectAll.addEventListener('click', toggleSelectAll);
        elements.btnClear.addEventListener('click', () => bridge.requestClearFiles());
        elements.btnProcess.addEventListener('click', startProcessing);
        elements.btnCancelProgress.addEventListener('click', () => bridge.cancelProcessing());

        // 样式选择
        elements.styleSelect.addEventListener('change', onStyleChange);

        // 搜索框
        elements.searchBox.addEventListener('input', onSearchInput);

        // 右键菜单
        elements.menuSelectAll.addEventListener('click', () => { selectAll(); hideContextMenu(); });
        elements.menuDeselectAll.addEventListener('click', () => { deselectAll(); hideContextMenu(); });
        elements.menuOpenFile.addEventListener('click', openCurrentFile);
        elements.menuOpenFolder.addEventListener('click', openCurrentFolder);
        elements.menuRemoveSelected.addEventListener('click', removeSelected);
        elements.menuClearAll.addEventListener('click', () => { bridge.requestClearFiles(); hideContextMenu(); });

        // 全局点击隐藏右键菜单
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.context-menu')) {
                hideContextMenu();
            }
        });

        // 键盘快捷键
        document.addEventListener('keydown', onKeyDown);

        // 拖放
        document.addEventListener('dragenter', onDragEnter);
        document.addEventListener('dragleave', onDragLeave);
        document.addEventListener('dragover', (e) => e.preventDefault());
        document.addEventListener('drop', onDrop);
    }

    async function initializeUI() {
        // 加载翻译
        const textsJson = await bridge.getTranslations();
        translations = JSON.parse(textsJson);
        applyTranslations();

        // 加载样式
        const stylesJson = await bridge.getStyles();
        const stylesData = JSON.parse(stylesJson);
        rebuildStyleSelect(stylesData);

        // 加载文件列表
        const fileListJson = await bridge.getFileList();
        fileList = JSON.parse(fileListJson);
        applyFilter();
        renderFileList();
    }

    // ==================== 文件列表相关 ====================

    function onFilesUpdated(jsonData) {
        fileList = JSON.parse(jsonData);
        
        // 清理已不存在的选中项
        const pathSet = new Set(fileList.map(f => f.path));
        selectedPaths = new Set([...selectedPaths].filter(p => pathSet.has(p)));
        
        applyFilter();
        renderFileList();
        updateProcessButton();
    }

    function applyFilter() {
        const searchText = elements.searchBox.value.toLowerCase().trim();
        if (!searchText) {
            filteredList = [...fileList];
        } else {
            filteredList = fileList.filter(f => 
                f.name.toLowerCase().includes(searchText)
            );
        }
    }

    function onSearchInput() {
        applyFilter();
        renderFileList();
    }

    function renderFileList() {
        const container = elements.fileList;
        const emptyHint = elements.emptyHint;

        // 清空容器
        container.innerHTML = '';

        if (filteredList.length === 0) {
            container.appendChild(emptyHint);
            emptyHint.style.display = 'flex';
            updateListInfo();
            return;
        }

        emptyHint.style.display = 'none';

        // 创建文件项
        filteredList.forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-item';
            if (selectedPaths.has(file.path)) {
                item.classList.add('selected');
            }
            item.dataset.path = file.path;

            const thumbHtml = file.thumbnail
                ? `<img src="${file.thumbnail}" alt="">`
                : '<span class="thumbnail-placeholder">...</span>';

            item.innerHTML = `
                <div class="thumbnail">${thumbHtml}</div>
                <span class="file-name" title="${escapeHtml(file.path)}">${escapeHtml(file.name)}</span>
            `;

            item.addEventListener('click', (e) => onFileItemClick(e, file.path));
            item.addEventListener('contextmenu', (e) => onFileItemContextMenu(e, file.path));

            container.appendChild(item);
        });

        updateListInfo();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function onFileItemClick(event, path) {
        event.stopPropagation();

        if (event.ctrlKey || event.metaKey) {
            // Ctrl+点击：切换选中状态
            if (selectedPaths.has(path)) {
                selectedPaths.delete(path);
            } else {
                selectedPaths.add(path);
            }
            lastClickedPath = path;
        } else if (event.shiftKey && lastClickedPath) {
            // Shift+点击：范围选择
            const paths = filteredList.map(f => f.path);
            const startIdx = paths.indexOf(lastClickedPath);
            const endIdx = paths.indexOf(path);

            if (startIdx !== -1 && endIdx !== -1) {
                const minIdx = Math.min(startIdx, endIdx);
                const maxIdx = Math.max(startIdx, endIdx);
                for (let i = minIdx; i <= maxIdx; i++) {
                    selectedPaths.add(paths[i]);
                }
            }
        } else {
            // 普通点击：单选
            selectedPaths.clear();
            selectedPaths.add(path);
            lastClickedPath = path;
        }

        renderFileList();
        updateProcessButton();

        // 请求预览最后点击的图片
        if (selectedPaths.size > 0) {
            bridge.requestPreview(path);
        }
    }

    function onFileItemContextMenu(event, path) {
        event.preventDefault();
        event.stopPropagation();

        // 如果右键点击的项未被选中，则选中它
        if (!selectedPaths.has(path)) {
            selectedPaths.clear();
            selectedPaths.add(path);
            lastClickedPath = path;
            renderFileList();
            updateProcessButton();
        }

        showContextMenu(event.clientX, event.clientY);
    }

    function updateListInfo() {
        const total = fileList.length;
        const selected = selectedPaths.size;

        if (selected > 0) {
            elements.listInfo.textContent = translations.selected_count
                ? translations.selected_count.replace('{selected}', selected).replace('{total}', total)
                : `已选择 ${selected}/${total} 张`;
        } else {
            elements.listInfo.textContent = translations.image_count
                ? translations.image_count.replace('{count}', total)
                : `共 ${total} 张图片`;
        }
    }

    // ==================== 选择操作 ====================

    function selectAll() {
        filteredList.forEach(f => selectedPaths.add(f.path));
        renderFileList();
        updateProcessButton();
    }

    function deselectAll() {
        selectedPaths.clear();
        lastClickedPath = null;
        renderFileList();
        updateProcessButton();
    }

    function toggleSelectAll() {
        if (selectedPaths.size === filteredList.length && filteredList.length > 0) {
            deselectAll();
        } else {
            selectAll();
        }
    }

    function removeSelected() {
        if (selectedPaths.size > 0) {
            bridge.removeSelected(JSON.stringify([...selectedPaths]));
        }
        hideContextMenu();
    }

    // ==================== 右键菜单 ====================

    let currentContextPath = null;

    function showContextMenu(x, y) {
        currentContextPath = selectedPaths.size === 1 ? [...selectedPaths][0] : null;
        
        const menu = elements.contextMenu;
        menu.style.left = x + 'px';
        menu.style.top = y + 'px';
        menu.classList.add('visible');
    }

    function hideContextMenu() {
        elements.contextMenu.classList.remove('visible');
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

    // ==================== 样式相关 ====================

    function rebuildStyleSelect(stylesData) {
        const select = elements.styleSelect;
        select.innerHTML = '';

        stylesData.styles.forEach(style => {
            const opt = document.createElement('option');
            opt.value = style.value;
            opt.textContent = style.display;
            if (style.value === stylesData.current) {
                opt.selected = true;
                currentStyleValue = style.value;
            }
            select.appendChild(opt);
        });
    }

    function onStyleChange() {
        currentStyleValue = elements.styleSelect.value;
        bridge.setStyle(currentStyleValue);

        // 如果有选中的图片，刷新预览
        if (selectedPaths.size > 0) {
            const lastSelected = [...selectedPaths].pop();
            bridge.requestPreview(lastSelected);
        }
    }

    function onStylesUpdated(jsonStr) {
        const data = JSON.parse(jsonStr);
        rebuildStyleSelect(data);
    }

    // ==================== 处理相关 ====================

    function updateProcessButton() {
        const btn = elements.btnProcess;
        const count = selectedPaths.size;

        if (count > 0) {
            btn.disabled = false;
            btn.textContent = translations.btn_process_selected
                ? translations.btn_process_selected.replace('{count}', count)
                : `处理选中 (${count})`;
        } else {
            btn.disabled = true;
            btn.textContent = translations.btn_process || '开始处理';
        }
    }

    function startProcessing() {
        if (selectedPaths.size === 0) {
            return;
        }

        const data = {
            style_name: currentStyleValue,
            selected_paths: [...selectedPaths]
        };
        bridge.startProcessing(JSON.stringify(data));
    }

    function onProgressUpdated(current, total, filename) {
        const percent = (current / total) * 100;
        elements.progressFill.style.width = percent + '%';
        elements.progressText.textContent = filename;
        elements.progressTitle.textContent = translations.exporting
            ? translations.exporting.replace('{current}', current).replace('{total}', total)
            : `导出第 ${current}/${total} 张`;
    }

    function onProcessingFinished(resultJson) {
        isProcessing = false;
        elements.progressOverlay.classList.remove('visible');
    }

    function onProcessingError(errorMsg) {
        elements.progressError.textContent = errorMsg;
        elements.progressError.classList.add('visible');

        const btn = elements.btnCancelProgress;
        btn.textContent = translations.close || '关闭';
        btn.onclick = function() {
            elements.progressOverlay.classList.remove('visible');
            elements.progressError.classList.remove('visible');
            btn.textContent = translations.btn_cancel || '取消';
            btn.onclick = () => bridge.cancelProcessing();
        };
    }

    function onShowProgressOverlay(show) {
        if (show) {
            elements.progressOverlay.classList.add('visible');
            elements.progressError.classList.remove('visible');
            isProcessing = true;
        } else {
            elements.progressOverlay.classList.remove('visible');
            isProcessing = false;
        }
    }

    // ==================== 预览相关 ====================

    function onPreviewUpdated(originalBase64, resultBase64) {
        if (originalBase64) {
            elements.originalImage.src = originalBase64;
            elements.originalImage.style.display = 'block';
            elements.originalPlaceholder.style.display = 'none';
        } else {
            elements.originalImage.style.display = 'none';
            elements.originalPlaceholder.style.display = 'block';
        }

        if (resultBase64) {
            elements.resultImage.src = resultBase64;
            elements.resultImage.style.display = 'block';
            elements.resultPlaceholder.style.display = 'none';
        } else {
            elements.resultImage.style.display = 'none';
            elements.resultPlaceholder.style.display = 'block';
        }
    }

    // ==================== 键盘快捷键 ====================

    function onKeyDown(e) {
        if (isProcessing) return;

        // Ctrl+A / Cmd+A：全选
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
            e.preventDefault();
            if (e.shiftKey) {
                // Ctrl+Shift+A：取消全选
                deselectAll();
            } else {
                // Ctrl+A：全选
                selectAll();
            }
            return;
        }

        // Delete：删除选中
        if (e.key === 'Delete' && selectedPaths.size > 0) {
            e.preventDefault();
            removeSelected();
            return;
        }

        // Escape：取消选择
        if (e.key === 'Escape') {
            e.preventDefault();
            deselectAll();
            hideContextMenu();
            return;
        }
    }

    // ==================== 拖放 ====================

    function onDragEnter(e) {
        e.preventDefault();
        if (!isProcessing) {
            elements.dropOverlay.classList.add('visible');
        }
    }

    function onDragLeave(e) {
        if (e.target === elements.dropOverlay) {
            elements.dropOverlay.classList.remove('visible');
        }
    }

    function onDrop(e) {
        e.preventDefault();
        elements.dropOverlay.classList.remove('visible');
        // 实际的文件处理由 Qt 端完成
    }

    // ==================== 状态和翻译 ====================

    function onStatusMessage(message) {
        elements.statusBar.textContent = message;
    }

    function onUITextsUpdated(textsJson) {
        translations = JSON.parse(textsJson);
        applyTranslations();
    }

    function applyTranslations() {
        elements.panelTitle.textContent = translations.panel_image_list || '图片列表';
        elements.searchBox.placeholder = translations.search_placeholder || '搜索图片...';
        elements.btnAdd.textContent = translations.btn_add_images || '添加图片';
        elements.btnSelectAll.textContent = translations.btn_select_all || '全选';
        elements.btnClear.textContent = translations.btn_clear_list || '清空';
        elements.styleTitle.textContent = translations.panel_watermark_style || '水印样式';
        elements.originalTitle.textContent = translations.preview_original || '原图';
        elements.resultTitle.textContent = translations.preview_result || '效果预览';
        elements.originalPlaceholder.textContent = translations.preview_no_image || '选择图片以预览';
        elements.resultPlaceholder.textContent = translations.preview_no_image || '选择图片以预览';
        elements.statusBar.textContent = translations.msg_ready || '就绪';
        elements.btnCancelProgress.textContent = translations.btn_cancel || '取消';

        elements.menuSelectAll.textContent = translations.ctx_select_all || '全选';
        elements.menuDeselectAll.textContent = translations.ctx_deselect_all || '取消全选';
        elements.menuOpenFile.textContent = translations.ctx_open_file || '打开文件';
        elements.menuOpenFolder.textContent = translations.ctx_open_folder || '打开所在文件夹';
        elements.menuRemoveSelected.textContent = translations.ctx_remove_selected || '移除选中项';
        elements.menuClearAll.textContent = translations.ctx_clear_all || '清空所有';

        if (elements.emptyHint) {
            elements.emptyHint.innerHTML = (translations.drop_hint || '将图片或文件夹拖放到此处<br>或点击下方按钮添加').replace(/\\n/g, '<br>');
        }

        updateListInfo();
        updateProcessButton();
    }

})();
</script>
</body>
</html>'''


# ==================== Settings Dialog ====================
class SettingsDialog(QDialog):
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config = config_manager.load()

        self.setWindowTitle(L("Settings&设置"))
        self.setMinimumSize(500, 560)
        self.setModal(True)

        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Language
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

        # Session
        self.restore_session_check = QCheckBox(L("Restore images from last session on startup&启动时恢复上次打开的图片"))
        self.restore_session_check.setChecked(self.config.get('general', {}).get('restore_last_session', True))
        layout.addWidget(self.restore_session_check)

        # Output
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

        # filename pattern
        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel(L("Filename pattern&文件名格式:")))
        self.filename_pattern_edit = QLineEdit()
        self.filename_pattern_edit.setText(output_config.get('filename_pattern', '{original}_stamped'))
        self.filename_pattern_edit.setToolTip(L("Variables: {original}=original name, {date}=date, {time}=time, {index}=index&可用变量：{original}=原文件名, {date}=日期, {time}=时间, {index}=序号"))
        pattern_layout.addWidget(self.filename_pattern_edit)
        output_layout.addLayout(pattern_layout)

        # quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel(L("JPEG Quality&JPEG质量:")))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(output_config.get('jpeg_quality', 97))
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

        # Time Source
        time_group = QGroupBox(L("Time Source&时间源"))
        time_layout = QVBoxLayout(time_group)
        time_layout.addWidget(QLabel(L("Primary source&主时间源:")))
        self.time_exif_radio = QRadioButton(L("EXIF Date Taken (Recommended)&EXIF拍摄时间（推荐）"))
        self.time_modified_radio = QRadioButton(L("File Modified Time&文件修改时间"))
        self.time_created_radio = QRadioButton(L("File Created Time&文件创建时间"))
        self.time_custom_radio = QRadioButton(L("Custom Time&自定义时间"))
        btn_group = QButtonGroup(self)
        for b in (self.time_exif_radio, self.time_modified_radio, self.time_created_radio, self.time_custom_radio):
            btn_group.addButton(b)
            time_layout.addWidget(b)
        custom_time_layout = QHBoxLayout()
        custom_time_layout.addWidget(self.time_custom_radio)
        self.custom_time_edit = QDateTimeEdit()
        self.custom_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.custom_time_edit.setDateTime(QDateTime.currentDateTime())
        self.custom_time_edit.setEnabled(False)
        custom_time_layout.addWidget(self.custom_time_edit)
        time_layout.addLayout(custom_time_layout)
        self.time_custom_radio.toggled.connect(lambda checked: self.custom_time_edit.setEnabled(checked))

        time_config = self.config.get('time_source', {})
        primary = time_config.get('primary', 'exif')
        if primary == 'exif':
            self.time_exif_radio.setChecked(True)
        elif primary == 'file_modified':
            self.time_modified_radio.setChecked(True)
        elif primary == 'file_created':
            self.time_created_radio.setChecked(True)
        else:
            self.time_custom_radio.setChecked(True)
            self.custom_time_edit.setEnabled(True)
            custom_time_str = time_config.get('custom_time', '')
            if custom_time_str:
                try:
                    dt = datetime.strptime(custom_time_str, "%Y-%m-%d %H:%M:%S")
                    self.custom_time_edit.setDateTime(QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second))
                except:
                    pass

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

        # buttons
        btn_layout = QHBoxLayout()
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
        self.language_combo.setCurrentIndex(1)  # zh
        self.restore_session_check.setChecked(True)
        self.same_dir_radio.setChecked(True)
        self.filename_pattern_edit.setText("{original}_stamped")
        self.quality_spin.setValue(97)
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


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(L("Keyboard Shortcuts&快捷键"))
        self.setFixedSize(420, 380)

        from PyQt6.QtWidgets import QVBoxLayout, QGridLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(L("Keyboard Shortcuts&快捷键"))
        title.setStyleSheet("font-size:16px; font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(8)

        # 快捷键列表
        shortcuts = [
            ("Ctrl+O", L("Import Images&导入图片")),
            ("Ctrl+Shift+O", L("Import Folder&导入文件夹")),
            ("Ctrl+A", L("Select All&全选")),
            ("Ctrl+Shift+A", L("Deselect All&取消全选")),
            ("Delete", L("Remove Selected&移除选中项")),
            ("Escape", L("Cancel Selection&取消选择")),
            ("Ctrl+,", L("Settings&设置")),
            ("Ctrl+Q", L("Exit&退出")),
        ]

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnMinimumWidth(0, 120)

        for row, (key, desc) in enumerate(shortcuts):
            key_label = QLabel(key)
            key_label.setStyleSheet("""
                background: #3d3d3d;
                padding: 4px 10px;
                border-radius: 4px;
                font-family: monospace;
                font-weight: bold;
            """)
            desc_label = QLabel(desc)
            grid.addWidget(key_label, row, 0)
            grid.addWidget(desc_label, row, 1)

        layout.addLayout(grid)
        layout.addStretch()

        close_btn = QPushButton(L("Close&关闭"))
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

# ==================== About Dialog ====================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(L("About Photo Timestamper&关于照片时间水印添加器"))
        self.setFixedSize(420, 480)

        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QSize
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedHeight(100)
        logo_path = get_base_path() / "assets" / "logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled = pixmap.scaled(QSize(80, 80), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled)
        else:
            logo_label.setText("📷")
            logo_label.setStyleSheet("font-size:48px;")
        layout.addWidget(logo_label)

        layout.addSpacing(16)

        name_label = QLabel("Photo Timestamper")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size:18px; font-weight:bold;")
        layout.addWidget(name_label)

        layout.addSpacing(4)

        version_label = QLabel(L("Version {version}&版本 {version}").replace("{version}", __version__))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(12)

        desc_label = QLabel(L("A tool for adding camera-style timestamp watermarks to photos&为照片添加仿相机原厂风格的时间戳水印工具"))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addSpacing(20)

        author_title = QLabel(L("Author&作者"))
        author_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_title.setStyleSheet("color:#888;")
        layout.addWidget(author_title)

        author_name = QLabel(__author__)
        author_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_name)

        layout.addSpacing(12)

        collab_title = QLabel(L("Collaborators&协作"))
        collab_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collab_title.setStyleSheet("color:#888;")
        layout.addWidget(collab_title)

        collab_names = QLabel(" · ".join(__collaborators__))
        collab_names.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(collab_names)

        layout.addStretch()

        license_label = QLabel("GPL-3.0")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setStyleSheet("color:#888;")
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


# ==================== Import Dialog ====================
class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(L("Import Images&导入图片"))
        self.setFixedSize(380, 220)
        self.selected_files: list[str] = []
        self.recursive = True

        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
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


# ==================== Language Selection Dialog ====================
class LanguageSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Language / 选择语言")
        self.setFixedSize(380, 240)
        self.selected_language = "zh"

        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Select Language / 选择语言")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:16px; font-weight:bold;")
        layout.addWidget(title)

        desc = QLabel("Please select your preferred language:\n请选择您偏好的语言：")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(8)

        self.language_combo = QComboBox()
        self.language_combo.setMinimumHeight(38)
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("简体中文", "zh")
        self.language_combo.setCurrentIndex(1)
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


# ==================== Main Window ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.style_manager = StyleManager()

        saved_lang = self.config.get('general', {}).get('language', 'zh')
        LocalizationManager.set_language(saved_lang)

        self.processing_thread: ProcessingThread | None = None

        self._init_ui()
        self._setup_menu()
        self._load_ui_state()

        if self.config_manager.is_first_run():
            QTimer.singleShot(100, self._show_language_selection)
        else:
            if self.config.get('general', {}).get('restore_last_session', True):
                QTimer.singleShot(500, self._restore_last_session)

    def _init_ui(self):
        self.setWindowTitle(L("Photo Timestamper&照片时间水印添加器"))
        self.setMinimumSize(1200, 700)

        icon_path = get_base_path() / "assets" / "logo.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            alt = get_base_path() / "assets" / "logo.png"
            if alt.exists():
                self.setWindowIcon(QIcon(str(alt)))

        self.web_view = QWebEngineView()
        self.bridge = WebBridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.web_view.setHtml(get_html_content(), QUrl("qrc:///"))
        self.setCentralWidget(self.web_view)
        self.statusBar().showMessage(L("Ready&就绪"))

    def _setup_menu(self):
        from PyQt6.QtGui import QAction
        menubar = self.menuBar()
        menubar.clear()

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

        software_menu = menubar.addMenu(L("Software&软件"))

        settings_action = QAction(L("Settings...&设置..."), self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        software_menu.addAction(settings_action)

        shortcuts_action = QAction(L("Keyboard Shortcuts&快捷键"), self)
        shortcuts_action.setShortcut("Ctrl+/")
        shortcuts_action.triggered.connect(self._show_shortcuts)
        software_menu.addAction(shortcuts_action)

        software_menu.addSeparator()

        about_action = QAction(L("About&关于"), self)
        about_action.triggered.connect(self._show_about)
        software_menu.addAction(about_action)

    def _show_language_selection(self):
        dialog = LanguageSelectDialog(self)
        if dialog.exec():
            selected_lang = dialog.get_selected_language()
            LocalizationManager.set_language(selected_lang)
            self.config['general']['language'] = selected_lang
            self.config_manager.save(self.config)
            self.config_manager.set_first_run_complete()
            self._update_ui_texts()

    def _show_import_dialog(self):
        dialog = ImportDialog(self)
        if dialog.exec():
            files = dialog.get_files()
            if files:
                self._add_files(files)

    def _import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, L("Select Folder&选择文件夹"))
        if folder:
            files = scan_images(folder, recursive=True)
            if files:
                self._add_files(files)

    def _add_files(self, files: list[str]):
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
        self.bridge.requestClearFiles()

    def _show_settings(self):
        dialog = SettingsDialog(self.config_manager, self)
        if dialog.exec():
            self.config = self.config_manager.load()
            self._update_ui_texts()
            self.statusBar().showMessage(L("Settings saved&设置已保存"))

    def _show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()
        
    def _show_shortcuts(self):
        dialog = ShortcutsDialog(self)
        dialog.exec()

    # ---------- Preview ----------
    def _make_preview_b64(self, image: Image.Image, max_long: int = 960, quality: int = 80) -> str:
        im = image.copy()
        im.thumbnail((max_long, max_long), Image.Resampling.LANCZOS)
        if im.mode != 'RGB':
            im = im.convert('RGB')
        buf = BytesIO()
        im.save(buf, format='JPEG', quality=quality)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

    def _update_preview(self, filepath: str):
        try:
            with Image.open(filepath) as image:
                if image.mode not in ('RGB', 'RGBA'):
                    image = image.convert('RGB')

                original_b64 = self._make_preview_b64(image, max_long=960, quality=80)

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

                preview_base = image.copy()
                preview_base.thumbnail((960, 960), Image.Resampling.LANCZOS)
                result_img = renderer.render(preview_base, timestamp)
                result_b64 = self._make_preview_b64(result_img, max_long=960, quality=80)

                self.bridge.previewUpdated.emit(original_b64, result_b64)
        except Exception as e:
            logger.error(f"Failed to generate preview: {e}")
            self.bridge.previewUpdated.emit('', '')

    # ---------- Processing ----------
    def _start_processing_with_files(self, files: list[str], style_name: str):
        processor = BatchProcessor(self.config, self.style_manager)
        self.processing_thread = ProcessingThread(processor, files, style_name)
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.preview.connect(self._on_processing_preview)
        self.processing_thread.finished.connect(self._on_finished)
        self.processing_thread.error.connect(self._on_error)
        self.bridge.showProgressOverlay.emit(True)
        self.processing_thread.start()

    def _cancel_processing(self):
        if self.processing_thread:
            self.processing_thread.cancel()
            self.statusBar().showMessage(L("Cancelling...&正在取消..."))

    def _on_progress(self, current: int, total: int, filename: str):
        self.bridge.progressUpdated.emit(current, total, filename)
        self.statusBar().showMessage(
            L("Exporting {current}/{total}&导出第 {current}/{total} 张").replace("{current}", str(current)).replace("{total}", str(total))
            + f": {filename}"
        )

    def _on_processing_preview(self, filepath: str, image: Image.Image):
        try:
            img = image.copy()
            img.thumbnail((960, 960), Image.Resampling.LANCZOS)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=78)
            result_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
            self.bridge.previewUpdated.emit('', result_b64)
        except Exception as e:
            logger.debug(f"Preview update failed: {e}")

    def _on_finished(self, results: dict):
        self.bridge.showProgressOverlay.emit(False)
        success = results.get('success', 0)
        failed = results.get('failed', 0)
        self.statusBar().showMessage(
            L("Complete: {success} succeeded, {failed} failed&处理完成：成功 {success} 张，失败 {failed} 张")
            .replace("{success}", str(success)).replace("{failed}", str(failed))
        )
        if failed == 0:
            QMessageBox.information(
                self,
                L("Photo Timestamper&照片时间水印添加器"),
                L("Successfully processed {count} images&成功处理 {count} 张图片").replace("{count}", str(success))
            )

    def _on_error(self, error: str):
        self.bridge.processingError.emit(L(error))
        self.statusBar().showMessage(L("Processing error&处理出错"))

    # ---------- UI text reload ----------
    def _update_ui_texts(self):
        self.setWindowTitle(L("Photo Timestamper&照片时间水印添加器"))
        self._setup_menu()
        translations = json.dumps({
            "app_name": L("Photo Timestamper&照片时间水印添加器"),
            "panel_image_list": L("Image List&图片列表"),
            "panel_watermark_style": L("Watermark Style&水印样式"),
            "search_placeholder": L("Search images...&搜索图片..."),
            "image_count": L("{count} images&共 {count} 张图片"),
            "selected_count": L("{selected}/{total} selected&已选择 {selected}/{total} 张"),
            "btn_add_images": L("Add Images&添加图片"),
            "btn_select_all": L("Select All&全选"),
            "btn_deselect_all": L("Deselect All&取消全选"),
            "btn_clear_list": L("Clear&清空"),
            "btn_process": L("Start Processing&开始处理"),
            "btn_process_selected": L("Process Selected ({count})&处理选中 ({count})"),
            "btn_cancel": L("Cancel&取消"),
            "preview_original": L("Original&原图"),
            "preview_result": L("Preview&效果预览"),
            "preview_no_image": L("Select an image to preview&选择图片以预览"),
            "drop_hint": L("Drop images or folders here\\nor click button below to add&将图片或文件夹拖放到此处\\n或点击下方按钮添加"),
            "msg_ready": L("Ready&就绪"),
            "msg_no_selection": L("Please select images to process&请选择要处理的图片"),
            "ctx_select_all": L("Select All&全选"),
            "ctx_deselect_all": L("Deselect All&取消全选"),
            "ctx_open_file": L("Open File&打开文件"),
            "ctx_open_folder": L("Open Containing Folder&打开所在文件夹"),
            "ctx_remove_selected": L("Remove Selected&移除选中项"),
            "ctx_clear_all": L("Clear All&清空所有"),
            "close": L("Close&关闭"),
        }, ensure_ascii=False)
        self.bridge.uiTextsUpdated.emit(translations)
        self._emit_styles()
        self.statusBar().showMessage(L("Ready&就绪"))

    def _emit_styles(self):
        styles = self.style_manager.list_styles()
        last_style = self.config.get('ui', {}).get('last_style', 'CANON&佳能')
        style_data = [{"value": s, "display": L(s)} for s in styles]
        current = last_style if last_style in styles else (styles[0] if styles else "")
        payload = json.dumps({
            "styles": style_data,
            "current": current,
            "currentDisplay": L(current) if current else ""
        }, ensure_ascii=False)
        self.bridge.stylesUpdated.emit(payload)

    # ---------- State ----------
    def _load_ui_state(self):
        geometry = self.config.get('ui', {}).get('window_geometry', '')
        if geometry:
            try:
                self.restoreGeometry(bytes.fromhex(geometry))
            except:
                pass

    def _save_ui_state(self):
        self.config['ui']['window_geometry'] = self.saveGeometry().toHex().data().decode()
        self.config_manager.save(self.config)

    def _restore_last_session(self):
        files = self.config_manager.get_last_session_files()
        if files:
            existing_files = [f for f in files if Path(f).exists()]
            if existing_files:
                self._add_files(existing_files)

    def _save_session(self):
        if self.config.get('general', {}).get('restore_last_session', True):
            files = self.bridge.get_all_files()
            self.config_manager.save_session_files(files)
        else:
            self.config_manager.clear_session_files()

    def closeEvent(self, event):
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
    app = QApplication(sys.argv)
    app.setApplicationName("Photo Timestamper")
    app.setOrganizationName("PhotoTimestamper")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
    
"""
Photo-Timestamper 多语言支持模块
"""

from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh-CN": {
        # 应用信息
        "app_name": "Photo Timestamper",
        "app_name_cn": "照片时间戳水印工具",

        # 菜单
        "menu_settings": "设置",
        "menu_about": "关于",

        # 左侧面板
        "panel_import": "导入",
        "btn_add_images": "添加图片",
        "panel_image_list": "图片列表",
        "search_placeholder": "搜索图片...",
        "image_count": "共 {count} 张图片",
        "btn_clear_list": "清空列表",
        "panel_watermark_style": "水印样式",
        "btn_process_selected": "处理选中的图片",
        "btn_process_all": "处理全部图片",

        # 预览面板
        "preview_original": "原图预览",
        "preview_result": "效果预览",

        # 进度
        "processing": "处理中...",
        "processing_progress": "正在处理 {current}/{total}: {filename}",
        "btn_cancel": "取消",
        "cancelling": "正在取消...",

        # 导入对话框
        "import_title": "导入图片",
        "import_desc": "选择导入图片的方式：",
        "import_recursive": "递归扫描子文件夹中的图片",
        "import_select_files": "选择图片文件",
        "import_select_folder": "选择文件夹",
        "import_cancel": "取消",
        "import_filter": "JPEG 图片 (*.jpg *.jpeg *.JPG *.JPEG)",

        # 设置对话框
        "settings_title": "设置",
        "settings_language": "语言 / Language",
        "settings_time_source": "时间来源",
        "settings_primary_source": "主时间源",
        "settings_exif": "EXIF 拍摄时间（推荐）",
        "settings_file_modified": "文件修改时间",
        "settings_file_created": "文件创建时间",
        "settings_fallback": "EXIF 不可用时自动降级使用文件时间",
        "settings_output": "输出设置",
        "settings_same_dir": "保存到原图所在目录",
        "settings_output_dir": "自定义输出目录...",
        "settings_browse": "浏览",
        "settings_filename_pattern": "输出文件名格式",
        "settings_filename_tooltip": "可用变量：{original}, {date}, {time}, {index}",
        "settings_jpeg_quality": "JPEG 质量",
        "settings_preserve_exif": "保留原始 EXIF 信息",
        "settings_overwrite": "覆盖已存在的文件",
        "settings_reset": "恢复默认",
        "settings_save": "保存",

        # 关于对话框
        "about_title": "关于",
        "about_version": "版本 {version}",
        "about_author": "作者：{author}",
        "about_collaborators": "协作开发",
        "about_license": "许可证：GPL-3.0",
        "about_github": "在 GitHub 上查看",
        "about_close": "关闭",

        # 语言选择对话框
        "language_select_title": "选择语言 / Select Language",
        "language_select_desc": "请选择您的首选语言：",
        "language_confirm": "确定",

        # 消息
        "msg_ready": "就绪",
        "msg_added_images": "已添加 {count} 张图片",
        "msg_duplicate_skipped": "跳过 {count} 张重复图片",
        "msg_no_images": "请先添加图片",
        "msg_process_complete": "处理完成: 成功 {success}, 失败 {failed}",
        "msg_process_error": "处理出错",
        "msg_confirm_exit": "确认退出",
        "msg_exit_processing": "正在处理中，确定要退出吗？",
        "msg_exit_unsaved": "当前打开的内容将会丢失，确定要退出吗？",
        "msg_success": "成功处理 {count} 张图片",
        "msg_partial_success": "成功处理 {success} 张图片\n失败 {failed} 张",
        "msg_error_details": "错误信息",
        "msg_more_errors": "... 还有 {count} 个错误",

        # 右键菜单
        "ctx_remove_selected": "移除选中",
        "ctx_clear_all": "清空列表",

        # 拖放提示
        "drop_hint": "拖放图片或文件夹\n到此处添加",

        # 工具提示
        "tooltip_import": "导入图片文件或文件夹 (Ctrl+I)",
        "tooltip_clear": "清空图片列表 (Ctrl+Shift+C)",
        "tooltip_process": "开始处理图片 (Ctrl+Enter)",
        "tooltip_settings": "打开设置 (Ctrl+,)",
    },

    "en": {
        # App info
        "app_name": "Photo Timestamper",
        "app_name_cn": "Photo Timestamp Watermark Tool",

        # Menu
        "menu_settings": "Settings",
        "menu_about": "About",

        # Left panel
        "panel_import": "Import",
        "btn_add_images": "Add Images",
        "panel_image_list": "Image List",
        "search_placeholder": "Search images...",
        "image_count": "{count} images",
        "btn_clear_list": "Clear List",
        "panel_watermark_style": "Watermark Style",
        "btn_process_selected": "Process Selected",
        "btn_process_all": "Process All",

        # Preview panel
        "preview_original": "Original Preview",
        "preview_result": "Result Preview",

        # Progress
        "processing": "Processing...",
        "processing_progress": "Processing {current}/{total}: {filename}",
        "btn_cancel": "Cancel",
        "cancelling": "Cancelling...",

        # Import dialog
        "import_title": "Import Images",
        "import_desc": "Select import method:",
        "import_recursive": "Recursively scan subfolders",
        "import_select_files": "Select Image Files",
        "import_select_folder": "Select Folder",
        "import_cancel": "Cancel",
        "import_filter": "JPEG Images (*.jpg *.jpeg *.JPG *.JPEG)",

        # Settings dialog
        "settings_title": "Settings",
        "settings_language": "Language / 语言",
        "settings_time_source": "Time Source",
        "settings_primary_source": "Primary Source",
        "settings_exif": "EXIF Date Taken (Recommended)",
        "settings_file_modified": "File Modified Time",
        "settings_file_created": "File Created Time",
        "settings_fallback": "Fallback to file time when EXIF unavailable",
        "settings_output": "Output Settings",
        "settings_same_dir": "Save to original directory",
        "settings_output_dir": "Custom output directory...",
        "settings_browse": "Browse",
        "settings_filename_pattern": "Output Filename Pattern",
        "settings_filename_tooltip": "Variables: {original}, {date}, {time}, {index}",
        "settings_jpeg_quality": "JPEG Quality",
        "settings_preserve_exif": "Preserve original EXIF data",
        "settings_overwrite": "Overwrite existing files",
        "settings_reset": "Reset to Default",
        "settings_save": "Save",

        # About dialog
        "about_title": "About",
        "about_version": "Version {version}",
        "about_author": "Author: {author}",
        "about_collaborators": "Collaborators",
        "about_license": "License: GPL-3.0",
        "about_github": "View on GitHub",
        "about_close": "Close",

        # Language selection
        "language_select_title": "Select Language / 选择语言",
        "language_select_desc": "Please select your preferred language:",
        "language_confirm": "Confirm",

        # Messages
        "msg_ready": "Ready",
        "msg_added_images": "Added {count} images",
        "msg_duplicate_skipped": "Skipped {count} duplicate images",
        "msg_no_images": "Please add images first",
        "msg_process_complete": "Complete: {success} succeeded, {failed} failed",
        "msg_process_error": "Processing error",
        "msg_confirm_exit": "Confirm Exit",
        "msg_exit_processing": "Processing in progress. Are you sure you want to exit?",
        "msg_exit_unsaved": "Current content will be lost. Are you sure you want to exit?",
        "msg_success": "Successfully processed {count} images",
        "msg_partial_success": "Successfully processed {success} images\nFailed: {failed}",
        "msg_error_details": "Error details",
        "msg_more_errors": "... and {count} more errors",

        # Context menu
        "ctx_remove_selected": "Remove Selected",
        "ctx_clear_all": "Clear All",

        # Drop hint
        "drop_hint": "Drop images or folders\nhere to add",

        # Tooltips
        "tooltip_import": "Import image files or folders (Ctrl+I)",
        "tooltip_clear": "Clear image list (Ctrl+Shift+C)",
        "tooltip_process": "Start processing images (Ctrl+Enter)",
        "tooltip_settings": "Open settings (Ctrl+,)",
    },

    "fr": {
        # App info
        "app_name": "Photo Timestamper",
        "app_name_cn": "Outil de filigrane horodaté",

        # Menu
        "menu_settings": "Paramètres",
        "menu_about": "À propos",

        # Left panel
        "panel_import": "Importer",
        "btn_add_images": "Ajouter des images",
        "panel_image_list": "Liste des images",
        "search_placeholder": "Rechercher des images...",
        "image_count": "{count} images",
        "btn_clear_list": "Effacer la liste",
        "panel_watermark_style": "Style du filigrane",
        "btn_process_selected": "Traiter la sélection",
        "btn_process_all": "Traiter tout",

        # Preview panel
        "preview_original": "Aperçu original",
        "preview_result": "Aperçu du résultat",

        # Progress
        "processing": "Traitement en cours...",
        "processing_progress": "Traitement {current}/{total}: {filename}",
        "btn_cancel": "Annuler",
        "cancelling": "Annulation...",

        # Import dialog
        "import_title": "Importer des images",
        "import_desc": "Sélectionnez la méthode d'importation:",
        "import_recursive": "Scanner récursivement les sous-dossiers",
        "import_select_files": "Sélectionner des fichiers",
        "import_select_folder": "Sélectionner un dossier",
        "import_cancel": "Annuler",
        "import_filter": "Images JPEG (*.jpg *.jpeg *.JPG *.JPEG)",

        # Settings dialog
        "settings_title": "Paramètres",
        "settings_language": "Langue / Language",
        "settings_time_source": "Source de temps",
        "settings_primary_source": "Source principale",
        "settings_exif": "Date EXIF (Recommandé)",
        "settings_file_modified": "Date de modification",
        "settings_file_created": "Date de création",
        "settings_fallback": "Utiliser le temps du fichier si EXIF indisponible",
        "settings_output": "Paramètres de sortie",
        "settings_same_dir": "Enregistrer dans le dossier d'origine",
        "settings_output_dir": "Dossier de sortie personnalisé...",
        "settings_browse": "Parcourir",
        "settings_filename_pattern": "Format du nom de fichier",
        "settings_filename_tooltip": "Variables: {original}, {date}, {time}, {index}",
        "settings_jpeg_quality": "Qualité JPEG",
        "settings_preserve_exif": "Conserver les données EXIF",
        "settings_overwrite": "Écraser les fichiers existants",
        "settings_reset": "Réinitialiser",
        "settings_save": "Enregistrer",

        # About dialog
        "about_title": "À propos",
        "about_version": "Version {version}",
        "about_author": "Auteur: {author}",
        "about_collaborators": "Collaborateurs",
        "about_license": "Licence: GPL-3.0",
        "about_github": "Voir sur GitHub",
        "about_close": "Fermer",

        # Language selection
        "language_select_title": "Sélectionner la langue",
        "language_select_desc": "Veuillez sélectionner votre langue préférée:",
        "language_confirm": "Confirmer",

        # Messages
        "msg_ready": "Prêt",
        "msg_added_images": "{count} images ajoutées",
        "msg_duplicate_skipped": "{count} images en double ignorées",
        "msg_no_images": "Veuillez d'abord ajouter des images",
        "msg_process_complete": "Terminé: {success} réussis, {failed} échoués",
        "msg_process_error": "Erreur de traitement",
        "msg_confirm_exit": "Confirmer la sortie",
        "msg_exit_processing": "Traitement en cours. Voulez-vous vraiment quitter?",
        "msg_exit_unsaved": "Le contenu actuel sera perdu. Voulez-vous vraiment quitter?",
        "msg_success": "{count} images traitées avec succès",
        "msg_partial_success": "{success} images traitées avec succès\nÉchecs: {failed}",
        "msg_error_details": "Détails de l'erreur",
        "msg_more_errors": "... et {count} autres erreurs",

        # Context menu
        "ctx_remove_selected": "Supprimer la sélection",
        "ctx_clear_all": "Tout effacer",

        # Drop hint
        "drop_hint": "Déposez des images ou dossiers\nici pour les ajouter",

        # Tooltips
        "tooltip_import": "Importer des fichiers ou dossiers (Ctrl+I)",
        "tooltip_clear": "Effacer la liste (Ctrl+Shift+C)",
        "tooltip_process": "Démarrer le traitement (Ctrl+Entrée)",
        "tooltip_settings": "Ouvrir les paramètres (Ctrl+,)",
    },
}

LANGUAGE_NAMES = {
    "zh-CN": "简体中文",
    "en": "English",
    "fr": "Français",
}


class I18n:
    """国际化管理器"""

    _instance = None
    _current_language = "zh-CN"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_language(cls, lang: str):
        """设置当前语言"""
        if lang in TRANSLATIONS:
            cls._current_language = lang

    @classmethod
    def get_language(cls) -> str:
        """获取当前语言"""
        return cls._current_language

    @classmethod
    def t(cls, key: str, **kwargs) -> str:
        """获取翻译文本"""
        translations = TRANSLATIONS.get(cls._current_language, TRANSLATIONS["en"])
        text = translations.get(key, key)

        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass

        return text

    @classmethod
    def get_available_languages(cls) -> dict:
        """获取所有可用语言"""
        return LANGUAGE_NAMES.copy()


def t(key: str, **kwargs) -> str:
    """翻译快捷函数"""
    return I18n.t(key, **kwargs)
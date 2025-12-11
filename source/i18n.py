# i18n.py
"""
Photo-Timestamper 多语言支持模块 - 完整覆盖版
"""

from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh-CN": {
        # 应用信息
        "app_name": "Photo Timestamper",
        "app_name_cn": "照片时间戳水印工具",

        # 菜单栏
        "menu_file": "文件",
        "menu_edit": "编辑",
        "menu_help": "帮助",
        "menu_import": "导入图片...",
        "menu_import_folder": "导入文件夹...",
        "menu_clear_list": "清空列表",
        "menu_exit": "退出",
        "menu_select_all": "全选",
        "menu_deselect_all": "取消全选",
        "menu_remove_selected": "移除选中",
        "menu_settings": "设置...",
        "menu_about": "关于",

        # 左侧面板
        "panel_image_list": "图片列表",
        "panel_watermark_style": "水印样式",
        "search_placeholder": "搜索图片...",
        "image_count": "共 {count} 张图片",
        "image_selected_count": "已选择 {selected} / {total} 张",
        "btn_add_images": "添加图片",
        "btn_add_folder": "添加文件夹",
        "btn_clear_list": "清空",
        "btn_select_all": "全选",
        "btn_process": "开始处理",
        "btn_process_selected": "处理选中",

        # 预览面板
        "preview_original": "原图",
        "preview_result": "效果预览",
        "preview_no_image": "选择图片以预览",

        # 进度
        "processing": "处理中...",
        "processing_progress": "正在处理 {current}/{total}: {filename}",
        "btn_cancel": "取消",
        "cancelling": "正在取消...",

        # 导入对话框
        "import_title": "导入图片",
        "import_desc": "选择导入方式：",
        "import_recursive": "递归扫描子文件夹",
        "import_select_files": "选择图片文件",
        "import_select_folder": "选择文件夹",
        "import_cancel": "取消",
        "import_filter": "JPEG 图片 (*.jpg *.jpeg *.JPG *.JPEG)",

        # 设置对话框
        "settings_title": "设置",
        "settings_tab_general": "常规",
        "settings_tab_output": "输出",
        "settings_tab_advanced": "高级",
        "settings_language": "界面语言",
        "settings_restore_session": "启动时恢复上次打开的图片",
        "settings_time_source": "时间来源",
        "settings_primary_source": "主时间源",
        "settings_exif": "EXIF 拍摄时间（推荐）",
        "settings_file_modified": "文件修改时间",
        "settings_file_created": "文件创建时间",
        "settings_fallback": "EXIF 不可用时自动使用文件时间",
        "settings_output": "输出设置",
        "settings_same_dir": "保存到原图所在目录",
        "settings_custom_dir": "自定义输出目录",
        "settings_output_dir": "输出目录...",
        "settings_browse": "浏览...",
        "settings_filename_pattern": "文件名格式",
        "settings_filename_tooltip": "可用变量：{original}=原文件名, {date}=日期, {time}=时间, {index}=序号",
        "settings_jpeg_quality": "JPEG 质量",
        "settings_preserve_exif": "保留原始 EXIF 信息",
        "settings_overwrite": "覆盖已存在的文件",
        "settings_reset": "恢复默认",
        "settings_cancel": "取消",
        "settings_save": "保存",
        "settings_apply": "应用",

        # 关于对话框
        "about_title": "关于 Photo Timestamper",
        "about_version": "版本 {version}",
        "about_description": "一款为照片添加时间戳水印的专业工具",
        "about_author": "作者",
        "about_collaborators": "协作开发",
        "about_license": "许可证",
        "about_license_type": "GPL-3.0",
        "about_github": "GitHub 仓库",
        "about_close": "关闭",

        # 语言选择对话框
        "language_select_title": "选择语言 / Select Language",
        "language_select_desc": "请选择界面语言：",
        "language_confirm": "确定",

        # 消息和状态
        "msg_ready": "就绪",
        "msg_added_images": "已添加 {count} 张图片",
        "msg_duplicate_skipped": "跳过 {count} 张重复图片",
        "msg_no_images": "请先添加图片",
        "msg_no_selection": "请选择要处理的图片",
        "msg_process_complete": "处理完成：成功 {success} 张，失败 {failed} 张",
        "msg_process_error": "处理出错",
        "msg_confirm_exit": "确认退出",
        "msg_exit_processing": "正在处理图片，确定要退出吗？",
        "msg_exit_unsaved": "当前打开的图片列表将不会保存，确定要退出吗？",
        "msg_success": "成功处理 {count} 张图片",
        "msg_partial_success": "处理完成\n成功：{success} 张\n失败：{failed} 张",
        "msg_error_details": "错误详情",
        "msg_more_errors": "... 还有 {count} 个错误",
        "msg_file_not_found": "文件不存在：{filename}",
        "msg_style_load_error": "无法加载样式：{style}",
        "msg_settings_saved": "设置已保存",
        "msg_settings_reset": "已恢复默认设置",
        "msg_language_changed": "语言已更改，部分更改需要重启生效",
        "msg_cleared": "已清空图片列表",
        "msg_removed": "已移除 {count} 张图片",

        # 右键菜单
        "ctx_open_file": "打开文件",
        "ctx_open_folder": "打开所在文件夹",
        "ctx_remove_selected": "移除选中项",
        "ctx_clear_all": "清空所有",
        "ctx_select_all": "全选",
        "ctx_deselect_all": "取消全选",
        "ctx_check_selected": "勾选选中项",
        "ctx_uncheck_selected": "取消勾选选中项",

        # 拖放提示
        "drop_hint": "将图片或文件夹拖放到此处\n或点击下方按钮添加",

        # 工具提示
        "tooltip_add_images": "添加图片文件 (Ctrl+O)",
        "tooltip_add_folder": "添加整个文件夹 (Ctrl+Shift+O)",
        "tooltip_clear": "清空图片列表 (Ctrl+Shift+Del)",
        "tooltip_select_all": "全选所有图片 (Ctrl+A)",
        "tooltip_process": "开始处理图片 (Ctrl+Enter)",
        "tooltip_settings": "打开设置 (Ctrl+,)",
        "tooltip_style": "选择水印样式",
        "tooltip_search": "搜索图片文件名",

        # 复选框状态
        "checkbox_checked": "已勾选",
        "checkbox_unchecked": "未勾选",

        # 文件信息
        "file_info_name": "文件名",
        "file_info_path": "路径",
        "file_info_size": "大小",
        "file_info_date": "日期",
        "file_info_dimensions": "尺寸",

        # 错误消息
        "error_title": "错误",
        "error_file_read": "无法读取文件：{filename}",
        "error_file_write": "无法写入文件：{filename}",
        "error_no_exif": "无法读取 EXIF 信息",
        "error_invalid_image": "无效的图片文件",
        "error_permission": "权限不足",
        "error_disk_full": "磁盘空间不足",
        "error_unknown": "未知错误：{error}",

        # 确认对话框
        "confirm_title": "确认",
        "confirm_clear": "确定要清空所有图片吗？",
        "confirm_remove": "确定要移除选中的 {count} 张图片吗？",
        "confirm_overwrite": "目标文件已存在，是否覆盖？",
        "confirm_yes": "是",
        "confirm_no": "否",
        "confirm_ok": "确定",
        "confirm_cancel": "取消",
    },

    "en": {
        # App info
        "app_name": "Photo Timestamper",
        "app_name_cn": "Photo Timestamp Watermark Tool",

        # Menu bar
        "menu_file": "File",
        "menu_edit": "Edit",
        "menu_help": "Help",
        "menu_import": "Import Images...",
        "menu_import_folder": "Import Folder...",
        "menu_clear_list": "Clear List",
        "menu_exit": "Exit",
        "menu_select_all": "Select All",
        "menu_deselect_all": "Deselect All",
        "menu_remove_selected": "Remove Selected",
        "menu_settings": "Settings...",
        "menu_about": "About",

        # Left panel
        "panel_image_list": "Image List",
        "panel_watermark_style": "Watermark Style",
        "search_placeholder": "Search images...",
        "image_count": "{count} images",
        "image_selected_count": "{selected} / {total} selected",
        "btn_add_images": "Add Images",
        "btn_add_folder": "Add Folder",
        "btn_clear_list": "Clear",
        "btn_select_all": "Select All",
        "btn_process": "Process",
        "btn_process_selected": "Process Selected",

        # Preview panel
        "preview_original": "Original",
        "preview_result": "Preview",
        "preview_no_image": "Select an image to preview",

        # Progress
        "processing": "Processing...",
        "processing_progress": "Processing {current}/{total}: {filename}",
        "btn_cancel": "Cancel",
        "cancelling": "Cancelling...",

        # Import dialog
        "import_title": "Import Images",
        "import_desc": "Select import method:",
        "import_recursive": "Scan subfolders recursively",
        "import_select_files": "Select Image Files",
        "import_select_folder": "Select Folder",
        "import_cancel": "Cancel",
        "import_filter": "JPEG Images (*.jpg *.jpeg *.JPG *.JPEG)",

        # Settings dialog
        "settings_title": "Settings",
        "settings_tab_general": "General",
        "settings_tab_output": "Output",
        "settings_tab_advanced": "Advanced",
        "settings_language": "Interface Language",
        "settings_restore_session": "Restore images from last session on startup",
        "settings_time_source": "Time Source",
        "settings_primary_source": "Primary Source",
        "settings_exif": "EXIF Date Taken (Recommended)",
        "settings_file_modified": "File Modified Time",
        "settings_file_created": "File Created Time",
        "settings_fallback": "Fallback to file time when EXIF unavailable",
        "settings_output": "Output Settings",
        "settings_same_dir": "Save to original directory",
        "settings_custom_dir": "Custom output directory",
        "settings_output_dir": "Output directory...",
        "settings_browse": "Browse...",
        "settings_filename_pattern": "Filename Pattern",
        "settings_filename_tooltip": "Variables: {original}=original name, {date}=date, {time}=time, {index}=index",
        "settings_jpeg_quality": "JPEG Quality",
        "settings_preserve_exif": "Preserve original EXIF data",
        "settings_overwrite": "Overwrite existing files",
        "settings_reset": "Reset to Default",
        "settings_cancel": "Cancel",
        "settings_save": "Save",
        "settings_apply": "Apply",

        # About dialog
        "about_title": "About Photo Timestamper",
        "about_version": "Version {version}",
        "about_description": "A professional tool for adding timestamp watermarks to photos",
        "about_author": "Author",
        "about_collaborators": "Collaborators",
        "about_license": "License",
        "about_license_type": "GPL-3.0",
        "about_github": "GitHub Repository",
        "about_close": "Close",

        # Language selection
        "language_select_title": "Select Language / 选择语言",
        "language_select_desc": "Please select your preferred language:",
        "language_confirm": "Confirm",

        # Messages and status
        "msg_ready": "Ready",
        "msg_added_images": "Added {count} images",
        "msg_duplicate_skipped": "Skipped {count} duplicate images",
        "msg_no_images": "Please add images first",
        "msg_no_selection": "Please select images to process",
        "msg_process_complete": "Complete: {success} succeeded, {failed} failed",
        "msg_process_error": "Processing error",
        "msg_confirm_exit": "Confirm Exit",
        "msg_exit_processing": "Processing in progress. Are you sure you want to exit?",
        "msg_exit_unsaved": "The current image list will not be saved. Are you sure you want to exit?",
        "msg_success": "Successfully processed {count} images",
        "msg_partial_success": "Processing complete\nSuccess: {success}\nFailed: {failed}",
        "msg_error_details": "Error details",
        "msg_more_errors": "... and {count} more errors",
        "msg_file_not_found": "File not found: {filename}",
        "msg_style_load_error": "Cannot load style: {style}",
        "msg_settings_saved": "Settings saved",
        "msg_settings_reset": "Settings reset to default",
        "msg_language_changed": "Language changed. Some changes may require restart.",
        "msg_cleared": "Image list cleared",
        "msg_removed": "Removed {count} images",

        # Context menu
        "ctx_open_file": "Open File",
        "ctx_open_folder": "Open Containing Folder",
        "ctx_remove_selected": "Remove Selected",
        "ctx_clear_all": "Clear All",
        "ctx_select_all": "Select All",
        "ctx_deselect_all": "Deselect All",
        "ctx_check_selected": "Check Selected",
        "ctx_uncheck_selected": "Uncheck Selected",

        # Drop hint
        "drop_hint": "Drop images or folders here\nor click button below to add",

        # Tooltips
        "tooltip_add_images": "Add image files (Ctrl+O)",
        "tooltip_add_folder": "Add entire folder (Ctrl+Shift+O)",
        "tooltip_clear": "Clear image list (Ctrl+Shift+Del)",
        "tooltip_select_all": "Select all images (Ctrl+A)",
        "tooltip_process": "Start processing (Ctrl+Enter)",
        "tooltip_settings": "Open settings (Ctrl+,)",
        "tooltip_style": "Select watermark style",
        "tooltip_search": "Search by filename",

        # Checkbox state
        "checkbox_checked": "Checked",
        "checkbox_unchecked": "Unchecked",

        # File info
        "file_info_name": "Filename",
        "file_info_path": "Path",
        "file_info_size": "Size",
        "file_info_date": "Date",
        "file_info_dimensions": "Dimensions",

        # Error messages
        "error_title": "Error",
        "error_file_read": "Cannot read file: {filename}",
        "error_file_write": "Cannot write file: {filename}",
        "error_no_exif": "Cannot read EXIF data",
        "error_invalid_image": "Invalid image file",
        "error_permission": "Permission denied",
        "error_disk_full": "Disk is full",
        "error_unknown": "Unknown error: {error}",

        # Confirm dialogs
        "confirm_title": "Confirm",
        "confirm_clear": "Are you sure you want to clear all images?",
        "confirm_remove": "Are you sure you want to remove {count} selected images?",
        "confirm_overwrite": "Target file already exists. Overwrite?",
        "confirm_yes": "Yes",
        "confirm_no": "No",
        "confirm_ok": "OK",
        "confirm_cancel": "Cancel",
    },

    "fr": {
        # App info
        "app_name": "Photo Timestamper",
        "app_name_cn": "Outil de filigrane horodaté",

        # Menu bar
        "menu_file": "Fichier",
        "menu_edit": "Édition",
        "menu_help": "Aide",
        "menu_import": "Importer des images...",
        "menu_import_folder": "Importer un dossier...",
        "menu_clear_list": "Effacer la liste",
        "menu_exit": "Quitter",
        "menu_select_all": "Tout sélectionner",
        "menu_deselect_all": "Tout désélectionner",
        "menu_remove_selected": "Supprimer la sélection",
        "menu_settings": "Paramètres...",
        "menu_about": "À propos",

        # Left panel
        "panel_image_list": "Liste des images",
        "panel_watermark_style": "Style du filigrane",
        "search_placeholder": "Rechercher des images...",
        "image_count": "{count} images",
        "image_selected_count": "{selected} / {total} sélectionnées",
        "btn_add_images": "Ajouter des images",
        "btn_add_folder": "Ajouter un dossier",
        "btn_clear_list": "Effacer",
        "btn_select_all": "Tout sélectionner",
        "btn_process": "Traiter",
        "btn_process_selected": "Traiter la sélection",

        # Preview panel
        "preview_original": "Original",
        "preview_result": "Aperçu",
        "preview_no_image": "Sélectionnez une image pour l'aperçu",

        # Progress
        "processing": "Traitement en cours...",
        "processing_progress": "Traitement {current}/{total}: {filename}",
        "btn_cancel": "Annuler",
        "cancelling": "Annulation...",

        # Import dialog
        "import_title": "Importer des images",
        "import_desc": "Sélectionnez la méthode d'importation:",
        "import_recursive": "Scanner les sous-dossiers récursivement",
        "import_select_files": "Sélectionner des fichiers",
        "import_select_folder": "Sélectionner un dossier",
        "import_cancel": "Annuler",
        "import_filter": "Images JPEG (*.jpg *.jpeg *.JPG *.JPEG)",

        # Settings dialog
        "settings_title": "Paramètres",
        "settings_tab_general": "Général",
        "settings_tab_output": "Sortie",
        "settings_tab_advanced": "Avancé",
        "settings_language": "Langue de l'interface",
        "settings_restore_session": "Restaurer les images de la dernière session au démarrage",
        "settings_time_source": "Source de temps",
        "settings_primary_source": "Source principale",
        "settings_exif": "Date EXIF (Recommandé)",
        "settings_file_modified": "Date de modification du fichier",
        "settings_file_created": "Date de création du fichier",
        "settings_fallback": "Utiliser le temps du fichier si EXIF indisponible",
        "settings_output": "Paramètres de sortie",
        "settings_same_dir": "Enregistrer dans le dossier d'origine",
        "settings_custom_dir": "Dossier de sortie personnalisé",
        "settings_output_dir": "Dossier de sortie...",
        "settings_browse": "Parcourir...",
        "settings_filename_pattern": "Format du nom de fichier",
        "settings_filename_tooltip": "Variables: {original}=nom original, {date}=date, {time}=heure, {index}=index",
        "settings_jpeg_quality": "Qualité JPEG",
        "settings_preserve_exif": "Conserver les données EXIF originales",
        "settings_overwrite": "Écraser les fichiers existants",
        "settings_reset": "Réinitialiser",
        "settings_cancel": "Annuler",
        "settings_save": "Enregistrer",
        "settings_apply": "Appliquer",

        # About dialog
        "about_title": "À propos de Photo Timestamper",
        "about_version": "Version {version}",
        "about_description": "Un outil professionnel pour ajouter des filigranes horodatés aux photos",
        "about_author": "Auteur",
        "about_collaborators": "Collaborateurs",
        "about_license": "Licence",
        "about_license_type": "GPL-3.0",
        "about_github": "Dépôt GitHub",
        "about_close": "Fermer",

        # Language selection
        "language_select_title": "Sélectionner la langue",
        "language_select_desc": "Veuillez sélectionner votre langue préférée:",
        "language_confirm": "Confirmer",

        # Messages and status
        "msg_ready": "Prêt",
        "msg_added_images": "{count} images ajoutées",
        "msg_duplicate_skipped": "{count} images en double ignorées",
        "msg_no_images": "Veuillez d'abord ajouter des images",
        "msg_no_selection": "Veuillez sélectionner des images à traiter",
        "msg_process_complete": "Terminé: {success} réussis, {failed} échoués",
        "msg_process_error": "Erreur de traitement",
        "msg_confirm_exit": "Confirmer la sortie",
        "msg_exit_processing": "Traitement en cours. Voulez-vous vraiment quitter?",
        "msg_exit_unsaved": "La liste d'images actuelle ne sera pas sauvegardée. Voulez-vous vraiment quitter?",
        "msg_success": "{count} images traitées avec succès",
        "msg_partial_success": "Traitement terminé\nRéussi: {success}\nÉchoué: {failed}",
        "msg_error_details": "Détails de l'erreur",
        "msg_more_errors": "... et {count} autres erreurs",
        "msg_file_not_found": "Fichier non trouvé: {filename}",
        "msg_style_load_error": "Impossible de charger le style: {style}",
        "msg_settings_saved": "Paramètres enregistrés",
        "msg_settings_reset": "Paramètres réinitialisés",
        "msg_language_changed": "Langue modifiée. Certains changements nécessitent un redémarrage.",
        "msg_cleared": "Liste d'images effacée",
        "msg_removed": "{count} images supprimées",

        # Context menu
        "ctx_open_file": "Ouvrir le fichier",
        "ctx_open_folder": "Ouvrir le dossier contenant",
        "ctx_remove_selected": "Supprimer la sélection",
        "ctx_clear_all": "Tout effacer",
        "ctx_select_all": "Tout sélectionner",
        "ctx_deselect_all": "Tout désélectionner",
        "ctx_check_selected": "Cocher la sélection",
        "ctx_uncheck_selected": "Décocher la sélection",

        # Drop hint
        "drop_hint": "Déposez des images ou dossiers ici\nou cliquez sur le bouton ci-dessous",

        # Tooltips
        "tooltip_add_images": "Ajouter des fichiers image (Ctrl+O)",
        "tooltip_add_folder": "Ajouter un dossier entier (Ctrl+Shift+O)",
        "tooltip_clear": "Effacer la liste (Ctrl+Shift+Suppr)",
        "tooltip_select_all": "Tout sélectionner (Ctrl+A)",
        "tooltip_process": "Démarrer le traitement (Ctrl+Entrée)",
        "tooltip_settings": "Ouvrir les paramètres (Ctrl+,)",
        "tooltip_style": "Sélectionner le style de filigrane",
        "tooltip_search": "Rechercher par nom de fichier",

        # Checkbox state
        "checkbox_checked": "Coché",
        "checkbox_unchecked": "Non coché",

        # File info
        "file_info_name": "Nom du fichier",
        "file_info_path": "Chemin",
        "file_info_size": "Taille",
        "file_info_date": "Date",
        "file_info_dimensions": "Dimensions",

        # Error messages
        "error_title": "Erreur",
        "error_file_read": "Impossible de lire le fichier: {filename}",
        "error_file_write": "Impossible d'écrire le fichier: {filename}",
        "error_no_exif": "Impossible de lire les données EXIF",
        "error_invalid_image": "Fichier image invalide",
        "error_permission": "Permission refusée",
        "error_disk_full": "Disque plein",
        "error_unknown": "Erreur inconnue: {error}",

        # Confirm dialogs
        "confirm_title": "Confirmer",
        "confirm_clear": "Voulez-vous vraiment effacer toutes les images?",
        "confirm_remove": "Voulez-vous vraiment supprimer {count} images sélectionnées?",
        "confirm_overwrite": "Le fichier cible existe déjà. Écraser?",
        "confirm_yes": "Oui",
        "confirm_no": "Non",
        "confirm_ok": "OK",
        "confirm_cancel": "Annuler",
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
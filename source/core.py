"""
Photo-Timestamper Core Module&照片时间戳核心模块
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Tuple, Optional

import yaml
from PIL import Image, ImageDraw, ImageFont
import piexif
import simpsave as ss


# ==================== Localization System&本地化系统 ====================

class LocalizationManager:
    """
    Bilingual localization manager&双语本地化管理器
    Format: "English&中文"
    """
    
    _instance = None
    _language = "zh"  # "en" or "zh"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def set_language(cls, lang: str):
        """Set current language&设置当前语言"""
        if lang in ("en", "zh", "zh-CN", "en-US"):
            cls._language = "zh" if lang.startswith("zh") else "en"
    
    @classmethod
    def get_language(cls) -> str:
        """Get current language&获取当前语言"""
        return cls._language
    
    @classmethod
    def parse(cls, text: str) -> str:
        """
        Parse bilingual text&解析双语文本
        Input: "English&中文" -> Output based on current language
        """
        if not text or "&" not in text:
            return text
        
        parts = text.split("&", 1)
        if len(parts) != 2:
            return text
        
        en_text, zh_text = parts
        return zh_text.strip() if cls._language == "zh" else en_text.strip()


def L(text: str) -> str:
    """
    Shortcut for localization&本地化快捷函数
    Usage: L("Hello&你好") -> "你好" or "Hello"
    """
    return LocalizationManager.parse(text)


# ==================== Logging Configuration&日志配置 ====================

class BilingualFormatter(logging.Formatter):
    """Formatter that parses bilingual messages&解析双语消息的格式化器"""
    
    def format(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = L(record.msg)
        return super().format(record)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('photo-timestamper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

for handler in logging.root.handlers:
    handler.setFormatter(BilingualFormatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger(__name__)


# ==================== Configuration Files&配置文件 ====================

SS_CONFIG_FILE = './simpsave/photo_timestamper_config.json'
SS_SESSION_FILE = './simpsave/photo_timestamper_session.json'


def get_base_path() -> Path:
    """Get program base path&获取程序基础路径"""
    return Path(__file__).parent.parent


class ConfigManager:
    """Configuration Manager&配置管理器"""

    DEFAULT_CONFIG = {
        "general": {
            "language": "zh",
            "first_run": True,
            "restore_last_session": True
        },
        "time_source": {
            "primary": "exif",
            "fallback_mode": "error",  # error, file_modified, file_created, custom
            "custom_time": ""
        },
        "output": {
            "same_directory": True,
            "custom_directory": "",
            "filename_pattern": "{original}_stamped",
            "jpeg_quality": 95,
            "preserve_exif": True,
            "overwrite_existing": False
        },
        "ui": {
            "last_style": "CANON&佳能",
            "preview_enabled": True,
            "window_geometry": ""
        }
    }

    def __init__(self):
        self._config = None

    def load(self) -> dict:
        """Load configuration&加载配置"""
        if self._config is not None:
            return self._config

        try:
            if ss.has('config', file=SS_CONFIG_FILE):
                stored_config = ss.read('config', file=SS_CONFIG_FILE)
                if stored_config is not None:
                    self._config = self._merge_with_defaults(stored_config)
                    logger.info("Configuration loaded from simpsave&配置已从simpsave加载")
                else:
                    self._config = self._get_default_copy()
                    self._save_to_file(self._config)
                    logger.info("Default configuration created&已创建默认配置")
            else:
                self._config = self._get_default_copy()
                self._save_to_file(self._config)
                logger.info("Default configuration created&已创建默认配置")
        except FileNotFoundError:
            self._config = self._get_default_copy()
            self._save_to_file(self._config)
            logger.info("Configuration file not found, created default&配置文件不存在，已创建默认配置")
        except Exception as e:
            logger.warning(f"Error loading configuration, using default&加载配置时出现问题，使用默认配置: {e}")
            self._config = self._get_default_copy()
            try:
                self._save_to_file(self._config)
            except Exception:
                pass

        return self._config

    def _save_to_file(self, config: dict) -> None:
        """Save configuration to file (internal)&保存配置到文件（内部方法）"""
        try:
            ss.write('config', config, file=SS_CONFIG_FILE)
        except Exception as e:
            logger.error(f"Failed to save configuration&保存配置失败: {e}")

    def save(self, config: dict) -> None:
        """Save configuration&保存配置"""
        try:
            ss.write('config', config, file=SS_CONFIG_FILE)
            self._config = config
            logger.info("Configuration saved&配置已保存")
        except Exception as e:
            logger.error(f"Failed to save configuration&保存配置失败: {e}")
            raise

    def _get_default_copy(self) -> dict:
        """Get a deep copy of default configuration&获取默认配置的深拷贝"""
        import copy
        return copy.deepcopy(self.DEFAULT_CONFIG)

    def _merge_with_defaults(self, stored: dict) -> dict:
        """Merge stored configuration with defaults&合并存储的配置与默认配置"""
        import copy
        result = copy.deepcopy(self.DEFAULT_CONFIG)
        for section, values in stored.items():
            if section in result and isinstance(values, dict):
                result[section].update(values)
            else:
                result[section] = values
        return result

    def get_default(self) -> dict:
        """Get default configuration&获取默认配置"""
        return self._get_default_copy()

    def is_first_run(self) -> bool:
        """Check if this is the first run&检查是否首次运行"""
        config = self.load()
        return config.get('general', {}).get('first_run', True)

    def set_first_run_complete(self):
        """Mark first run as complete&标记首次运行完成"""
        config = self.load()
        config['general']['first_run'] = False
        self.save(config)

    def get_last_session_files(self) -> list:
        """Get files from last session&获取上次会话的文件列表"""
        try:
            if ss.has('last_session_files', file=SS_SESSION_FILE):
                files = ss.read('last_session_files', file=SS_SESSION_FILE)
                return files if files else []
            return []
        except (FileNotFoundError, Exception):
            return []

    def save_session_files(self, files: list) -> None:
        """Save current session files&保存当前会话的文件列表"""
        try:
            ss.write('last_session_files', files, file=SS_SESSION_FILE)
        except Exception as e:
            logger.error(f"Failed to save session files&保存会话文件失败: {e}")

    def clear_session_files(self) -> None:
        """Clear session files&清除会话文件"""
        try:
            if ss.has('last_session_files', file=SS_SESSION_FILE):
                ss.remove('last_session_files', file=SS_SESSION_FILE)
        except (FileNotFoundError, Exception):
            pass


class StyleManager:
    """Style Manager&样式管理器"""

    FONT_MAPPING = {
        "DS-Digital.ttf": "DS-Digital/DS-DIGIB.TTF",
        "DS-Digital-Bold.ttf": "DS-Digital/DS-DIGIB.TTF",
        "DS-Digital-Italic.ttf": "DS-Digital/DS-DIGII.TTF",
        "Courier-Prime.ttf": "Courier_Prime/CourierPrime-Bold.ttf",
        "Courier-Prime-Bold.ttf": "Courier_Prime/CourierPrime-Bold.ttf",
        "Courier-Prime-Regular.ttf": "Courier_Prime/CourierPrime-Regular.ttf",
        "Roboto-Mono.ttf": "Roboto_Mono/static/RobotoMono-Regular.ttf",
        "Roboto-Mono-Bold.ttf": "Roboto_Mono/static/RobotoMono-Bold.ttf",
        "Roboto-Mono-Regular.ttf": "Roboto_Mono/static/RobotoMono-Regular.ttf",
        "Noto-Sans-SC.ttf": "Noto_Sans_SC/static/NotoSansSC-Regular.ttf",
        "Noto-Sans-SC-Bold.ttf": "Noto_Sans_SC/static/NotoSansSC-Bold.ttf",
    }

    def __init__(self, styles_dir: str | None = None, fonts_dir: str | None = None):
        base_path = get_base_path()
        self.styles_dir = Path(styles_dir) if styles_dir else base_path / "styles"
        self.fonts_dir = Path(fonts_dir) if fonts_dir else base_path / "fonts"
        self._styles_cache: dict = {}

    def list_styles(self) -> list[str]:
        """Get all available style names&获取所有可用样式名称列表"""
        styles = []
        if self.styles_dir.exists():
            for file in self.styles_dir.glob("*.yml"):
                styles.append(file.stem)
            for file in self.styles_dir.glob("*.yaml"):
                styles.append(file.stem)

        # Sort by brand priority&按品牌优先级排序
        brand_order = ["CANON&佳能", "NIKON&尼康", "FUJIFILM&富士", "PENTAX&宾得", 
                       "SONY&索尼", "PANASONIC&松下", "XIAOMI&小米"]
        
        sorted_styles = []
        for name in brand_order:
            if name in styles:
                sorted_styles.append(name)
        for name in styles:
            if name not in sorted_styles:
                sorted_styles.append(name)

        return sorted_styles

    def get_style_display_name(self, style_name: str) -> str:
        """Get localized display name for style&获取样式的本地化显示名称"""
        return L(style_name)

    def load_style(self, name: str) -> dict:
        """Load style configuration using simpsave&使用simpsave读取样式配置"""
        if name in self._styles_cache:
            return self._styles_cache[name]

        style_path = self.styles_dir / f"{name}.yml"
        if not style_path.exists():
            style_path = self.styles_dir / f"{name}.yaml"
        if not style_path.exists():
            raise FileNotFoundError(f"Style file not found&样式文件不存在: {name}")

        try:
            style = {
                "font": ss.read("font", file=str(style_path)),
                "color": ss.read("color", file=str(style_path)),
                "position": ss.read("position", file=str(style_path)),
                "format": ss.read("format", file=str(style_path)),
                "effects": ss.read("effects", file=str(style_path)),
            }
            self._styles_cache[name] = style
            return style
        except Exception as e:
            raise FileNotFoundError(f"Cannot read style from SimpSave&无法从SimpSave读取样式 [{name}]: {e}")
        
    def get_font_path(self, font_file: str) -> Path | None:
        """Get full path to font file&获取字体文件完整路径"""
        if font_file in self.FONT_MAPPING:
            mapped_path = self.fonts_dir / self.FONT_MAPPING[font_file]
            if mapped_path.exists():
                return mapped_path

        direct_path = self.fonts_dir / font_file
        if direct_path.exists():
            return direct_path

        for path in self.fonts_dir.rglob(f"*{Path(font_file).stem}*"):
            if path.suffix.lower() in ['.ttf', '.otf']:
                return path

        logger.warning(f"Font file not found, using system default&字体文件未找到，将使用系统默认字体: {font_file}")
        return None


class TimeExtractor:
    """Time Extractor&时间提取器"""

    def __init__(self, primary: str = "exif",
                 fallback_mode: str = "error",
                 custom_time: str = ""):
        self.primary = primary
        self.fallback_mode = fallback_mode
        self.custom_time = custom_time

    def extract(self, image_path: str | Path) -> datetime:
        """Extract time information from image&从图片提取时间信息"""
        image_path = Path(image_path)

        if self.primary == "exif":
            exif_time = self.get_exif_datetime(image_path)
            if exif_time:
                return exif_time

            # Handle fallback based on mode
            if self.fallback_mode == "error":
                raise ValueError(f"Cannot get EXIF time&无法获取EXIF时间: {image_path}")
            elif self.fallback_mode == "file_modified":
                logger.info(f"EXIF unavailable, using file modified time&EXIF时间不可用，使用文件修改时间: {image_path.name}")
                return self.get_file_datetime(image_path, "file_modified")
            elif self.fallback_mode == "file_created":
                logger.info(f"EXIF unavailable, using file created time&EXIF时间不可用，使用文件创建时间: {image_path.name}")
                return self.get_file_datetime(image_path, "file_created")
            elif self.fallback_mode == "custom":
                if self.custom_time:
                    try:
                        return datetime.strptime(self.custom_time, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            return datetime.strptime(self.custom_time, "%Y-%m-%d")
                        except ValueError:
                            raise ValueError(f"Invalid custom time format&无效的自定义时间格式: {self.custom_time}")
                raise ValueError(f"Custom time not set&未设置自定义时间")
            else:
                raise ValueError(f"Unknown fallback mode&未知的降级模式: {self.fallback_mode}")
        elif self.primary == "custom":
            if self.custom_time:
                try:
                    return datetime.strptime(self.custom_time, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        return datetime.strptime(self.custom_time, "%Y-%m-%d")
                    except ValueError:
                        raise ValueError(f"Invalid custom time format&无效的自定义时间格式: {self.custom_time}")
            raise ValueError(f"Custom time not set&未设置自定义时间")
        else:
            return self.get_file_datetime(image_path, self.primary)

    def get_exif_datetime(self, image_path: Path) -> datetime | None:
        """Read EXIF capture time&读取EXIF拍摄时间"""
        try:
            exif_dict = piexif.load(str(image_path))

            if piexif.ExifIFD.DateTimeOriginal in exif_dict.get("Exif", {}):
                dt_str = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal]
                if isinstance(dt_str, bytes):
                    dt_str = dt_str.decode('utf-8')
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")

            if piexif.ExifIFD.DateTimeDigitized in exif_dict.get("Exif", {}):
                dt_str = exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized]
                if isinstance(dt_str, bytes):
                    dt_str = dt_str.decode('utf-8')
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")

            if piexif.ImageIFD.DateTime in exif_dict.get("0th", {}):
                dt_str = exif_dict["0th"][piexif.ImageIFD.DateTime]
                if isinstance(dt_str, bytes):
                    dt_str = dt_str.decode('utf-8')
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")

            return None

        except Exception as e:
            logger.debug(f"Failed to read EXIF&读取EXIF失败 [{image_path.name}]: {e}")
            return None

    def get_file_datetime(self, image_path: Path, type_: str) -> datetime:
        """Read file time (modified/created)&读取文件时间（modified/created）"""
        stat = image_path.stat()

        if type_ == "file_modified":
            return datetime.fromtimestamp(stat.st_mtime)
        elif type_ == "file_created":
            if hasattr(stat, 'st_birthtime'):
                return datetime.fromtimestamp(stat.st_birthtime)
            return datetime.fromtimestamp(stat.st_ctime)
        else:
            raise ValueError(f"Unknown time type&未知的时间类型: {type_}")


class WatermarkRenderer:
    """Watermark Renderer&水印渲染器"""

    def __init__(self, style: dict, fonts_dir: Path):
        self.style = style or {}
        self.fonts_dir = fonts_dir
        self._font_cache: dict = {}

    def render(self, image: Image.Image, timestamp: datetime) -> Image.Image:
        """Render watermark on image and return new image&在图片上渲染水印并返回新图片"""
        if image.mode != 'RGB':
            image = image.convert('RGB')

        result = image.copy()
        draw = ImageDraw.Draw(result)

        font_size = self._calculate_font_size(image.size)
        font = self._get_font(font_size)

        text = self._format_timestamp(timestamp)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x, y = self._calculate_position(image.size, (text_width, text_height))

        effects = self.style.get('effects', {})
        if effects.get('shadow_enabled', True):
            shadow_color = self._parse_color(
                self.style.get('color', {}).get('shadow', '#000000'),
                effects.get('shadow_opacity', 0.3)
            )
            scale = font_size / 30
            offset_x = int(effects.get('shadow_offset_x', 2) * scale)
            offset_y = int(effects.get('shadow_offset_y', 2) * scale)
            draw.text((x + offset_x, y + offset_y), text, font=font, fill=shadow_color)

        text_color = self._parse_color(
            self.style.get('color', {}).get('text', '#FF6B35'),
            effects.get('opacity', 1.0)
        )
        draw.text((x, y), text, font=font, fill=text_color)

        return result

    def render_preview(self, image: Image.Image, timestamp: datetime,
                       preview_size: Tuple[int, int]) -> Image.Image:
        """Render thumbnail with watermark for preview&渲染用于预览的缩略图（带水印）"""
        watermarked = self.render(image, timestamp)

        img_ratio = watermarked.width / watermarked.height
        preview_ratio = preview_size[0] / preview_size[1]

        if img_ratio > preview_ratio:
            new_width = preview_size[0]
            new_height = int(new_width / img_ratio)
        else:
            new_height = preview_size[1]
            new_width = int(new_height * img_ratio)

        preview = watermarked.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return preview

    def _calculate_font_size(self, image_size: Tuple[int, int]) -> int:
        """Calculate font size based on image dimensions&根据图片尺寸计算字体大小"""
        short_edge = min(image_size)
        size_ratio = self.style.get('font', {}).get('size_ratio', 0.025)
        font_size = int(short_edge * size_ratio)
        return max(font_size, 12)

    def _calculate_position(self, image_size: Tuple[int, int],
                            text_size: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate watermark position coordinates&计算水印位置坐标"""
        width, height = image_size
        text_width, text_height = text_size

        position = self.style.get('position', {})
        anchor = position.get('anchor', 'bottom-right')
        margin_x = int(width * position.get('margin_x_ratio', 0.02))
        margin_y = int(height * position.get('margin_y_ratio', 0.02))

        if anchor == 'bottom-right':
            x = width - text_width - margin_x
            y = height - text_height - margin_y
        elif anchor == 'bottom-left':
            x = margin_x
            y = height - text_height - margin_y
        elif anchor == 'top-right':
            x = width - text_width - margin_x
            y = margin_y
        elif anchor == 'top-left':
            x = margin_x
            y = margin_y
        else:
            x = width - text_width - margin_x
            y = height - text_height - margin_y

        return (x, y)

    def _format_timestamp(self, timestamp: datetime) -> str:
        """Format timestamp to display text&格式化时间戳为显示文本"""
        format_config = self.style.get('format', {})
        pattern = format_config.get('date_pattern', '%y %m %d')
        prefix = format_config.get('prefix', '')
        suffix = format_config.get('suffix', '')
        formatted = timestamp.strftime(pattern)
        return f"{prefix}{formatted}{suffix}"

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font object&获取字体对象"""
        font_file = self.style.get('font', {}).get('file', 'Courier-Prime.ttf')
        cache_key = f"{font_file}_{size}"

        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font_path = StyleManager(fonts_dir=str(self.fonts_dir)).get_font_path(font_file)
        try:
            if font_path and font_path.exists():
                font = ImageFont.truetype(str(font_path), size)
            else:
                font = ImageFont.load_default()
                logger.warning(f"Using system default font instead of&使用系统默认字体替代: {font_file}")
        except Exception as e:
            logger.error(f"Failed to load font&加载字体失败: {e}")
            font = ImageFont.load_default()

        self._font_cache[cache_key] = font
        return font

    def _parse_color(self, color_str: str, opacity: float = 1.0) -> tuple:
        """Parse color string to RGBA tuple&解析颜色字符串为RGBA元组"""
        if color_str.startswith('#'):
            color_str = color_str[1:]

        if len(color_str) == 6:
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
        elif len(color_str) == 3:
            r = int(color_str[0], 16) * 17
            g = int(color_str[1], 16) * 17
            b = int(color_str[2], 16) * 17
        else:
            r, g, b = 255, 255, 255

        a = int(255 * opacity)
        return (r, g, b, a)


class ImageProcessor:
    """Image Processor&图片处理器"""

    def __init__(self, config: dict, style_manager: StyleManager):
        self.config = config
        self.style_manager = style_manager
        time_config = config.get('time_source', {})
        self.time_extractor = TimeExtractor(
            primary=time_config.get('primary', 'exif'),
            fallback_mode=time_config.get('fallback_mode', 'error'),
            custom_time=time_config.get('custom_time', '')
        )

    def process(self, input_path: str, style_name: str,
                output_path: str | None = None) -> bool:
        """Process single image&处理单张图片"""
        input_path = Path(input_path)

        try:
            style = self.style_manager.load_style(style_name)
            image = Image.open(input_path)
            timestamp = self.time_extractor.extract(input_path)

            renderer = WatermarkRenderer(style, self.style_manager.fonts_dir)
            result = renderer.render(image, timestamp)

            if output_path is None:
                output_path = self.generate_output_path(input_path, timestamp)
            output_path = Path(output_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.exists() and not self.config.get('output', {}).get('overwrite_existing', False):
                logger.warning(f"Output file exists, skipping&输出文件已存在，跳过: {output_path}")
                return False

            self._save_with_exif(result, input_path, output_path)

            logger.info(f"Processing complete&处理完成: {input_path.name} -> {output_path.name}")
            return True

        except Exception as e:
            logger.error(f"Processing failed&处理失败 [{input_path.name}]: {e}")
            raise

    def generate_output_path(self, input_path: Path, timestamp: datetime) -> Path:
        """Generate output path based on configuration&根据配置生成输出路径"""
        output_config = self.config.get('output', {})

        if output_config.get('same_directory', True):
            output_dir = input_path.parent
        else:
            custom_dir = output_config.get('custom_directory', '')
            if custom_dir:
                output_dir = Path(custom_dir)
            else:
                output_dir = input_path.parent

        pattern = output_config.get('filename_pattern', '{original}_stamped')
        original_stem = input_path.stem

        filename = pattern.format(
            original=original_stem,
            date=timestamp.strftime('%Y%m%d'),
            time=timestamp.strftime('%H%M%S'),
            index='001'
        )

        return output_dir / f"{filename}{input_path.suffix}"

    def _save_with_exif(self, image: Image.Image, original_path: Path,
                        output_path: Path) -> None:
        """Save image with EXIF handling&保存图片并处理EXIF"""
        output_config = self.config.get('output', {})
        quality = output_config.get('jpeg_quality', 95)
        preserve_exif = output_config.get('preserve_exif', True)

        save_kwargs = {
            'quality': quality,
            'optimize': True,
        }

        if preserve_exif:
            try:
                exif_dict = piexif.load(str(original_path))
                exif_bytes = piexif.dump(exif_dict)
                save_kwargs['exif'] = exif_bytes
            except Exception as e:
                logger.debug(f"Cannot preserve EXIF&无法保留EXIF: {e}")

        image.save(output_path, 'JPEG', **save_kwargs)


class BatchProcessor:
    """Batch Processing Engine&批量处理引擎"""

    def __init__(self, config: dict, style_manager: StyleManager):
        self.config = config
        self.style_manager = style_manager
        self._cancelled = False

    def process_batch(
            self,
            image_paths: list[str],
            style_name: str,
            progress_callback: Callable[[int, int, str], None] | None = None,
            preview_callback: Callable[[str, Image.Image], None] | None = None
    ) -> dict:
        """Batch process images&批量处理图片"""
        self._cancelled = False
        results = {
            "success": 0,
            "failed": 0,
            "errors": []
        }

        total = len(image_paths)
        processor = ImageProcessor(self.config, self.style_manager)

        try:
            style = self.style_manager.load_style(style_name)
        except Exception as e:
            results["errors"].append(f"Failed to load style&加载样式失败: {e}")
            raise Exception(f"Failed to load style&加载样式失败: {e}")

        for i, image_path in enumerate(image_paths):
            if self._cancelled:
                logger.info("Batch processing cancelled&批处理已取消")
                break

            image_path = Path(image_path)

            if progress_callback:
                progress_callback(i + 1, total, image_path.name)

            if preview_callback:
                try:
                    image = Image.open(image_path)
                    timestamp = processor.time_extractor.extract(image_path)
                    renderer = WatermarkRenderer(style, self.style_manager.fonts_dir)
                    preview = renderer.render_preview(image, timestamp, (3600, 2700))
                    preview_callback(str(image_path), preview)
                except Exception as e:
                    logger.debug(f"Failed to generate preview&生成预览失败: {e}")

            output_path = self._generate_indexed_output_path(
                processor, image_path, i + 1
            )

            try:
                success = processor.process(str(image_path), style_name, str(output_path))
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Processing failed&处理失败: {image_path.name}")
            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)
                results["errors"].append(f"{image_path.name}: {error_msg}")
                raise Exception(f"Processing failed&处理失败 [{image_path.name}]: {error_msg}")

        logger.info(f"Batch processing complete: success {results['success']}, failed {results['failed']}&批处理完成: 成功 {results['success']}, 失败 {results['failed']}")
        return results

    def cancel(self) -> None:
        """Cancel current batch processing&取消当前批处理"""
        self._cancelled = True
        logger.info("Cancelling batch processing...&正在取消批处理...")

    def _generate_indexed_output_path(self, processor: ImageProcessor,
                                      input_path: Path, index: int) -> Path:
        """Generate indexed output path&生成带序号的输出路径"""
        output_config = self.config.get('output', {})

        if output_config.get('same_directory', True):
            output_dir = input_path.parent
        else:
            custom_dir = output_config.get('custom_directory', '')
            output_dir = Path(custom_dir) if custom_dir else input_path.parent

        try:
            timestamp = processor.time_extractor.extract(input_path)
        except:
            timestamp = datetime.now()

        pattern = output_config.get('filename_pattern', '{original}_stamped')

        filename = pattern.format(
            original=input_path.stem,
            date=timestamp.strftime('%Y%m%d'),
            time=timestamp.strftime('%H%M%S'),
            index=f'{index:03d}'
        )

        return output_dir / f"{filename}{input_path.suffix}"


def scan_images(directory: str, recursive: bool = True) -> list[str]:
    """Scan directory for image files&扫描目录中的图片文件"""
    directory = Path(directory)
    extensions = {'.jpg', '.jpeg', '.JPG', '.JPEG'}
    images = []

    if recursive:
        for ext in extensions:
            images.extend(directory.rglob(f"*{ext}"))
    else:
        for ext in extensions:
            images.extend(directory.glob(f"*{ext}"))

    return [str(p) for p in sorted(images)]


def process_single_image(image_path: str, style_name: str = "CANON&佳能",
                         output_path: str | None = None) -> bool:
    """Convenience function to process single image&处理单张图片的便捷函数"""
    config_manager = ConfigManager()
    config = config_manager.load()
    style_manager = StyleManager()
    processor = ImageProcessor(config, style_manager)
    return processor.process(image_path, style_name, output_path)


if __name__ == "__main__":
    print("Photo-Timestamper Core Module")
    print("-" * 40)

    style_manager = StyleManager()
    styles = style_manager.list_styles()
    print(f"Available styles&可用样式: {styles}")

    config_manager = ConfigManager()
    config = config_manager.load()
    print(f"Configuration loaded&配置已加载")

    print("\nCore module test complete!&核心模块测试完成！")
    
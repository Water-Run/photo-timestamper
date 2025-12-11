"""
Photo-Timestamper 核心处理模块
"""

import os
import json
import logging
import configparser
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml
from PIL import Image, ImageDraw, ImageFont
import piexif

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('photo-timestamper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_base_path() -> Path:
    """获取程序基础路径"""
    return Path(__file__).parent.parent


class ConfigManager:
    """配置管理器 - 使用INI格式"""

    DEFAULT_CONFIG = {
        "general": {
            "recursive_scan": "true",
            "language": "",
            "first_run": "true"
        },
        "time_source": {
            "primary": "exif",
            "fallback_enabled": "true",
            "fallback_to": "file_modified"
        },
        "output": {
            "same_directory": "true",
            "custom_directory": "",
            "filename_pattern": "{original}_stamped",
            "jpeg_quality": "95",
            "preserve_exif": "true",
            "overwrite_existing": "false"
        },
        "ui": {
            "last_style": "佳能",
            "preview_enabled": "true",
            "window_geometry": ""
        }
    }

    def __init__(self, config_path: str | None = None):
        if config_path is None:
            self.config_path = get_base_path() / "config.ini"
        else:
            self.config_path = Path(config_path)
        self._config: configparser.ConfigParser | None = None

    def load(self) -> dict:
        """加载配置，不存在则返回默认配置"""
        if self._config is not None:
            return self._to_dict()

        self._config = configparser.ConfigParser()

        if self.config_path.exists():
            try:
                self._config.read(self.config_path, encoding='utf-8')
                self._merge_defaults()
                logger.info(f"配置文件已加载: {self.config_path}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                self._set_defaults()
        else:
            self._set_defaults()
            self._save_config()
            logger.info("已创建默认配置文件")

        return self._to_dict()

    def save(self, config: dict) -> None:
        """保存配置到文件"""
        try:
            if self._config is None:
                self._config = configparser.ConfigParser()

            for section, values in config.items():
                if not self._config.has_section(section):
                    self._config.add_section(section)
                for key, value in values.items():
                    self._config.set(section, key, str(value))

            self._save_config()
            logger.info("配置文件已保存")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise

    def _save_config(self):
        """写入配置文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self._config.write(f)

    def get_default(self) -> dict:
        """获取默认配置"""
        return {section: dict(values) for section, values in self.DEFAULT_CONFIG.items()}

    def _set_defaults(self):
        """设置默认配置"""
        for section, values in self.DEFAULT_CONFIG.items():
            if not self._config.has_section(section):
                self._config.add_section(section)
            for key, value in values.items():
                self._config.set(section, key, value)

    def _merge_defaults(self):
        """合并默认配置（添加缺失项）"""
        for section, values in self.DEFAULT_CONFIG.items():
            if not self._config.has_section(section):
                self._config.add_section(section)
            for key, value in values.items():
                if not self._config.has_option(section, key):
                    self._config.set(section, key, value)

    def _to_dict(self) -> dict:
        """转换为字典格式"""
        result = {}
        for section in self._config.sections():
            result[section] = {}
            for key, value in self._config.items(section):
                # 转换布尔值和数字
                if value.lower() in ('true', 'false'):
                    result[section][key] = value.lower() == 'true'
                elif value.isdigit():
                    result[section][key] = int(value)
                else:
                    result[section][key] = value
        return result

    def is_first_run(self) -> bool:
        """检查是否首次运行"""
        config = self.load()
        return config.get('general', {}).get('first_run', True)

    def set_first_run_complete(self):
        """标记首次运行完成"""
        config = self.load()
        config['general']['first_run'] = False
        self.save(config)


class StyleManager:
    """样式管理器"""

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
        """获取所有可用样式名称列表"""
        styles = []
        if self.styles_dir.exists():
            for file in self.styles_dir.glob("*.yml"):
                styles.append(file.stem)
            for file in self.styles_dir.glob("*.yaml"):
                styles.append(file.stem)

        brand_order = ["佳能", "尼康", "富士", "宾得", "索尼", "松下", "小米"]
        default_order = ["默认红", "默认黄", "默认绿", "默认蓝", "默认白", "默认灰"]

        sorted_styles = []
        for name in brand_order:
            if name in styles:
                sorted_styles.append(name)
        for name in default_order:
            if name in styles:
                sorted_styles.append(name)
        for name in styles:
            if name not in sorted_styles:
                sorted_styles.append(name)

        return sorted_styles

    def load_style(self, name: str) -> dict:
        """加载指定样式配置"""
        if name in self._styles_cache:
            return self._styles_cache[name]

        style_path = self.styles_dir / f"{name}.yml"
        if not style_path.exists():
            style_path = self.styles_dir / f"{name}.yaml"

        if not style_path.exists():
            raise FileNotFoundError(f"样式文件不存在: {name}")

        try:
            with open(style_path, 'r', encoding='utf-8') as f:
                style = yaml.safe_load(f)
            self._styles_cache[name] = style
            logger.info(f"已加载样式: {name}")
            return style
        except Exception as e:
            logger.error(f"加载样式失败 [{name}]: {e}")
            raise

    def get_font_path(self, font_file: str) -> Path | None:
        """获取字体文件完整路径"""
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

        logger.warning(f"字体文件未找到: {font_file}，将使用系统默认字体")
        return None


class TimeExtractor:
    """时间提取器"""

    def __init__(self, primary: str = "exif",
                 fallback_enabled: bool = True,
                 fallback_to: str = "file_modified"):
        self.primary = primary
        self.fallback_enabled = fallback_enabled
        self.fallback_to = fallback_to

    def extract(self, image_path: str | Path) -> datetime:
        """从图片提取时间信息"""
        image_path = Path(image_path)

        if self.primary == "exif":
            exif_time = self.get_exif_datetime(image_path)
            if exif_time:
                return exif_time

            if self.fallback_enabled:
                logger.info(f"EXIF时间不可用，降级使用{self.fallback_to}: {image_path.name}")
                return self.get_file_datetime(image_path, self.fallback_to)
            else:
                raise ValueError(f"无法获取EXIF时间且未启用降级: {image_path}")
        else:
            return self.get_file_datetime(image_path, self.primary)

    def get_exif_datetime(self, image_path: Path) -> datetime | None:
        """读取EXIF拍摄时间"""
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
            logger.debug(f"读取EXIF失败 [{image_path.name}]: {e}")
            return None

    def get_file_datetime(self, image_path: Path, type_: str) -> datetime:
        """读取文件时间（modified/created）"""
        stat = image_path.stat()

        if type_ == "file_modified":
            return datetime.fromtimestamp(stat.st_mtime)
        elif type_ == "file_created":
            if hasattr(stat, 'st_birthtime'):
                return datetime.fromtimestamp(stat.st_birthtime)
            return datetime.fromtimestamp(stat.st_ctime)
        else:
            raise ValueError(f"未知的时间类型: {type_}")


class WatermarkRenderer:
    """水印渲染器"""

    def __init__(self, style: dict, fonts_dir: Path):
        self.style = style
        self.fonts_dir = fonts_dir
        self._font_cache: dict = {}

    def render(self, image: Image.Image, timestamp: datetime) -> Image.Image:
        """在图片上渲染水印并返回新图片"""
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
                       preview_size: tuple[int, int]) -> Image.Image:
        """渲染用于预览的缩略图（带水印）"""
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

    def _calculate_font_size(self, image_size: tuple[int, int]) -> int:
        """根据图片尺寸计算字体大小"""
        short_edge = min(image_size)
        size_ratio = self.style.get('font', {}).get('size_ratio', 0.025)
        font_size = int(short_edge * size_ratio)
        return max(font_size, 12)

    def _calculate_position(self, image_size: tuple[int, int],
                            text_size: tuple[int, int]) -> tuple[int, int]:
        """计算水印位置坐标"""
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
        """格式化时间戳为显示文本"""
        format_config = self.style.get('format', {})
        pattern = format_config.get('date_pattern', '%y %m %d')
        prefix = format_config.get('prefix', '')
        suffix = format_config.get('suffix', '')

        formatted = timestamp.strftime(pattern)
        return f"{prefix}{formatted}{suffix}"

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """获取字体对象"""
        cache_key = f"{self.style.get('font', {}).get('file', '')}_{size}"

        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font_file = self.style.get('font', {}).get('file', 'Courier-Prime.ttf')
        font_path = StyleManager(fonts_dir=str(self.fonts_dir)).get_font_path(font_file)

        try:
            if font_path and font_path.exists():
                font = ImageFont.truetype(str(font_path), size)
            else:
                font = ImageFont.load_default()
                logger.warning(f"使用系统默认字体替代: {font_file}")
        except Exception as e:
            logger.error(f"加载字体失败: {e}")
            font = ImageFont.load_default()

        self._font_cache[cache_key] = font
        return font

    def _parse_color(self, color_str: str, opacity: float = 1.0) -> tuple:
        """解析颜色字符串为 RGBA 元组"""
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
    """图片处理器"""

    def __init__(self, config: dict, style_manager: StyleManager):
        self.config = config
        self.style_manager = style_manager
        self.time_extractor = TimeExtractor(
            primary=config.get('time_source', {}).get('primary', 'exif'),
            fallback_enabled=config.get('time_source', {}).get('fallback_enabled', True),
            fallback_to=config.get('time_source', {}).get('fallback_to', 'file_modified')
        )

    def process(self, input_path: str, style_name: str,
                output_path: str | None = None) -> bool:
        """处理单张图片"""
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
                logger.warning(f"输出文件已存在，跳过: {output_path}")
                return False

            self._save_with_exif(result, input_path, output_path)

            logger.info(f"处理完成: {input_path.name} -> {output_path.name}")
            return True

        except Exception as e:
            logger.error(f"处理失败 [{input_path.name}]: {e}")
            return False

    def generate_output_path(self, input_path: Path, timestamp: datetime) -> Path:
        """根据配置生成输出路径"""
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
        """保存图片并处理EXIF"""
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
                logger.debug(f"无法保留EXIF: {e}")

        image.save(output_path, 'JPEG', **save_kwargs)


class BatchProcessor:
    """批量处理引擎"""

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
        """批量处理图片"""
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
            results["errors"].append(f"加载样式失败: {e}")
            return results

        for i, image_path in enumerate(image_paths):
            if self._cancelled:
                logger.info("批处理已取消")
                break

            image_path = Path(image_path)

            if progress_callback:
                progress_callback(i + 1, total, image_path.name)

            if preview_callback:
                try:
                    image = Image.open(image_path)
                    timestamp = processor.time_extractor.extract(image_path)
                    renderer = WatermarkRenderer(style, self.style_manager.fonts_dir)
                    preview = renderer.render_preview(image, timestamp, (3600, 2700))  # 原来是 1200x900
                    preview_callback(str(image_path), preview)
                except Exception as e:
                    logger.debug(f"生成预览失败: {e}")

            output_path = self._generate_indexed_output_path(
                processor, image_path, i + 1
            )

            success = processor.process(str(image_path), style_name, str(output_path))

            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"处理失败: {image_path.name}")

        logger.info(f"批处理完成: 成功 {results['success']}, 失败 {results['failed']}")
        return results

    def cancel(self) -> None:
        """取消当前批处理"""
        self._cancelled = True
        logger.info("正在取消批处理...")

    def _generate_indexed_output_path(self, processor: ImageProcessor,
                                      input_path: Path, index: int) -> Path:
        """生成带序号的输出路径"""
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
    """扫描目录中的图片文件"""
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


def process_single_image(image_path: str, style_name: str = "佳能",
                         output_path: str | None = None) -> bool:
    """处理单张图片的便捷函数"""
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
    print(f"可用样式: {styles}")

    config_manager = ConfigManager()
    config = config_manager.load()
    print(f"配置已加载")

    print("\n核心模块测试完成！")
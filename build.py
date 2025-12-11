"""
PyInstaller 打包脚本
Photo-Timestamper Windows 桌面应用打包
"""

r"""python build.py""" # 执行打包

import PyInstaller.__main__
import os
import sys
import shutil
from pathlib import Path

# 项目路径
BASE_DIR = Path(__file__).parent
SOURCE_DIR = BASE_DIR / "source"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"

def clean():
    """清理旧的构建文件"""
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"已删除: {d}")
    
    # 清理 .spec 文件
    for spec_file in BASE_DIR.glob("*.spec"):
        spec_file.unlink()
        print(f"已删除: {spec_file}")
    
    print("清理完成\n")

def create_icon():
    """从 PNG 创建 ICO 图标"""
    try:
        from PIL import Image
    except ImportError:
        print("需要 Pillow 库来创建图标: pip install Pillow")
        return False
    
    png_path = BASE_DIR / "assets" / "logo.png"
    ico_path = BASE_DIR / "assets" / "logo.ico"
    
    if not png_path.exists():
        print(f"PNG 文件不存在: {png_path}")
        return False
    
    if ico_path.exists():
        print(f"ICO 图标已存在: {ico_path}")
        return True
    
    img = Image.open(png_path)
    
    # 确保是 RGBA 模式
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # 创建多尺寸图标
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"已创建图标: {ico_path}")
    return True

def build(onefile=False):
    """执行打包"""
    mode = "单文件" if onefile else "目录"
    
    print("=" * 50)
    print(f"Photo-Timestamper 打包脚本 ({mode}模式)")
    print("=" * 50)
    
    # 确保图标存在
    create_icon()
    
    # Windows 使用分号分隔
    separator = ";" if sys.platform == "win32" else ":"
    
    # 数据文件
    add_data = []
    
    fonts_dir = BASE_DIR / "fonts"
    if fonts_dir.exists():
        add_data.append(f"--add-data={fonts_dir}{separator}fonts")
    
    styles_dir = BASE_DIR / "styles"
    if styles_dir.exists():
        add_data.append(f"--add-data={styles_dir}{separator}styles")
    
    assets_dir = BASE_DIR / "assets"
    if assets_dir.exists():
        add_data.append(f"--add-data={assets_dir}{separator}assets")
    
    # 图标
    icon_path = BASE_DIR / "assets" / "logo.ico"
    icon_arg = [f"--icon={icon_path}"] if icon_path.exists() else []
    
    # PyInstaller 参数
    args = [
        str(SOURCE_DIR / "main.py"),
        "--name=PhotoTimestamper",
        "--windowed",
        "--onefile" if onefile else "--onedir",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        "--clean",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=PyQt6.sip",
        "--collect-all=PyQt6",
    ]
    
    args.extend(add_data)
    args.extend(icon_arg)
    
    print(f"\n入口文件: {SOURCE_DIR / 'main.py'}")
    if onefile:
        print(f"输出文件: {DIST_DIR / 'PhotoTimestamper.exe'}")
    else:
        print(f"输出目录: {DIST_DIR / 'PhotoTimestamper'}")
    print("\n开始打包，请稍候...\n")
    
    # 执行打包
    PyInstaller.__main__.run(args)
    
    print("\n" + "=" * 50)
    print("打包完成！")
    print("=" * 50)
    
    if onefile:
        exe_path = DIST_DIR / "PhotoTimestamper.exe"
        if exe_path.exists():
            size = exe_path.stat().st_size / 1024 / 1024
            print(f"\n程序位置: {exe_path}")
            print(f"文件大小: {size:.1f} MB")
    else:
        output_dir = DIST_DIR / "PhotoTimestamper"
        if output_dir.exists():
            total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
            print(f"\n程序位置: {output_dir / 'PhotoTimestamper.exe'}")
            print(f"总大小: {total_size / 1024 / 1024:.1f} MB")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Photo-Timestamper 打包工具")
    parser.add_argument("command", nargs="?", default="onefile",
                       choices=["build", "onefile", "clean", "icon"],
                       help="命令: onefile(默认单文件), build(目录模式), clean, icon")
    
    args = parser.parse_args()
    
    if args.command == "clean":
        clean()
    elif args.command == "icon":
        create_icon()
    elif args.command == "build":
        clean()
        build(onefile=False)
    else:  # onefile
        clean()
        build(onefile=True)

if __name__ == "__main__":
    main()
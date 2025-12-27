# build.py
"""
PyInstaller 打包脚本（目录模式 / onedir）
目标：
- 生成可扩展的目录结构
- styles/ 目录在输出目录下保持为独立目录，便于后续直接增删 yml 扩展
- 支持 QtWebEngine 的正确打包
- 根据平台生成对应的安装脚本和说明文件
- 最终封装到 photo-time-stamper(windows) 或 photo-time-stamper(linux) 目录
"""

r"""python build.py"""

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

import PyInstaller.__main__
import PyInstaller

# 项目路径
BASE_DIR = Path(__file__).parent
SOURCE_DIR = BASE_DIR / "source"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"

APP_NAME = "PhotoTimestamper"
ENTRY = SOURCE_DIR / "main.py"

# 判断当前平台
IS_WINDOWS = sys.platform.startswith("win")
PLATFORM_NAME = "windows" if IS_WINDOWS else "linux"

# 最终输出的封装目录名
PACKAGE_DIR_NAME = f"photo-time-stamper({PLATFORM_NAME})"

# 需要以"原样目录"形式保留在输出目录（exe 同级）
RUNTIME_DIRS = [
    ("styles", BASE_DIR / "styles"),
    ("fonts", BASE_DIR / "fonts"),
    ("assets", BASE_DIR / "assets"),
]

# 需要拷贝到输出目录（exe 同级）的文件
RUNTIME_FILES = [
    BASE_DIR / "config.ini",
    BASE_DIR / "config.json",
]

# Windows 安装脚本内容
INSTALL_BAT_CONTENT = r'''@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   Photo Timestamper 安装程序
echo ============================================
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\PhotoTimestamper"
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%PhotoTimestamper"

echo 正在安装到: %INSTALL_DIR%
echo.

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo 正在复制文件...
xcopy /E /I /Y "%APP_DIR%\*" "%INSTALL_DIR%\" >nul 2>&1
if errorlevel 1 (
    echo 复制文件失败！
    pause
    exit /b 1
)

echo 正在创建桌面快捷方式...
set "SHORTCUT=%USERPROFILE%\Desktop\Photo Timestamper.lnk"
set "VBS_TEMP=%TEMP%\create_shortcut.vbs"

(
echo Set oWS = WScript.CreateObject("WScript.Shell"^)
echo sLinkFile = "%SHORTCUT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile^)
echo oLink.TargetPath = "%INSTALL_DIR%\PhotoTimestamper.exe"
echo oLink.WorkingDirectory = "%INSTALL_DIR%"
echo oLink.Description = "Photo Timestamper - 照片时间戳工具"
echo oLink.IconLocation = "%INSTALL_DIR%\PhotoTimestamper.exe, 0"
echo oLink.Save
) > "%VBS_TEMP%"

cscript //nologo "%VBS_TEMP%"
del "%VBS_TEMP%" >nul 2>&1

echo 正在创建开始菜单快捷方式...
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "SHORTCUT_START=%START_MENU%\Photo Timestamper.lnk"

(
echo Set oWS = WScript.CreateObject("WScript.Shell"^)
echo sLinkFile = "%SHORTCUT_START%"
echo Set oLink = oWS.CreateShortcut(sLinkFile^)
echo oLink.TargetPath = "%INSTALL_DIR%\PhotoTimestamper.exe"
echo oLink.WorkingDirectory = "%INSTALL_DIR%"
echo oLink.Description = "Photo Timestamper - 照片时间戳工具"
echo oLink.IconLocation = "%INSTALL_DIR%\PhotoTimestamper.exe, 0"
echo oLink.Save
) > "%VBS_TEMP%"

cscript //nologo "%VBS_TEMP%"
del "%VBS_TEMP%" >nul 2>&1

echo.
echo ============================================
echo   安装完成！
echo ============================================
echo.
echo 程序已安装到: %INSTALL_DIR%
echo 桌面快捷方式已创建
echo 开始菜单快捷方式已创建
echo.
echo 按任意键退出...
pause >nul
'''

# Linux 安装脚本内容
INSTALL_SH_CONTENT = r'''#!/bin/bash
set -e

echo "============================================"
echo "  Photo Timestamper 安装程序"
echo "============================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/PhotoTimestamper"

INSTALL_DIR="$HOME/.local/share/PhotoTimestamper"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

echo "正在安装到: $INSTALL_DIR"
echo ""

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DIR"

echo "正在复制文件..."
cp -r "$APP_DIR"/* "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR/PhotoTimestamper"

echo "正在创建命令行链接..."
ln -sf "$INSTALL_DIR/PhotoTimestamper" "$BIN_DIR/photo-timestamper"

if [ -f "$INSTALL_DIR/assets/logo.png" ]; then
    echo "正在安装图标..."
    cp "$INSTALL_DIR/assets/logo.png" "$ICON_DIR/photo-timestamper.png"
fi

echo "正在创建桌面入口..."
cat > "$DESKTOP_DIR/photo-timestamper.desktop" << EOF
[Desktop Entry]
Name=Photo Timestamper
Comment=照片时间戳工具
Exec=$INSTALL_DIR/PhotoTimestamper
Icon=photo-timestamper
Terminal=false
Type=Application
Categories=Graphics;Photography;
StartupWMClass=PhotoTimestamper
EOF

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo ""
echo "============================================"
echo "  安装完成！"
echo "============================================"
echo ""
echo "程序已安装到: $INSTALL_DIR"
echo "命令行工具: photo-timestamper"
echo "桌面入口已创建"
echo ""
echo "请确保 $BIN_DIR 在您的 PATH 中"
echo ""
'''

# README 内容（通用：Windows / Linux）
README_COMMON_CONTENT = r'''photo-timestamper&照片时间水印添加器
Add camera OEM-style timestamp watermarks to photos.&为照片添加仿相机原厂风格的水印。

Windows installation: run install.bat&在Windows上安装: 运行install.bat
Linux installation: run install.sh&在Linux上安装: 运行install.sh

Developed with PyQt; QTWebEngine wraps the web interface; packaged as an executable with PyInstaller.&使用PyQT开发；QTWebEngine封装Web界面；PyInstaller打包为可执行文件。

----------------------------------------------------------------
by WaterRun&by WaterRun
GitHub: https://github.com/Water-Run/photo-timestamper&GitHub: https://github.com/Water-Run/photo-timestamper
'''

# README 内容（Windows）
README_WINDOWS_CONTENT = README_COMMON_CONTENT

# README 内容（Linux）
README_LINUX_CONTENT = README_COMMON_CONTENT


def _win_data_sep() -> str:
    return ";" if IS_WINDOWS else ":"


def _parse_version_tuple(v: str) -> tuple[int, int, int]:
    core = v.split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    nums = []
    for p in parts[:3]:
        try:
            nums.append(int("".join(ch for ch in p if ch.isdigit()) or "0"))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)  # type: ignore[return-value]


def clean(purge_spec: bool = False) -> None:
    """清理旧的构建产物。"""
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            print(f"已删除: {d}")

    if purge_spec:
        for spec_file in BASE_DIR.glob("*.spec"):
            try:
                spec_file.unlink()
                print(f"已删除: {spec_file}")
            except OSError:
                pass

    print("清理完成\n")


def create_icon() -> bool:
    """从 assets/logo.png 创建 assets/logo.ico。"""
    try:
        from PIL import Image
    except ImportError:
        print("警告: 需要 Pillow 库来创建图标")
        return False

    png_path = BASE_DIR / "assets" / "logo.png"
    ico_path = BASE_DIR / "assets" / "logo.ico"

    if not png_path.exists():
        print(f"警告: PNG 文件不存在: {png_path}")
        return False

    if ico_path.exists():
        return True

    img = Image.open(png_path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"已创建图标: {ico_path}")
    return True


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)


def _copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _ensure_external_runtime_layout(app_dir: Path) -> None:
    """确保 styles/fonts/assets 在 exe 同级。"""
    internal_dir = app_dir / "_internal"

    for name, src in RUNTIME_DIRS:
        dst = app_dir / name
        if src.exists():
            _copy_tree(src, dst)

    for f in RUNTIME_FILES:
        if f.exists():
            _copy_file(f, app_dir / f.name)

    if internal_dir.exists():
        for name, _src in RUNTIME_DIRS:
            internal_path = internal_dir / name
            if internal_path.exists() and not (app_dir / name).exists():
                _copy_tree(internal_path, app_dir / name)


def _get_pyqt6_webengine_binaries() -> list[tuple[str, str]]:
    """获取 PyQt6-WebEngine 相关的二进制文件路径。"""
    binaries = []
    
    try:
        import PyQt6
        pyqt6_path = Path(PyQt6.__file__).parent
        
        webengine_process_names = ["QtWebEngineProcess.exe", "QtWebEngineProcess"]
        
        for name in webengine_process_names:
            process_path = pyqt6_path / "Qt6" / "bin" / name
            if process_path.exists():
                binaries.append((str(process_path), "PyQt6/Qt6/bin"))
                break
            process_path = pyqt6_path / name
            if process_path.exists():
                binaries.append((str(process_path), "PyQt6"))
                break
        
        resources_dir = pyqt6_path / "Qt6" / "resources"
        if resources_dir.exists():
            for res_file in resources_dir.glob("*"):
                if res_file.is_file():
                    binaries.append((str(res_file), "PyQt6/Qt6/resources"))
        
        translations_dir = pyqt6_path / "Qt6" / "translations"
        if translations_dir.exists():
            for trans_file in translations_dir.glob("qtwebengine_*.qm"):
                binaries.append((str(trans_file), "PyQt6/Qt6/translations"))
                
    except ImportError:
        print("警告: 无法导入 PyQt6，跳过 WebEngine 二进制文件收集")
    except Exception as e:
        print(f"警告: 收集 WebEngine 二进制文件时出错: {e}")
    
    return binaries


def _fix_webengine_resources(app_dir: Path) -> None:
    """修复 WebEngine 资源文件的位置。"""
    try:
        import PyQt6
        pyqt6_src = Path(PyQt6.__file__).parent
        
        possible_pyqt6_dirs = [
            app_dir / "PyQt6",
            app_dir / "_internal" / "PyQt6",
        ]
        
        pyqt6_dst = None
        for p in possible_pyqt6_dirs:
            if p.exists():
                pyqt6_dst = p
                break
        
        if pyqt6_dst is None:
            pyqt6_dst = app_dir / "PyQt6"
            pyqt6_dst.mkdir(parents=True, exist_ok=True)
        
        qt6_src = pyqt6_src / "Qt6"
        qt6_dst = pyqt6_dst / "Qt6"
        
        if qt6_src.exists() and not qt6_dst.exists():
            print("复制 Qt6 目录...")
            for subdir in ["bin", "resources", "translations"]:
                src_sub = qt6_src / subdir
                dst_sub = qt6_dst / subdir
                if src_sub.exists():
                    _copy_tree(src_sub, dst_sub)
                    print(f"  已复制: {subdir}/")
        
        resources_dst = qt6_dst / "resources"
        resources_src = qt6_src / "resources"
        
        if resources_src.exists():
            resources_dst.mkdir(parents=True, exist_ok=True)
            for f in resources_src.glob("*"):
                dst_file = resources_dst / f.name
                if not dst_file.exists():
                    shutil.copy2(f, dst_file)
        
        print("WebEngine 资源文件已修复")
        
    except ImportError:
        print("警告: 无法导入 PyQt6，跳过 WebEngine 资源修复")
    except Exception as e:
        print(f"警告: 修复 WebEngine 资源时出错: {e}")


def _create_platform_files(package_dir: Path) -> None:
    """根据平台创建安装脚本和 README 文件。"""
    print("\n创建平台相关文件...")
    
    if IS_WINDOWS:
        # Windows: 创建 install.bat
        install_script = package_dir / "install.bat"
        install_script.write_text(INSTALL_BAT_CONTENT, encoding="utf-8")
        print(f"  已创建: install.bat")
        
        # Windows: 创建 README.txt
        readme_file = package_dir / "README.txt"
        readme_file.write_text(README_WINDOWS_CONTENT, encoding="utf-8-sig")
        print(f"  已创建: README.txt")
        
    else:
        # Linux: 创建 install.sh
        install_script = package_dir / "install.sh"
        install_script.write_text(INSTALL_SH_CONTENT, encoding="utf-8")
        install_script.chmod(install_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  已创建: install.sh")
        
        # Linux: 创建 README
        readme_file = package_dir / "README"
        readme_file.write_text(README_LINUX_CONTENT, encoding="utf-8")
        print(f"  已创建: README")


def _package_to_final_directory(app_dir: Path) -> Path:
    """将打包结果封装到最终目录。"""
    print("\n封装到最终目录...")
    
    final_dir = DIST_DIR / PACKAGE_DIR_NAME
    
    if final_dir.exists():
        shutil.rmtree(final_dir, ignore_errors=True)
    
    final_dir.mkdir(parents=True, exist_ok=True)
    
    final_app_dir = final_dir / APP_NAME
    shutil.move(str(app_dir), str(final_app_dir))
    print(f"  已移动: {APP_NAME}/ -> {PACKAGE_DIR_NAME}/{APP_NAME}/")
    
    _create_platform_files(final_dir)
    
    return final_dir


def build(*, clean_first: bool = True, purge_spec: bool = False, console: bool = False) -> None:
    """执行目录打包（onedir）。"""
    if clean_first:
        clean(purge_spec=purge_spec)

    if not ENTRY.exists():
        raise FileNotFoundError(f"入口文件不存在: {ENTRY}")

    print("=" * 60)
    print("Photo-Timestamper 打包脚本（目录模式 / onedir）")
    print(f"目标平台: {PLATFORM_NAME.upper()}")
    print("=" * 60)

    create_icon()

    sep = _win_data_sep()

    add_data_args: list[str] = []
    for name, src in RUNTIME_DIRS:
        if src.exists():
            add_data_args.append(f"--add-data={src}{sep}{name}")

    for f in RUNTIME_FILES:
        if f.exists():
            add_data_args.append(f"--add-data={f}{sep}.")

    add_binary_args: list[str] = []
    webengine_binaries = _get_pyqt6_webengine_binaries()
    for src_path, dest_dir in webengine_binaries:
        add_binary_args.append(f"--add-binary={src_path}{sep}{dest_dir}")
    
    if webengine_binaries:
        print(f"已收集 {len(webengine_binaries)} 个 WebEngine 相关文件")

    icon_path = BASE_DIR / "assets" / "logo.ico"
    icon_args = [f"--icon={icon_path}"] if icon_path.exists() else []

    pyi_ver = getattr(PyInstaller, "__version__", "0.0.0")
    use_contents_dir_dot = _parse_version_tuple(pyi_ver) >= (6, 9, 0)

    args = [
        str(ENTRY),
        f"--name={APP_NAME}",
        "--onedir",
        "--noconfirm",
        "--clean",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=PyQt6.sip",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtWebEngineWidgets",
        "--hidden-import=PyQt6.QtWebEngineCore",
        "--hidden-import=PyQt6.QtWebChannel",
        "--hidden-import=PyQt6.QtNetwork",
        "--hidden-import=PyQt6.QtPositioning",
        "--hidden-import=PyQt6.QtPrintSupport",
        "--hidden-import=yaml",
        "--hidden-import=piexif",
        "--hidden-import=simpsave",
        "--collect-all=PyQt6",
        "--collect-all=PyQt6_WebEngine",
    ]

    if console:
        args.append("--console")
    else:
        args.append("--windowed")

    if use_contents_dir_dot:
        args.append("--contents-directory=.")

    args.extend(add_data_args)
    args.extend(add_binary_args)
    args.extend(icon_args)

    print(f"\nPyInstaller 版本: {pyi_ver}")
    print(f"入口文件: {ENTRY}")
    print(f"输出目录: {DIST_DIR / PACKAGE_DIR_NAME}")
    print("\n开始打包...\n")

    PyInstaller.__main__.run(args)

    app_dir = DIST_DIR / APP_NAME
    if app_dir.exists():
        _ensure_external_runtime_layout(app_dir)
        _fix_webengine_resources(app_dir)
        
        final_dir = _package_to_final_directory(app_dir)
        final_app_dir = final_dir / APP_NAME

        exe_name = f"{APP_NAME}.exe" if IS_WINDOWS else APP_NAME
        exe_path = final_app_dir / exe_name
        
        print("\n" + "=" * 60)
        print("打包完成！")
        if exe_path.exists():
            total_size = sum(p.stat().st_size for p in final_dir.rglob("*") if p.is_file())
            print(f"程序位置: {exe_path}")
            print(f"总大小: {total_size / 1024 / 1024:.1f} MB")
            print(f"可扩展目录: {final_app_dir / 'styles'}")
            print(f"\n最终输出目录: {final_dir}")
            print(f"\n目录结构:")
            print(f"  {PACKAGE_DIR_NAME}/")
            print(f"    ├── {APP_NAME}/")
            print(f"    │   ├── {exe_name}")
            print(f"    │   ├── styles/")
            print(f"    │   ├── fonts/")
            print(f"    │   └── assets/")
            if IS_WINDOWS:
                print(f"    ├── install.bat")
                print(f"    └── README.txt")
            else:
                print(f"    ├── install.sh")
                print(f"    └── README")
        else:
            print(f"错误: 未找到输出文件: {exe_path}")
        print("=" * 60)
    else:
        print(f"\n错误: 打包目录不存在: {app_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Photo-Timestamper 打包工具")
    parser.add_argument(
        "command",
        nargs="?",
        default="build",
        choices=["build", "clean", "icon"],
        help="命令: build(默认), clean, icon",
    )
    parser.add_argument("--purge-spec", action="store_true", help="clean 时额外删除 *.spec")
    parser.add_argument("--no-clean", action="store_true", help="build 时不先清理")
    parser.add_argument("--console", action="store_true", help="使用控制台模式")

    args = parser.parse_args()

    if args.command == "clean":
        clean(purge_spec=args.purge_spec)
        return

    if args.command == "icon":
        create_icon()
        return

    build(clean_first=not args.no_clean, purge_spec=args.purge_spec, console=args.console)


if __name__ == "__main__":
    main()
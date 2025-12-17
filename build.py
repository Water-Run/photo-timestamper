# build.py
"""
PyInstaller 打包脚本（目录模式 / onedir）
目标：
- 不再生成单文件（onefile），而是生成可扩展的目录结构
- styles/ 目录在 dist/PhotoTimestamper/ 下保持为独立目录，便于后续直接增删 yml 扩展
"""

r"""python build.py"""  # 默认执行目录打包

import argparse
import os
import shutil
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

# 需要以“原样目录”形式保留在输出目录（exe 同级）
RUNTIME_DIRS = [
    ("styles", BASE_DIR / "styles"),
    ("fonts", BASE_DIR / "fonts"),
    ("assets", BASE_DIR / "assets"),
]

# 需要拷贝到输出目录（exe 同级）的可选文件
RUNTIME_FILES = [
    BASE_DIR / "config.ini",
    BASE_DIR / "config.json",
]


def _win_data_sep() -> str:
    # PyInstaller: Windows 用 ';'，其他平台用 ':'
    return ";" if sys.platform.startswith("win") else ":"


def _parse_version_tuple(v: str) -> tuple[int, int, int]:
    # 兼容如 "6.14.0" / "6.14.0.dev0" / "6.14"
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
    """清理旧的构建产物。默认不删除任何 .spec（避免误删你手写的 PhotoTimestamper.spec）。"""
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
    """从 assets/logo.png 创建 assets/logo.ico（若已存在则跳过）。"""
    try:
        from PIL import Image
    except ImportError:
        print("需要 Pillow 库来创建图标：pip install Pillow")
        return False

    png_path = BASE_DIR / "assets" / "logo.png"
    ico_path = BASE_DIR / "assets" / "logo.ico"

    if not png_path.exists():
        print(f"PNG 文件不存在: {png_path}")
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
    """
    保险措施：
    - PyInstaller 6.x 的 onedir 可能把内容放到 _internal/ 下（exe 同级只剩 exe）
    - 这里强制把 styles/fonts/assets 拷贝到 exe 同级，确保可直接扩展
    """
    internal_dir = app_dir / "_internal"

    # 1) 优先：从源码拷贝一份到 exe 同级（保证“原样目录”）
    for name, src in RUNTIME_DIRS:
        dst = app_dir / name
        if src.exists():
            _copy_tree(src, dst)

    for f in RUNTIME_FILES:
        _copy_file(f, app_dir / f.name)

    # 2) 如果 PyInstaller 把 datas 放进了 _internal，也再“提取/复制”一份出来（不依赖运行时路径）
    if internal_dir.exists():
        for name, _src in RUNTIME_DIRS:
            internal_path = internal_dir / name
            if internal_path.exists() and not (app_dir / name).exists():
                _copy_tree(internal_path, app_dir / name)


def build(*, clean_first: bool = True, purge_spec: bool = False, console: bool = False) -> None:
    """执行目录打包（onedir）。"""
    if clean_first:
        clean(purge_spec=purge_spec)

    if not ENTRY.exists():
        raise FileNotFoundError(f"入口文件不存在: {ENTRY}")

    print("=" * 60)
    print("Photo-Timestamper 打包脚本（目录模式 / onedir）")
    print("=" * 60)

    create_icon()

    sep = _win_data_sep()

    # 关键：数据目录保持为独立目录（exe 同级）
    add_data_args: list[str] = []
    for name, src in RUNTIME_DIRS:
        if src.exists():
            # dest_dir 用 name，保证输出目录出现 styles/ fonts/ assets/
            add_data_args.append(f"--add-data={src}{sep}{name}")

    # 可选：把配置文件也放到 exe 同级（便于发版后直接编辑）
    for f in RUNTIME_FILES:
        if f.exists():
            add_data_args.append(f"--add-data={f}{sep}.")

    icon_path = BASE_DIR / "assets" / "logo.ico"
    icon_args = [f"--icon={icon_path}"] if icon_path.exists() else []

    # PyInstaller 6.9+：onedir 默认把依赖放进 _internal；用 "." 回到旧布局（减少路径坑）
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
        "--collect-all=PyQt6",
    ]

    # 默认做 GUI（无控制台）；需要排错时可用 --console
    if console:
        args.append("--console")
    else:
        args.append("--windowed")

    if use_contents_dir_dot:
        args.append("--contents-directory=.")

    args.extend(add_data_args)
    args.extend(icon_args)

    print(f"\nPyInstaller 版本: {pyi_ver}")
    print(f"入口文件: {ENTRY}")
    print(f"输出目录: {DIST_DIR / APP_NAME}")
    print("\n开始打包...\n")

    PyInstaller.__main__.run(args)

    # 打包后确保 styles/fonts/assets 在 exe 同级（可直接增量扩展）
    app_dir = DIST_DIR / APP_NAME
    if app_dir.exists():
        _ensure_external_runtime_layout(app_dir)

    exe_path = (DIST_DIR / APP_NAME / f"{APP_NAME}.exe")
    print("\n" + "=" * 60)
    print("打包完成！")
    if exe_path.exists():
        total_size = sum(p.stat().st_size for p in (DIST_DIR / APP_NAME).rglob("*") if p.is_file())
        print(f"程序位置: {exe_path}")
        print(f"总大小: {total_size / 1024 / 1024:.1f} MB")
        print(f"可扩展目录: {(DIST_DIR / APP_NAME / 'styles')}")
    else:
        print(f"未找到输出 exe（请检查 PyInstaller 输出日志）: {exe_path}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Photo-Timestamper 打包工具（目录模式）")
    parser.add_argument(
        "command",
        nargs="?",
        default="build",
        choices=["build", "clean", "icon"],
        help="命令: build(默认), clean, icon",
    )
    parser.add_argument("--purge-spec", action="store_true", help="clean 时额外删除根目录 *.spec（谨慎）")
    parser.add_argument("--no-clean", action="store_true", help="build 时不先清理 dist/build")
    parser.add_argument("--console", action="store_true", help="使用控制台模式（便于排错；默认 windowed）")

    args = parser.parse_args()

    if args.command == "clean":
        clean(purge_spec=args.purge_spec)
        return

    if args.command == "icon":
        create_icon()
        return

    # build
    build(clean_first=not args.no_clean, purge_spec=args.purge_spec, console=args.console)


if __name__ == "__main__":
    main()

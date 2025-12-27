#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_DIR="/opt/PhotoTimestamper"

echo 'If you are using English, type "en" below to start the installation (case-insensitive). | 如果你使用的是英文, 在下方输入"zh"开始安装(不区分大小写)'
printf "|> "
read -r LANG
LANG="${LANG:0:2}"

if [[ "${LANG,,}" == "zh" ]]; then
  L_CHOOSE_DIR="请输入安装路径（回车使用默认路径）："
  L_DEFAULT="默认"
  L_NOT_EXIST="目录不存在，是否创建？(Y/N)："
  L_EXISTS_NOT_EMPTY="目录已存在且非空，是否覆盖？(Y/N)："
  L_ABORT="操作已取消。"
  L_COPY="正在复制文件..."
  L_COPY_OK="复制完成。"
  L_COPY_FAIL="复制失败，错误码："
  L_SHORTCUT="是否创建快捷方式（应用程序菜单 + 桌面）？(Y/N)："
  L_SHORTCUT_OK="快捷方式已创建。"
  L_SHORTCUT_FAIL="创建快捷方式时出错。"
  L_DONE="安装完成！"
  L_REMOVE_HINT="移除快捷方式：删除 ~/.local/share/applications/phototimestamper.desktop（以及桌面快捷方式）；卸载：删除安装目录即可。"
else
  L_CHOOSE_DIR="Enter installation path (press Enter to use default):"
  L_DEFAULT="Default"
  L_NOT_EXIST="Directory does not exist. Create it? (Y/N):"
  L_EXISTS_NOT_EMPTY="Directory exists and is not empty. Overwrite? (Y/N):"
  L_ABORT="Operation cancelled."
  L_COPY="Copying files..."
  L_COPY_OK="Copy finished."
  L_COPY_FAIL="Copy failed. Error code:"
  L_SHORTCUT="Create shortcuts (Applications menu + Desktop)? (Y/N):"
  L_SHORTCUT_OK="Shortcuts created."
  L_SHORTCUT_FAIL="Failed to create shortcuts."
  L_DONE="Installation complete!"
  L_REMOVE_HINT="Remove shortcuts: delete ~/.local/share/applications/phototimestamper.desktop (and the desktop shortcut); uninstall: delete the install directory."
fi

echo "$L_CHOOSE_DIR"
echo "[$L_DEFAULT: $DEFAULT_DIR]"
read -r TARGET_DIR
if [[ -z "$TARGET_DIR" ]]; then
  TARGET_DIR="$DEFAULT_DIR"
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  read -r -p "$L_NOT_EXIST" CREATE_OK
  if [[ ! "${CREATE_OK^^}" =~ ^Y$ ]]; then
    echo "$L_ABORT"
    exit 1
  fi
else
  if find "$TARGET_DIR" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
    read -r -p "$L_EXISTS_NOT_EMPTY" OVW
    if [[ ! "${OVW^^}" =~ ^Y$ ]]; then
      echo "$L_ABORT"
      exit 1
    fi
    rm -rf -- "$TARGET_DIR"
  fi
fi

mkdir -p -- "$TARGET_DIR"

echo "$L_COPY"
if ! cp -a "$SOURCE_DIR"/. "$TARGET_DIR"/ ; then
  echo "$L_COPY_FAIL $?"
  exit 1
fi
echo "$L_COPY_OK"

EXE="$TARGET_DIR/PhotoTimestamper"
if [[ ! -x "$EXE" && -f "$TARGET_DIR/PhotoTimestamper.exe" ]]; then
  EXE="$TARGET_DIR/PhotoTimestamper.exe"
fi
ICON_PNG="$TARGET_DIR/assets/logo.png"

read -r -p "$L_SHORTCUT" MKSC
if [[ "${MKSC^^}" =~ ^Y$ ]]; then
  DESKTOP_ENTRY="$HOME/.local/share/applications/phototimestamper.desktop"
  mkdir -p "$(dirname "$DESKTOP_ENTRY")"

  cat > "$DESKTOP_ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=PhotoTimestamper
Exec=$EXE
Icon=$ICON_PNG
Terminal=false
Categories=Utility;
EOF

  chmod +x "$DESKTOP_ENTRY"

  if [[ -d "$HOME/Desktop" ]]; then
    cp "$DESKTOP_ENTRY" "$HOME/Desktop/PhotoTimestamper.desktop"
    chmod +x "$HOME/Desktop/PhotoTimestamper.desktop"
  fi

  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" || true

  echo "$L_SHORTCUT_OK"
fi

echo
echo "$L_DONE"
echo "$L_REMOVE_HINT"
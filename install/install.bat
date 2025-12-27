@echo off
setlocal EnableDelayedExpansion

:: -----------------------------------------------------------------------------
:: PhotoTimestamper Windows installer
:: -----------------------------------------------------------------------------
set "SCRIPT_DIR=%~dp0"
set "SOURCE_DIR=%SCRIPT_DIR%.."
set "DEFAULT_DIR=%ProgramFiles%\PhotoTimestamper"

:: ---------------------- Language selection ----------------------
echo If you are using English, type "en" below to start the installation (case-insensitive).
echo 如果你使用的是中文, 在下方输入 "zh" 开始安装 (不区分大小写)
set /p LANG=^|^> 
set "LANG=%LANG:~0,2%"

if /i "%LANG%"=="zh" (
    set "L_MSG_CHOOSE_DIR=请输入安装路径（回车使用默认路径）："
    set "L_MSG_DEFAULT=默认路径"
    set "L_MSG_NOT_EXIST=目录不存在，是否创建？(Y/N)："
    set "L_MSG_EXISTS_NOT_EMPTY=目录已存在且非空，是否覆盖？(Y/N)："
    set "L_MSG_ABORT=操作已取消。"
    set "L_MSG_COPY=正在复制文件..."
    set "L_MSG_COPY_OK=复制完成。"
    set "L_MSG_COPY_FAIL=复制失败，错误码："
    set "L_MSG_SHORTCUT=是否创建快捷方式（开始菜单和桌面）？(Y/N)："
    set "L_MSG_SHORTCUT_OK=快捷方式已创建。"
    set "L_MSG_SHORTCUT_FAIL=创建快捷方式时出错。"
    set "L_MSG_DONE=安装完成！"
    set "L_MSG_REMOVE_HINT=卸载方法：删除安装目录；快捷方式请手动删除。"
) else (
    set "L_MSG_CHOOSE_DIR=Enter installation path (press Enter to use default):"
    set "L_MSG_DEFAULT=Default path"
    set "L_MSG_NOT_EXIST=Directory does not exist. Create it? (Y/N):"
    set "L_MSG_EXISTS_NOT_EMPTY=Directory exists and is not empty. Overwrite? (Y/N):"
    set "L_MSG_ABORT=Operation cancelled."
    set "L_MSG_COPY=Copying files..."
    set "L_MSG_COPY_OK=Copy finished."
    set "L_MSG_COPY_FAIL=Copy failed. Error code:"
    set "L_MSG_SHORTCUT=Create shortcuts (Start Menu and Desktop)? (Y/N):"
    set "L_MSG_SHORTCUT_OK=Shortcuts created."
    set "L_MSG_SHORTCUT_FAIL=Failed to create shortcuts."
    set "L_MSG_DONE=Installation complete!"
    set "L_MSG_REMOVE_HINT=To uninstall, delete the install directory; remove shortcuts manually."
)

:: ---------------------- Ask install path ----------------------
echo.
echo %L_MSG_CHOOSE_DIR%
echo %L_MSG_DEFAULT% ^> %DEFAULT_DIR%
set /p TARGET_DIR=

if "%TARGET_DIR%"=="" set "TARGET_DIR=%DEFAULT_DIR%"
if "%TARGET_DIR:~-1%"=="\" set "TARGET_DIR=%TARGET_DIR:~0,-1%"

:: ---------------------- Ensure directory state ----------------------
if not exist "%TARGET_DIR%" (
    set /p CREATE_OK=%L_MSG_NOT_EXIST%
    if /i "!CREATE_OK!" NEQ "Y" (
        echo %L_MSG_ABORT%
        goto :end
    )
) else (
    set "NONEMPTY="
    for /f %%A in ('dir /b "%TARGET_DIR%" 2^>nul') do (
        set "NONEMPTY=1"
        goto :checked
    )
:checked
    if defined NONEMPTY (
        set /p OVW=%L_MSG_EXISTS_NOT_EMPTY%
        if /i "!OVW!" NEQ "Y" (
            echo %L_MSG_ABORT%
            goto :end
        )
        rmdir /s /q "%TARGET_DIR%" 2>nul
    )
)

mkdir "%TARGET_DIR%" 2>nul

:: ---------------------- Copy files ----------------------
echo.
echo %L_MSG_COPY%

robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /R:2 /W:2 >nul
set "RC=%ERRORLEVEL%"

if %RC% GEQ 8 (
    echo %L_MSG_COPY_FAIL% %RC%
    goto :end
)

echo %L_MSG_COPY_OK%

:: ---------------------- Shortcuts ----------------------
set /p MKSC=%L_MSG_SHORTCUT%
if /i "%MKSC%"=="Y" (
    set "EXE=%TARGET_DIR%\PhotoTimestamper.exe"
    if not exist "%EXE%" set "EXE=%TARGET_DIR%\PhotoTimestamper"
    set "ICON=%TARGET_DIR%\assets\logo.ico"
    set "START_LNK=%ProgramData%\Microsoft\Windows\Start Menu\Programs\PhotoTimestamper.lnk"
    set "DESK_LNK=%Public%\Desktop\PhotoTimestamper.lnk"

    powershell -NoProfile -Command ^
      "$ws=New-Object -ComObject WScript.Shell;" ^
      "$s=$ws.CreateShortcut('%START_LNK%');" ^
      "$s.TargetPath='%EXE%';$s.WorkingDirectory='%TARGET_DIR%';" ^
      "if(Test-Path '%ICON%'){$s.IconLocation='%ICON%'};$s.Save();" ^
      "$d=$ws.CreateShortcut('%DESK_LNK%');" ^
      "$d.TargetPath='%EXE%';$d.WorkingDirectory='%TARGET_DIR%';" ^
      "if(Test-Path '%ICON%'){$d.IconLocation='%ICON%'};$d.Save();"

    if errorlevel 1 (
        echo %L_MSG_SHORTCUT_FAIL%
    ) else (
        echo %L_MSG_SHORTCUT_OK%
    )
)

:end
echo.
echo %L_MSG_DONE%
echo %L_MSG_REMOVE_HINT%
pause
exit /b
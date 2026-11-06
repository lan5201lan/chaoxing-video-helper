@echo off
chcp 65001 >nul
title 学习通刷课 - 一键启动
color 0A

echo ==============================================
echo        学习通刷课脚本 - 一键启动
echo ==============================================
echo.

rem 切换到脚本所在目录
cd /d "%~dp0"

rem ADB 路径：优先用 PATH 中的 adb，找不到再试相对路径
set "ADB=adb"
where adb >nul 2>&1
if errorlevel 1 (
    if exist "%~dp0..\tools\platform-tools\adb.exe" set "ADB=%~dp0..\tools\platform-tools\adb.exe"
)

rem Python 路径：优先用 PATH 中的 python
set "PY=python"
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python。请安装 Python 并勾选 "Add python.exe to PATH"，
    echo         或把本脚本的 PY 改成你的 python.exe 完整路径。
    pause
    exit /b 1
)

rem 检查 ADB 是否可用
"%ADB%" version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 ADB 工具。请安装 Android platform-tools 并加入 PATH。
    pause
    exit /b 1
)

echo [1/3] 检查手机连接...
"%ADB%" devices
echo.

rem 循环检测设备直到连上
:check_device
set "DEVICE_OK="
for /f "skip=1 tokens=2" %%a in ('"%ADB%" devices') do (
    if "%%a"=="device" set "DEVICE_OK=1"
)

if not defined DEVICE_OK (
    echo ==============================================
    echo   [警告] 未检测到已授权的手机！
    echo ==============================================
    echo   请检查：
    echo   1. 手机是否用 USB 线连接电脑
    echo   2. 是否已开启 USB 调试并点击"允许"
    echo   3. 手机上是否弹出授权窗口
    echo.
    echo   连好后按任意键重新检测；按 Ctrl+C 退出。
    echo.
    pause
    echo.
    goto :check_device
)

echo [2/3] 设备已连接，唤醒屏幕...
"%ADB%" shell input keyevent KEYCODE_WAKEUP >nul 2>&1

echo [3/3] 启动刷课脚本...
echo.
echo 提示：脚本运行期间请不要碰手机、不要拔数据线。
echo       如需停止，请关闭本窗口，或按 Ctrl+C。
echo.
echo ==============================================
echo.

"%PY%" main.py

echo.
echo ==============================================
echo   脚本已停止。
echo ==============================================
pause

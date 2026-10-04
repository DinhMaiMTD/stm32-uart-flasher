@echo off
setlocal enabledelayedexpansion
title Building STM32 Flasher Release
cd /d "%~dp0"

echo =====================================================================
echo                STM32 UART BOOTLOADER FLASHER BUILDER
echo              Packaging Standalone Executable (Zero-Dependency)
echo =====================================================================
echo.

:: 1. Verify Python is installed and accessible
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.10+ and make sure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

:: 2. Ensure required build dependencies are up to date
echo [1/4] Checking and installing required packages...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

:: 3. Ensure application icon exists
echo [2/4] Ensuring application icon is ready...
if not exist "%~dp0app_icon.ico" (
    python -c "from gui.app_icon import ensure_app_icon_ico; ensure_app_icon_ico('app_icon.ico')"
)

set "ICON_PARAM="
if exist "%~dp0app_icon.ico" (
    set "ICON_PARAM=--icon ""%~dp0app_icon.ico"""
)

:: Clean any previous temporary build cache before building
if exist "build" rmdir /s /q "build"

:: 4. Build standalone single-file windowed application with embedded icon
echo [3/4] Bundling application with PyInstaller (this may take 1-2 minutes)...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "STM32_UART_Flasher" ^
    %ICON_PARAM% ^
    --collect-all ttkbootstrap ^
    --collect-all intelhex ^
    --collect-all serial ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo =====================================================================
    echo [BUILD ERROR] PyInstaller failed to package the application.
    echo Please inspect the error messages above.
    echo =====================================================================
    pause
    exit /b %ERRORLEVEL%
)

:: 5. Clean up temporary build artifacts (leave only dist\ and app_icon.ico)
echo [4/4] Cleaning up temporary build cache...
if exist "build" rmdir /s /q "build"
if exist "STM32_UART_Flasher.spec" del /f /q "STM32_UART_Flasher.spec"
if exist "STM32_Flasher.spec" del /f /q "STM32_Flasher.spec"

echo.
echo =====================================================================
echo [BUILD SUCCESS] Standalone executable created successfully!
echo Executable: %~dp0dist\STM32_UART_Flasher.exe
echo.
echo You can copy STM32_UART_Flasher.exe to any Windows computer and run it
echo directly without installing Python or any libraries.
echo =====================================================================
echo.
pause


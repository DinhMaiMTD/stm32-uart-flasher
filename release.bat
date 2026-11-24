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
echo [1/3] Checking and installing required packages...
python -m pip install --quiet -r requirements.txt

:: 3. Clean previous build cache
if exist "build" rmdir /s /q "build"
if exist "dist\STM32_UART_Flasher.exe" del /f /q "dist\STM32_UART_Flasher.exe"

:: 4. Build ultra-slim standalone single-file windowed application
echo [2/3] Bundling application with PyInstaller...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --noupx ^
    --optimize 2 ^
    --name "STM32_UART_Flasher" ^
    --icon "%~dp0app_icon.ico" ^
    --add-data "%~dp0app_icon.ico;." ^
    --exclude-module PIL ^
    --exclude-module ttkbootstrap ^
    --exclude-module intelhex ^
    --exclude-module numpy ^
    --exclude-module ssl ^
    --exclude-module _ssl ^
    --exclude-module sqlite3 ^
    --exclude-module _sqlite3 ^
    --exclude-module bz2 ^
    --exclude-module _bz2 ^
    --exclude-module lzma ^
    --exclude-module _lzma ^
    --exclude-module decimal ^
    --exclude-module _decimal ^
    --exclude-module xml ^
    --exclude-module xmlrpc ^
    --exclude-module html ^
    --exclude-module http ^
    --exclude-module email ^
    --exclude-module unittest ^
    --exclude-module pydoc ^
    --exclude-module doctest ^
    --exclude-module pdb ^
    --exclude-module asyncio ^
    --exclude-module _overlapped ^
    --exclude-module multiprocessing ^
    --exclude-module concurrent ^
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

:: 5. Clean up temporary build artifacts
echo [3/3] Cleaning up temporary build cache...
if exist "build" rmdir /s /q "build"
if exist "STM32_UART_Flasher.spec" del /f /q "STM32_UART_Flasher.spec"

echo.
echo =====================================================================
echo [BUILD SUCCESS] Standalone executable created successfully!
echo Executable: %~dp0dist\STM32_UART_Flasher.exe
echo =====================================================================
echo.
pause

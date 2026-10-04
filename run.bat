@echo off
title STM32 UART Bootloader Flasher
cd /d "%~dp0"
echo Starting STM32 UART Bootloader Flasher...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] An error occurred while launching STM32 Flasher!
    pause
)


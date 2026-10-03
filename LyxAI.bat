@echo off
REM ============================================================
REM  LyX AI Agent — Windows Launcher
REM  Compatible with CMD and PowerShell
REM ============================================================
cd /d "%~dp0"

REM Prefer pythonw (no console window) if available
SET PYTHONW=%~dp0.venv\Scripts\pythonw.exe
SET PYTHON=%~dp0.venv\Scripts\python.exe

IF EXIST "%PYTHONW%" (
    start "" "%PYTHONW%" "%~dp0main.py"
) ELSE IF EXIST "%PYTHON%" (
    start "" "%PYTHON%" "%~dp0main.py"
) ELSE (
    echo [ERROR] Virtual environment not found.
    echo Please run install_windows.ps1 first.
    pause
)

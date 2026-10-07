@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
if exist "venv\Scripts\python.exe" set "PYTHON_CMD=venv\Scripts\python.exe"
if not defined PYTHON_CMD (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo [ERROR] Python not found. Run setup.bat or install Python 3.10+.
    exit /b 1
)

%PYTHON_CMD% scripts\cli.py %*
exit /b %ERRORLEVEL%

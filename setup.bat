@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

echo.
echo ================================================================
echo   My Bookshelves -- Setup
echo ================================================================
echo.

echo [1/5] Checking Python...
set "SYSTEM_PYTHON="
python --version >nul 2>&1
if not errorlevel 1 set "SYSTEM_PYTHON=python"
if not defined SYSTEM_PYTHON (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "SYSTEM_PYTHON=py -3"
)
if not defined SYSTEM_PYTHON (
    echo    [ERROR] Python not found! Please install Python 3.10+
    echo            https://www.python.org/downloads/
    exit /b 1
)
%SYSTEM_PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo    [ERROR] Python 3.10+ is required. Please install a newer Python.
    echo            https://www.python.org/downloads/
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('%SYSTEM_PYTHON% --version 2^>^&1') do (
    echo    [OK] Python %%v detected
)

echo.
echo [2/5] Creating virtual environment and upgrading Python dependencies...
if not exist "venv\Scripts\python.exe" (
    %SYSTEM_PYTHON% -m venv venv
    if errorlevel 1 (
        echo    [ERROR] Failed to create virtual environment
        exit /b 1
    )
)
set "PYTHON_CMD=venv\Scripts\python.exe"

"%PYTHON_CMD%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo    [WARN] Existing venv has a broken pip install. Recreating venv...
    rmdir /s /q venv
    %SYSTEM_PYTHON% -m venv venv
    if errorlevel 1 (
        echo    [ERROR] Failed to recreate virtual environment
        exit /b 1
    )
)

"%PYTHON_CMD%" -c "import pathlib, site, sys; sys.exit(0 if any(path.name.lower().startswith('~ip') for root in site.getsitepackages() for path in pathlib.Path(root).glob('~ip*')) else 1)" >nul 2>&1
if not errorlevel 1 (
    echo    [WARN] Existing venv has a partial pip upgrade. Recreating venv...
    rmdir /s /q venv
    %SYSTEM_PYTHON% -m venv venv
    if errorlevel 1 (
        echo    [ERROR] Failed to recreate virtual environment
        exit /b 1
    )
)

"%PYTHON_CMD%" -X utf8 -m pip install --upgrade --upgrade-strategy eager --disable-pip-version-check --no-cache-dir -r requirements-dev.txt
if errorlevel 1 (
    echo    [ERROR] Failed to install or upgrade dependencies
    exit /b 1
)
echo    [OK] All dependencies installed or upgraded
echo    [HINT] Add %CD% to your PATH to run "bookshelves" from anywhere

echo.
echo [3/5] Creating project directories...
if not exist "Books\" mkdir Books
if not exist "Inbox\" mkdir Inbox
if not exist "assets\covers\" mkdir assets\covers
echo    [OK] Books/  Inbox/  assets/covers/

echo.
echo [4/5] Verifying setup...
"%PYTHON_CMD%" -c "import fitz; print('    [OK] PyMuPDF', fitz.version[0])"
if errorlevel 1 echo    [FAIL] PyMuPDF not working
"%PYTHON_CMD%" -c "from PIL import Image; print('    [OK] Pillow', Image.__version__)"
if errorlevel 1 echo    [FAIL] Pillow not working
"%PYTHON_CMD%" -c "import docx; print('    [OK] python-docx')"
if errorlevel 1 echo    [FAIL] python-docx not working

echo.
echo [5/5] Running repo doctor...
if /I "%~1"=="--reset-sample-data" (
    echo    [WARN] Resetting sample data because --reset-sample-data was provided
    "%PYTHON_CMD%" scripts\reset_library.py --execute --yes
) else (
    echo    [OK] Skipping reset. Existing library data is preserved.
)
"%PYTHON_CMD%" scripts\cli.py doctor --base-dir .

echo.
echo ================================================================
echo   Setup complete!
echo ================================================================
echo.
echo   View locally:
echo     cd web ^&^& npm run dev
echo     Open http://localhost:5173/bookshelves/
echo.
echo   Add books:
echo     1. Drop files into Inbox/
echo     2. Run bookshelves, pick Auto-Organize
echo.
echo   Shortcuts:
echo     bookshelves            ^(TUI, cmd.exe or repo dir on PATH^)
echo     .\bookshelves.bat      ^(PowerShell from repo root^)
echo     bookshelves doctor
echo.
echo ================================================================
echo.

endlocal

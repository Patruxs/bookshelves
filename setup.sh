#!/usr/bin/env bash

set -e
cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  📚 ${BOLD}My Bookshelves — Setup${NC}                         ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "[1/5] 🐍 Checking Python..."

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "   ${RED}❌ Python not found! Please install Python 3.10+${NC}"
    echo "      https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
if ! "$PYTHON_CMD" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo -e "   ${RED}❌ $PYTHON_CMD $PYTHON_VERSION is too old. Please install Python 3.10+${NC}"
    echo "      https://www.python.org/downloads/"
    exit 1
fi
echo -e "   ${GREEN}✅ $PYTHON_CMD $PYTHON_VERSION detected${NC}"

is_windows_shell() {
    [ "${OS:-}" = "Windows_NT" ] || uname -s 2>/dev/null | grep -Eq '^(MINGW|MSYS|CYGWIN)'
}

find_venv_python() {
    if [ -x "venv/bin/python" ]; then
        echo "venv/bin/python"
        return 0
    fi

    if ! is_windows_shell; then
        return 1
    fi

    if [ -x "venv/Scripts/python.exe" ]; then
        echo "venv/Scripts/python.exe"
        return 0
    fi

    if [ -x "venv/Scripts/python" ]; then
        echo "venv/Scripts/python"
        return 0
    fi

    return 1
}

venv_has_broken_pip() {
    if ! "$PYTHON_CMD" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    if "$PYTHON_CMD" -c "import pathlib, site, sys; sys.exit(0 if any(path.name.lower().startswith('~ip') for root in site.getsitepackages() for path in pathlib.Path(root).glob('~ip*')) else 1)" >/dev/null 2>&1; then
        return 0
    fi

    return 1
}

create_venv() {
    VENV_EXISTED="false"
    if [ -d "venv" ]; then
        VENV_EXISTED="true"
    fi

    if ! "$1" -m venv venv; then
        echo -e "   ${RED}❌ Failed to create virtual environment${NC}"
        echo "      If you are on Ubuntu/WSL, install python3-venv and rerun setup."
        echo "      If you are on Windows Git Bash, make sure Windows Python is on PATH or run setup.bat."
        if [ "$VENV_EXISTED" = "false" ] && [ -d "venv" ]; then
            rm -rf venv
        fi
        exit 1
    fi

    if ! VENV_PYTHON="$(find_venv_python)"; then
        echo -e "   ${RED}❌ Virtual environment was created, but its Python executable was not found${NC}"
        echo "      Expected one of: venv/bin/python, venv/Scripts/python.exe"
        exit 1
    fi
}

echo ""
echo -e "[2/5] 📥 Creating virtual environment and upgrading Python dependencies..."

SYSTEM_PYTHON_CMD="$PYTHON_CMD"
if ! VENV_PYTHON="$(find_venv_python)"; then
    if [ -d "venv" ] && ! is_windows_shell; then
        echo -e "   ${YELLOW}⚠️  venv/ was built for another OS (no venv/bin/python). Recreating venv...${NC}"
        rm -rf venv
    fi
    create_venv "$SYSTEM_PYTHON_CMD"
fi
PYTHON_CMD="$VENV_PYTHON"

echo "   Using $PYTHON_CMD"
if venv_has_broken_pip; then
    echo -e "   ${YELLOW}⚠️  Existing venv has a broken pip install. Recreating venv...${NC}"
    rm -rf venv
    create_venv "$SYSTEM_PYTHON_CMD"
    PYTHON_CMD="$VENV_PYTHON"
    echo "   Using $PYTHON_CMD"
fi

echo "   Installing or upgrading requirements..."
if ! "$PYTHON_CMD" -X utf8 -m pip install --upgrade --upgrade-strategy eager --disable-pip-version-check --no-cache-dir -r requirements-dev.txt; then
    echo -e "   ${RED}❌ Failed to install or upgrade dependencies${NC}"
    exit 1
fi
echo -e "   ${GREEN}✅ All dependencies installed or upgraded${NC}"

BOOKSHELVES_LINK="$HOME/.local/bin/bookshelves"
if ! is_windows_shell; then
    if [ -e "$BOOKSHELVES_LINK" ] && [ ! -L "$BOOKSHELVES_LINK" ]; then
        echo -e "   ${YELLOW}⚠️  $BOOKSHELVES_LINK exists and is not a symlink; left untouched${NC}"
    elif mkdir -p "$HOME/.local/bin" && ln -sf "$ROOT_DIR/bookshelves" "$BOOKSHELVES_LINK"; then
        echo -e "   ${GREEN}✅ Linked $BOOKSHELVES_LINK → $ROOT_DIR/bookshelves${NC}"
        case ":$PATH:" in
            *":$HOME/.local/bin:"*) ;;
            *) echo -e "   ${YELLOW}⚠️  Add ~/.local/bin to PATH to run 'bookshelves' from anywhere${NC}" ;;
        esac
    else
        echo -e "   ${YELLOW}⚠️  Could not link $BOOKSHELVES_LINK; run ./bookshelves from the repo instead${NC}"
    fi
fi

echo ""
echo -e "[3/5] 📁 Creating project directories..."

mkdir -p Books Inbox data assets/covers
echo -e "   ${GREEN}✅ Books/  Inbox/  assets/covers/${NC}"

echo ""
echo -e "[4/5] ✅ Verifying setup..."

if PYMUPDF_VERSION=$("$PYTHON_CMD" -c "import fitz; print(fitz.version[0])" 2>/dev/null); then
    echo -e "   ${GREEN}✅ PyMuPDF $PYMUPDF_VERSION${NC}"
else
    echo -e "   ${RED}❌ PyMuPDF not working${NC}"
fi

if PILLOW_VERSION=$("$PYTHON_CMD" -c "from PIL import Image; print(Image.__version__)" 2>/dev/null); then
    echo -e "   ${GREEN}✅ Pillow $PILLOW_VERSION${NC}"
else
    echo -e "   ${RED}❌ Pillow not working${NC}"
fi

if "$PYTHON_CMD" -c "import docx" 2>/dev/null; then
    echo -e "   ${GREEN}✅ python-docx${NC}"
else
    echo -e "   ${RED}❌ python-docx not working${NC}"
fi

echo ""
echo -e "[5/5] 🩺 Running repo doctor..."
if [ "${1:-}" = "--reset-sample-data" ]; then
    echo -e "   ${YELLOW}⚠️  Resetting sample data because --reset-sample-data was provided${NC}"
    "$PYTHON_CMD" scripts/reset_library.py --execute --yes
else
    echo -e "   ${GREEN}✅ Skipping reset. Existing library data is preserved.${NC}"
fi
if ! "$PYTHON_CMD" scripts/cli.py doctor --base-dir .; then
    echo -e "   ${YELLOW}⚠️  Doctor reported problems (see above). Setup itself finished.${NC}"
fi

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  🎉 ${BOLD}Setup complete!${NC}                                ${CYAN}║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║${NC}                                                     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  View locally:                                      ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    cd web && npm run dev                            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    → http://localhost:5173/bookshelves/           ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  Add books:                                         ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    1. Drop files into Inbox/                        ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    2. Run bookshelves, pick Auto-Organize           ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  Shortcuts:                                         ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    bookshelves          (TUI)                       ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    bookshelves doctor                               ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                     ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

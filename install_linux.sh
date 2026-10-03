#!/usr/bin/env bash
# ============================================================
#  LyX AI Agent — Linux Installer (Debian 12 / 13)
#  Usage:  chmod +x install_linux.sh && ./install_linux.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
ICON_PNG="$SCRIPT_DIR/assets/logo-lyx-ai.png"
DESKTOP_FILE="$HOME/.local/share/applications/lyx-ai-agent.desktop"
LAUNCHER="$HOME/.local/bin/lyx-ai-agent"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       LyX AI Agent — Linux Installer         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: Check Python 3.10+ ─────────────────────────────────────────────
echo -e "${YELLOW}▶  Checking Python...${NC}"

PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            echo -e "   ${GREEN}✓ Found: $cmd ($VER)${NC}"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}   ✗ Python 3.10+ not found.${NC}"
    echo "   Installing python3 via apt..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv
    PYTHON_CMD="python3"
fi

# ── Step 2: Ensure tkinter is installed ────────────────────────────────────
echo -e "${YELLOW}▶  Checking tkinter...${NC}"
if ! "$PYTHON_CMD" -c "import tkinter" &>/dev/null; then
    echo "   Installing python3-tk..."
    sudo apt-get install -y python3-tk
fi
echo -e "   ${GREEN}✓ tkinter OK${NC}"

# ── Step 3: Create virtual environment ─────────────────────────────────────
echo -e "${YELLOW}▶  Creating virtual environment (.venv)...${NC}"
if [ -d "$VENV_DIR" ]; then
    echo -e "   ℹ  .venv already exists — skipping."
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo -e "   ${GREEN}✓ Virtual environment created.${NC}"
fi

# ── Step 4: Install dependencies ───────────────────────────────────────────
echo -e "${YELLOW}▶  Installing dependencies (this may take a minute)...${NC}"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
echo -e "   ${GREEN}✓ Dependencies installed.${NC}"

# ── Step 5: Create launcher script ─────────────────────────────────────────
echo -e "${YELLOW}▶  Creating launcher script...${NC}"
mkdir -p "$(dirname "$LAUNCHER")"
cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
# LyX AI Agent launcher
cd "$SCRIPT_DIR"
exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"
echo -e "   ${GREEN}✓ Launcher: $LAUNCHER${NC}"

# ── Step 6: Create .desktop entry ──────────────────────────────────────────
echo -e "${YELLOW}▶  Creating application menu entry...${NC}"
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=LyX AI Agent
Comment=LaTeX / LyX document assistant powered by AI
Exec=$LAUNCHER
Icon=$ICON_PNG
Terminal=false
Type=Application
Categories=Office;Science;Education;
Keywords=latex;lyx;ai;assistant;document;
StartupWMClass=lyx-ai-agent
EOF
chmod +x "$DESKTOP_FILE"

# Refresh desktop database if available
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
fi
echo -e "   ${GREEN}✓ Desktop entry created.${NC}"

# ── Done ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✓  Installation complete!                ║${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}║  → Run:  lyx-ai-agent                       ║${NC}"
echo -e "${GREEN}║  → Or open from your application menu       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""

read -rp "Launch LyX AI Agent now? (y/N): " LAUNCH
if [[ "$LAUNCH" =~ ^[Yy]$ ]]; then
    nohup "$LAUNCHER" &>/dev/null &
    echo "Launched!"
fi

#!/usr/bin/env bash
set -euo pipefail

# ─── OpenSS Installer ───
# One-liner: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Mide6x/OpenSS/main/install.sh)"

echo ""
echo "  ● OpenSS Installer"
echo "  ─────────────────────"
echo ""

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
  echo "  ✗ OpenSS requires macOS. Exiting."
  exit 1
fi

# Check Python 3
if ! command -v python3 &>/dev/null; then
  echo "  ✗ python3 not found. Install Python 3.10+ first."
  exit 1
fi

INSTALL_DIR="$HOME/.openss"

# Clone or update
if [ -d "$INSTALL_DIR" ]; then
  echo "  → Updating existing installation..."
  cd "$INSTALL_DIR"
  git pull --quiet origin main
else
  echo "  → Cloning OpenSS..."
  git clone --quiet https://github.com/Mide6x/OpenSS.git "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

# Virtual environment
if [ ! -d "venv" ]; then
  echo "  → Creating virtual environment..."
  python3 -m venv venv
fi

echo "  → Installing dependencies..."
./venv/bin/pip install -q -r requirements.txt

# Symlink
mkdir -p "$HOME/bin"
ln -sf "$INSTALL_DIR/openssmide" "$HOME/bin/openssmide"

# Check PATH
if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
  echo ""
  echo "  ⚠ ~/bin is not in your PATH."
  echo "  Add this to your ~/.zshrc (or ~/.bashrc):"
  echo ""
  echo "    export PATH=\"\$HOME/bin:\$PATH\""
  echo ""
fi

echo ""
echo "  ✓ OpenSS installed successfully!"
echo "  Run: openssmide"
echo ""

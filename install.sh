#!/usr/bin/env sh
# DiskAGI (`dagi`) — Frontier at home · OMP Harness Installer (Linux & macOS)
# Usage:
#   curl -fsSL https://bryonhigbee.github.io/install.sh | sh
set -eu

INSTALL_DIR="${DISKAGI_INSTALL_DIR:-$HOME/.local/bin}"
SHARE_DIR="${DISKAGI_SHARE_DIR:-$HOME/.local/share/diskagi}"
CONFIG_DIR="${DISKAGI_CONFIG_DIR:-$HOME/.config/diskagi}"

mkdir -p "$INSTALL_DIR" "$SHARE_DIR" "$CONFIG_DIR"

if [ -f "/home/bryonh/Documents/DiskNCM/diskagi-cli/diskagi.py" ]; then
    cp "/home/bryonh/Documents/DiskNCM/diskagi-cli/diskagi.py" "$SHARE_DIR/dagi.py"
else
    curl -fsSL "https://bryonhigbee.github.io/dagi.py" -o "$SHARE_DIR/dagi.py"
fi

chmod +x "$SHARE_DIR/dagi.py"
ln -sf "$SHARE_DIR/dagi.py" "$INSTALL_DIR/dagi"
ln -sf "$SHARE_DIR/dagi.py" "$INSTALL_DIR/diskagi"

echo "✓ Installed DiskAGI OMP Harness to $INSTALL_DIR/dagi"
echo "  Run: dagi            (interactive OMP TUI with 20-Slot Shared Brain)"
echo "       dagi --help     (all OMP flags & subcommands)"
echo "       dagi doctor     (verify Brain, OMP roles, models & endpoints)"

#!/usr/bin/env sh
# DiskAGI (`dagi`) — Frontier at home · Linux & macOS One-Line Installer
# Usage:
#   curl -fsSL https://bryonhigbee.github.io/install.sh | sh
#   or local: sh ~/Documents/DiskNCM/diskagi-cli/install.sh
set -eu

INSTALL_DIR="${DISKAGI_INSTALL_DIR:-$HOME/.local/bin}"
SHARE_DIR="${DISKAGI_SHARE_DIR:-$HOME/.local/share/diskagi}"
CONFIG_DIR="${HOME}/.config/diskagi"
REMOTE_BASE="${DISKAGI_DIST_URL:-https://bryonhigbee.github.io}"

mkdir -p "$INSTALL_DIR" "$SHARE_DIR" "$CONFIG_DIR"

if [ -f "/home/bryonh/Documents/DiskNCM/diskagi-cli/diskagi.py" ]; then
  cp "/home/bryonh/Documents/DiskNCM/diskagi-cli/diskagi.py" "$SHARE_DIR/dagi.py"
else
  echo "[dagi] Downloading DiskAGI CLI from ${REMOTE_BASE}/dagi.py ..."
  curl -fsSL "${REMOTE_BASE}/dagi.py" -o "$SHARE_DIR/dagi.py"
fi

chmod +x "$SHARE_DIR/dagi.py"

# Pick best Python interpreter (prefer DiskAGI brain/.venv if on main workstation, else python3)
PY_BIN="python3"
if [ -x "/home/bryonh/Documents/DiskNCM/brain/.venv/bin/python" ]; then
  PY_BIN="/home/bryonh/Documents/DiskNCM/brain/.venv/bin/python"
fi

cat > "$INSTALL_DIR/dagi" <<EOF
#!/usr/bin/env sh
exec "$PY_BIN" "$SHARE_DIR/dagi.py" "\$@"
EOF
chmod +x "$INSTALL_DIR/dagi"
ln -sf "$INSTALL_DIR/dagi" "$INSTALL_DIR/diskagi"

echo "✓ Installed DiskAGI CLI to $INSTALL_DIR/dagi (and $INSTALL_DIR/diskagi)"
echo "  Run: dagi          (interactive Blue Claude-Code TUI)"
echo "       dagi --help   (all subcommands)"
echo "       dagi doctor   (verify Brain, models & endpoints)"

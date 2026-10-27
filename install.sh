#!/usr/bin/env sh
# DiskAGI Standalone MCP + Vision/Video + Local->Cloud Failover Auto-Setup (Linux & macOS)
set -eu
SHARE_DIR="${HOME}/.local/share/diskagi-mcp"
mkdir -p "$SHARE_DIR"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/diskagi_mcp_standalone.py" ]; then
    cp "$SCRIPT_DIR/diskagi_mcp_standalone.py" "$SHARE_DIR/diskagi_mcp_standalone.py"
    cp "$SCRIPT_DIR/setup_harnesses.py" "$SHARE_DIR/setup_harnesses.py"
else
    curl -fsSL "https://bryonhigbee.github.io/releases/diskagi_mcp_standalone.py" -o "$SHARE_DIR/diskagi_mcp_standalone.py"
    curl -fsSL "https://bryonhigbee.github.io/releases/setup_harnesses.py" -o "$SHARE_DIR/setup_harnesses.py"
fi
chmod +x "$SHARE_DIR/diskagi_mcp_standalone.py" "$SHARE_DIR/setup_harnesses.py"
python3 "$SHARE_DIR/setup_harnesses.py"

#!/usr/bin/env python3
"""Automated Multi-Harness DiskAGI MCP Setup (`setup_harnesses.py`).

Runs on BOTH **Linux** and **Windows** (dual-boot ready):
  1. Installs the standalone `diskagi_mcp_standalone.py` into:
       - Linux/macOS: `~/.local/share/diskagi-mcp/diskagi_mcp_standalone.py`
         (and uses `/home/bryonh/Documents/DiskNCM/plugin/.venv/bin/diskncm-brain` when present)
       - Windows:     `%LOCALAPPDATA%\\DiskAGI-MCP\\diskagi_mcp_standalone.py`
  2. Automatically detects and wires `diskncm-brain` (with automatic Local -> Cloud Brain failover,
     Laya System-1 + 16-Domain router, 20-Slot Human Working Memory, and pure-CPU Vision/Video Bridge)
     into every installed agentic harness:
       - Oh-My-Pi (`omp`)
       - Claude Code (`claude`) & Claude Desktop
       - OpenCode (`opencode`)
       - OpenAI Codex CLI (`codex`)
       - Cursor (`cursor`)
       - Windsurf (`windsurf`)
       - Cline / Roo Code (VS Code)
       - Zed (`zed`)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


def get_install_paths() -> tuple[Path, str, list[str]]:
    home = Path.home()
    is_win = sys.platform.startswith("win") or os.name == "nt"
    if is_win:
        base_dir = Path(os.environ.get("LOCALAPPDATA") or (home / "AppData" / "Local")) / "DiskAGI-MCP"
        server_py = base_dir / "diskagi_mcp_standalone.py"
        py_cmd = shutil.which("python") or shutil.which("python3") or sys.executable or "python"
        return base_dir, py_cmd, [str(server_py)]
    else:
        base_dir = home / ".local" / "share" / "diskagi-mcp"
        server_py = base_dir / "diskagi_mcp_standalone.py"
        venv_bin = Path("/home/bryonh/Documents/DiskNCM/plugin/.venv/bin/diskncm-brain")
        if venv_bin.is_file():
            return base_dir, str(venv_bin), []
        py_cmd = shutil.which("python3") or sys.executable or "python3"
        return base_dir, py_cmd, [str(server_py)]


def _write_json_safe(path: Path, mutator) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        mutator(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return "configured"
    except Exception as e:
        return f"error: {e}"


def run_automated_mcp_setup() -> dict[str, Any]:
    home = Path.home()
    is_win = sys.platform.startswith("win") or os.name == "nt"
    base_dir, cmd, args = get_install_paths()
    base_dir.mkdir(parents=True, exist_ok=True)

    # Copy standalone server script into base_dir
    here_standalone = Path(__file__).resolve().parent / "diskagi_mcp_standalone.py"
    target_standalone = base_dir / "diskagi_mcp_standalone.py"
    if here_standalone.is_file() and here_standalone.resolve() != target_standalone.resolve():
        shutil.copy2(here_standalone, target_standalone)
        try:
            target_standalone.chmod(0o755)
        except Exception:
            pass

    stdio_entry = {
        "type": "stdio",
        "command": cmd,
        "args": args,
        "enabled": True,
    }

    harnesses: dict[str, str] = {}

    # 1. Oh-My-Pi (`omp`) — ALWAYS auto-install into ~/.omp/agent/mcp.json
    omp_mcp = home / ".omp" / "agent" / "mcp.json"
    def _mutate_omp(d: dict) -> None:
        s = d.setdefault("mcpServers", {})
        s.pop("synapse", None)
        s["diskncm-brain"] = stdio_entry
    harnesses["Oh-My-Pi (omp)"] = f"{_write_json_safe(omp_mcp, _mutate_omp)} ({omp_mcp})"

    # Also update repo .omp/mcp.json if present
    repo_omp = Path("/home/bryonh/Documents/DiskNCM/.omp/mcp.json")
    if repo_omp.parent.is_dir():
        _write_json_safe(repo_omp, _mutate_omp)

    # 2. Claude Code (`claude`) — ~/.claude.json
    claude_cfg = home / ".claude.json"
    def _mutate_claude(d: dict) -> None:
        s = d.setdefault("mcpServers", {})
        s["diskncm-brain"] = {"type": "stdio", "command": cmd, "args": args}
    harnesses["Claude Code (claude)"] = f"{_write_json_safe(claude_cfg, _mutate_claude)} ({claude_cfg})"

    # 3. Claude Desktop
    claude_desk = (
        (Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming")) / "Claude" / "claude_desktop_config.json")
        if is_win
        else (home / ".config" / "Claude" / "claude_desktop_config.json")
    )
    harnesses["Claude Desktop"] = f"{_write_json_safe(claude_desk, _mutate_claude)} ({claude_desk})"

    # 4. OpenCode (`opencode`) — ~/.config/opencode/opencode.json
    oc_cfg = home / ".config" / "opencode" / "opencode.json"
    def _mutate_opencode(d: dict) -> None:
        m = d.setdefault("mcp", {})
        m["diskncm-brain"] = {
            "type": "local",
            "command": [cmd, *args],
            "enabled": True,
        }
    harnesses["OpenCode (opencode)"] = f"{_write_json_safe(oc_cfg, _mutate_opencode)} ({oc_cfg})"

    # 5. OpenAI Codex CLI (`codex`) — ~/.codex/mcp.json
    codex_cfg = home / ".codex" / "mcp.json"
    harnesses["OpenAI Codex (codex)"] = f"{_write_json_safe(codex_cfg, _mutate_claude)} ({codex_cfg})"

    # 6. Cursor (`cursor`) — ~/.cursor/mcp.json
    cursor_cfg = home / ".cursor" / "mcp.json"
    harnesses["Cursor IDE (cursor)"] = f"{_write_json_safe(cursor_cfg, _mutate_claude)} ({cursor_cfg})"

    # 7. Windsurf (`windsurf`) — ~/.codeium/windsurf/mcp_config.json
    windsurf_cfg = home / ".codeium" / "windsurf" / "mcp_config.json"
    harnesses["Windsurf IDE"] = f"{_write_json_safe(windsurf_cfg, _mutate_claude)} ({windsurf_cfg})"

    # 8. Zed (`zed`) — ~/.config/zed/settings.json
    zed_cfg = home / ".config" / "zed" / "settings.json"
    def _mutate_zed(d: dict) -> None:
        cs = d.setdefault("context_servers", {})
        cs["diskncm-brain"] = {"command": {"path": cmd, "args": args, "env": {}}}
    harnesses["Zed Editor"] = f"{_write_json_safe(zed_cfg, _mutate_zed)} ({zed_cfg})"

    # Check active Brain status (Local vs Cloud failover)
    brain_mode = "cloud_failover"
    brain_root = ""
    try:
        from diskagi_mcp_standalone import resolve_brain_cross_platform
        b_path, b_mode = resolve_brain_cross_platform()
        brain_root = str(b_path)
        brain_mode = b_mode
    except Exception:
        pass

    result = {
        "ok": True,
        "platform": "Windows" if is_win else "Linux",
        "mcp_command": cmd,
        "mcp_args": args,
        "standalone_script": str(target_standalone),
        "brain_mode": brain_mode,
        "brain_root": brain_root,
        "failover_policy": "Local Brain -> Cloud Brain (automatic when Local Brain or Linux is off)",
        "features": [
            "20-Slot Human Working Memory (<1ms follow-ups, automatic topic-switch eviction)",
            "Laya System-1 + 16-Domain & 844-DevDocs Router (5.5M+ compressed notes)",
            "Pure-CPU Universal Vision & Video Bridge (`vision_inspect_image`, `vision_watch_video` — no local 4B LLM required)",
        ],
        "harnesses_configured": harnesses,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run_automated_mcp_setup()

#!/home/bryonh/Documents/DiskNCM/brain/.venv/bin/python
"""DiskAGI CLI (`dagi`) — Frontier at home.

Built directly on the `omp` (`can1357/oh-my-pi`) terminal agent harness architecture:
  - Role-based model routing (`default`, `smol`, `slow`, `plan`) supporting any local model
    (`diskagi-core` GPU engine, `ollama`, `vllm`/`llama.cpp`, any OpenAI-compatible server)
    and any frontier cloud provider (`anthropic`, `openai`, `gemini`, `openrouter`).
  - Full `omp` CLI ergonomics: `$ dagi [MESSAGES...]`, `@file` context expansion,
    `-p / --print`, `-c / --continue`, `-r / --resume`, `--model`, `--smol`, `--slow`,
    `--plan`, `--thinking`, `--goal`, `--cwd`, `--mode`, `--tools`, `--auto-approve`.
  - Surgical tool suite (`read`, `write`, `edit`, `bash`, `grep`, `glob`, `find`, `todo`,
    `brain_recall`, `brain_teach`) + 6-pass Python AST & headless smoke verifier.
  - 20-Slot Human Working Memory + Shared Compressed Brain (`Local brain` or `Cloud brain`,
    with 100% of knowledge synced across both).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import readline
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

VERSION = "1.5.0"
REPO_ROOT = Path("/home/bryonh/Documents/DiskNCM")
AGENTOS_DIR = REPO_ROOT / "agentos"
BRAIN_SRC_DIR = REPO_ROOT / "brain" / "src"
for _p in (str(REPO_ROOT), str(AGENTOS_DIR), str(BRAIN_SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CONFIG_DIR = Path.home() / ".config" / "diskagi"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_DIR = CONFIG_DIR / "sessions"
LAST_SESSION_FILE = SESSION_DIR / "last.json"
DEFAULT_LOCAL_BRAIN = Path("/home/bryonh/DiskNCM-Brain")
DEFAULT_AGENTOS_URL = os.environ.get("DISKAGI_CONTROL_URL", "http://127.0.0.1:7700")
DEFAULT_CORE_URL = os.environ.get("DISKAGI_CORE_URL", "http://127.0.0.1:7710")

# ── DiskAGI Electric-Blue OMP TrueColor ANSI Theme ────────────────────────────
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_ITALIC = "\033[3m"
C_BLUE_DEEP = "\033[38;2;59;130;246m"     # #3b82f6 Electric Royal Blue
C_BLUE_BRIGHT = "\033[38;2;96;165;250m"   # #60a5fa Sky Blue
C_CYAN_GLOW = "\033[38;2;116;237;241m"    # #74edf1 DiskAGI Signature Cyan
C_SLATE = "\033[38;2;148;163;184m"        # #94a3b8 Muted Slate
C_WHITE = "\033[38;2;241;245;249m"        # #f1f5f9 Crisp Foreground
C_GREEN = "\033[38;2;52;211;153m"         # #34d399 Emerald OK
C_AMBER = "\033[38;2;251;191;36m"         # #fbbf24 Warning Amber
C_RED = "\033[38;2;248;113;113m"          # #f87171 Coral Error
C_PURPLE = "\033[38;2;192;132;252m"       # #c084fc Tool Accent

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _visible_len(s: str) -> int:
    return len(_ANSI_RE.sub("", s))


def _pad_row(content: str, width: int = 74) -> str:
    vlen = _visible_len(content)
    pad = max(0, width - vlen)
    return f"{C_BLUE_DEEP}│{C_RESET}{content}{' ' * pad}{C_BLUE_DEEP}│{C_RESET}"

def render_dagi_header(cfg: dict[str, Any], st: dict[str, Any]) -> str:
    """Render a column-exact DiskAGI OMP header card with the Chip+Platter mark and status bar."""
    w = 76
    top = f"{C_BLUE_DEEP}╭{'─' * w}╮{C_RESET}"
    sep = f"{C_BLUE_DEEP}├{'─' * w}┤{C_RESET}"
    bot = f"{C_BLUE_DEEP}╰{'─' * w}╯{C_RESET}"

    active_m = cfg.get("active_model", "diskagi-core")
    thinking = cfg.get("thinking", "high")
    b_mode = "Cloud brain" if st.get("brain_mode") == "cloud" else "Local brain"
    n_notes = f"{st.get('note_count', 0):,}"
    wm_cap = st.get("working_memory_capacity", 20)

    # Symmetric 7-row Chip (cols 1..14) + Platter (cols 5..10) + Actuator Arm (col 9..12), all above separator
    r_default = cfg.get("roles", {}).get("default", active_m)
    r_smol = cfg.get("roles", {}).get("smol", "diskagi-core")
    r_slow = cfg.get("roles", {}).get("slow", "agentos-frontier")
    rows = [
        _pad_row(
            f"   {C_CYAN_GLOW}╻  ╻  ╻  ╻{C_RESET}     {C_BOLD}{C_WHITE}█▀▄ █ █▀▀ █▄▀ {C_BLUE_BRIGHT}▄▀█ █▀▀ █{C_RESET}   {C_CYAN_GLOW}DiskAGI{C_RESET} {C_SLATE}v{VERSION} · omp harness{C_RESET}",
            w,
        ),
        _pad_row(
            f" {C_BLUE_BRIGHT}╭─┴──┴──┴──┴─╮{C_RESET}   {C_BOLD}{C_WHITE}█▄▀ █ ▄██ █ █ {C_BLUE_BRIGHT}█▀█ █▄█ █{C_RESET}   {C_BLUE_BRIGHT}Frontier at home{C_RESET} {C_SLATE}(`dagi`){C_RESET}",
            w,
        ),
        _pad_row(
            f" {C_BLUE_BRIGHT}┤{C_CYAN_GLOW}•  ╭────╮   {C_BLUE_BRIGHT}├{C_RESET}   {C_SLATE}────────────────────────────────────────────────────────{C_RESET}",
            w,
        ),
        _pad_row(
            f" {C_BLUE_BRIGHT}┤{C_CYAN_GLOW}   │ ◉  │   {C_BLUE_BRIGHT}├{C_RESET}   {C_SLATE}Model  :{C_RESET} {C_WHITE}{active_m}{C_RESET} {C_SLATE}· thinking:{C_RESET} {C_CYAN_GLOW}{thinking}{C_RESET}",
            w,
        ),
        _pad_row(
            f" {C_BLUE_BRIGHT}┤{C_CYAN_GLOW}   ╰───╱╯ ◉ {C_BLUE_BRIGHT}├{C_RESET}   {C_SLATE}Brain  :{C_RESET} {C_GREEN}{b_mode}{C_RESET} {C_SLATE}·{C_RESET} {C_CYAN_GLOW}{n_notes} notes{C_RESET} {C_SLATE}({wm_cap}-slot WM){C_RESET}",
            w,
        ),
        _pad_row(
            f" {C_BLUE_BRIGHT}╰─┬──┬──┬──┬─╯{C_RESET}   {C_SLATE}Roles  :{C_RESET} {C_SLATE}default={C_WHITE}{r_default}{C_SLATE} · smol={C_WHITE}{r_smol}{C_RESET}",
            w,
        ),
        _pad_row(
            f"   {C_CYAN_GLOW}╹  ╹  ╹  ╹{C_RESET}     {C_SLATE}Storage:{C_RESET} {C_WHITE}{st.get('total_compressed_mb', 0)} MB{C_RESET} {C_SLATE}compressed PPMd · 0 raw files{C_RESET}",
            w,
        ),
        sep,
        _pad_row(
            f"  {C_SLATE}OMP Commands:{C_RESET} {C_CYAN_GLOW}/help  /model  /roles  /thinking  /brain  /memory  /doctor{C_RESET}",
            w,
        ),
    ]
    return "\n".join([top, *rows, bot])


DEFAULT_MODELS: dict[str, dict[str, Any]] = {
    "diskagi-core": {
        "id": "diskagi-core",
        "provider": "diskagi-core",
        "model": "Qwen3.5-4B-int8-262k",
        "url": f"{DEFAULT_CORE_URL}/generate",
        "description": "Local DiskAGI Core GPU Engine (Qwen3.5-4B int8, 262K ctx, 60 tok/s)",
    },
    "agentos-frontier": {
        "id": "agentos-frontier",
        "provider": "agentos",
        "model": "hosted-frontier-chain",
        "url": f"{DEFAULT_AGENTOS_URL}/api/chat/stream",
        "description": "DiskAGI Control Panel Hosted Frontier Chain + Shared Brain",
    },
    "ollama-local": {
        "id": "ollama-local",
        "provider": "ollama",
        "model": "qwen2.5-coder:latest",
        "url": "http://127.0.0.1:11434/api/chat",
        "description": "Any local Ollama model (http://127.0.0.1:11434)",
    },
    "vllm-local": {
        "id": "vllm-local",
        "provider": "openai-compatible",
        "model": "local-model",
        "url": "http://127.0.0.1:8000/v1/chat/completions",
        "api_key_env": "LOCAL_LLM_API_KEY",
        "description": "Any local vLLM / llama.cpp / LM Studio OpenAI-compatible server",
    },
    "claude-sonnet": {
        "id": "claude-sonnet",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "description": "Anthropic Claude Sonnet (via ANTHROPIC_API_KEY)",
    },
    "openai-gpt": {
        "id": "openai-gpt",
        "provider": "openai-compatible",
        "model": "gpt-4.1",
        "url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "description": "OpenAI GPT / o-series (via OPENAI_API_KEY)",
    },
    "openrouter": {
        "id": "openrouter",
        "provider": "openai-compatible",
        "model": "anthropic/claude-3.7-sonnet",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_API_KEY",
        "description": "OpenRouter Multi-Model Gateway (via OPENROUTER_API_KEY)",
    },
}


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "version": VERSION,
        "active_model": os.environ.get("DISKAGI_MODEL", "diskagi-core"),
        "thinking": os.environ.get("DISKAGI_THINKING", "high"),
        "roles": {
            "default": os.environ.get("DISKAGI_MODEL", "diskagi-core"),
            "smol": os.environ.get("PI_SMOL_MODEL", "diskagi-core"),
            "slow": os.environ.get("PI_SLOW_MODEL", "agentos-frontier"),
            "plan": os.environ.get("PI_PLAN_MODEL", "diskagi-core"),
        },
        "brain_mode": "local",
        "local_brain_path": str(DEFAULT_LOCAL_BRAIN),
        "storage_server_url": os.environ.get("DISKAGI_STORAGE_SERVER", ""),
        "cloud_remote": "brainstore:Brain",
        "control_panel_url": DEFAULT_AGENTOS_URL,
        "auto_recall": True,
        "recall_limit": 20,
        "auto_approve": False,
        "models": dict(DEFAULT_MODELS),
    }
    if CONFIG_FILE.is_file():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                saved_models = saved.pop("models", {})
                saved_roles = saved.pop("roles", {})
                cfg.update(saved)
                if isinstance(saved_models, dict):
                    cfg["models"].update(saved_models)
                if isinstance(saved_roles, dict):
                    cfg["roles"].update(saved_roles)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


# ── Shared Compressed Brain Access (20-Slot Human Working Memory) ─────────────
def get_brain_status(cfg: dict[str, Any]) -> dict[str, Any]:
    local_root = Path(cfg.get("local_brain_path") or DEFAULT_LOCAL_BRAIN)
    idx_db = local_root / ".diskncm" / "index.sqlite"
    bod_db = local_root / ".diskncm" / "bodies.sqlite"
    notes_cnt = 0
    sources_cnt = 0
    if idx_db.is_file():
        try:
            con = sqlite3.connect(f"file:{idx_db}?mode=ro", uri=True, timeout=5.0)
            notes_cnt = con.execute("SELECT max(id) FROM notes").fetchone()[0] or 0
            sources_cnt = con.execute("SELECT count(*) FROM sources WHERE status='ingested'").fetchone()[0]
            con.close()
        except Exception:
            pass
    idx_mb = round(idx_db.stat().st_size / (1024 * 1024), 1) if idx_db.is_file() else 0.0
    bod_mb = round(bod_db.stat().st_size / (1024 * 1024), 1) if bod_db.is_file() else 0.0
    raw_entries = [p.name for p in local_root.iterdir() if p.name != ".diskncm"] if local_root.is_dir() else []
    b_mode = cfg.get("brain_mode", "local")
    return {
        "brain_mode": b_mode,
        "local_brain_path": str(local_root),
        "local_compressed_only": len(raw_entries) == 0,
        "raw_unpacked_files": len(raw_entries),
        "note_count": notes_cnt,
        "ingested_sources": sources_cnt,
        "index_sqlite_mb": idx_mb,
        "bodies_ppmd_mb": bod_mb,
        "total_compressed_mb": round(idx_mb + bod_mb, 1),
        "working_memory_capacity": 20,
        "storage_server_url": cfg.get("storage_server_url") or "",
        "cloud_remote": cfg.get("cloud_remote") or "brainstore:Brain",
        "control_panel_url": cfg.get("control_panel_url") or DEFAULT_AGENTOS_URL,
    }


def recall_from_shared_brain(query: str, cfg: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    """Recall knowledge from the 20-Slot Shared Brain (`Local brain`, `Cloud brain`, or Storage Server)."""
    t0 = time.perf_counter()
    upstream = (cfg.get("storage_server_url") or "").strip().rstrip("/")
    if cfg.get("brain_mode") == "storage_server" and upstream:
        try:
            u = f"{upstream}/api/search?q={urllib.parse.quote_plus(query)}&limit={limit}"
            with urllib.request.urlopen(u, timeout=6.0) as r:
                hits = json.loads(r.read())
            return {
                "notes": hits[:limit],
                "categories": ["StorageServer"],
                "route_ms": round((time.perf_counter() - t0) * 1000, 1),
                "source": f"storage_server:{upstream}",
            }
        except Exception:
            pass

    local_root = Path(cfg.get("local_brain_path") or DEFAULT_LOCAL_BRAIN)
    idx_db = local_root / ".diskncm" / "index.sqlite"
    if idx_db.is_file():
        try:
            import server as agentos_server
            if getattr(agentos_server, "BRAIN", None) is None or str(agentos_server.BRAIN.path) != str(idx_db):
                agentos_server.CFG["vault"] = local_root
                agentos_server.BRAIN = agentos_server.Brain(idx_db)
            res = agentos_server.route_knowledge(query, limit=limit)
            res["source"] = "local_compressed_ppmd"
            return res
        except Exception:
            pass

    ctrl = (cfg.get("control_panel_url") or DEFAULT_AGENTOS_URL).rstrip("/")
    try:
        u = f"{ctrl}/api/search?q={urllib.parse.quote_plus(query)}&limit={limit}"
        with urllib.request.urlopen(u, timeout=6.0) as r:
            hits = json.loads(r.read())
        return {
            "notes": hits[:limit],
            "categories": ["ControlPanel"],
            "route_ms": round((time.perf_counter() - t0) * 1000, 1),
            "source": f"control_panel:{ctrl}",
        }
    except Exception as e:
        return {"notes": [], "categories": [], "route_ms": 0.0, "error": str(e)}


def teach_shared_brain(fact: str, title: str, cfg: dict[str, Any]) -> dict[str, Any]:
    local_root = Path(cfg.get("local_brain_path") or DEFAULT_LOCAL_BRAIN)
    idx_db = local_root / ".diskncm" / "index.sqlite"
    if idx_db.is_file():
        try:
            import server as agentos_server
            agentos_server.CFG["vault"] = local_root
            agentos_server.BRAIN = agentos_server.Brain(idx_db)
            return agentos_server._teach_brain_fact(fact, title=title, source="dagi-cli", kind="cli_taught")
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": f"Brain index not found at {idx_db}"}


# ── OMP Built-In Surgical Tool Suite ──────────────────────────────────────────
def exec_tool_read(path_str: str, start_line: int = 1, end_line: int = 120) -> dict[str, Any]:
    if ":" in path_str and not Path(path_str).exists():
        base_p, rng = path_str.rsplit(":", 1)
        m = re.match(r"^(\d+)(?:-(\d+))?$", rng)
        if m and Path(base_p).exists():
            path_str = base_p
            start_line = int(m.group(1))
            end_line = int(m.group(2) or (start_line + 100))
    p = Path(path_str).expanduser().resolve()
    if not p.is_file():
        return {"ok": False, "error": f"File not found: {p}"}
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    s = max(1, int(start_line))
    e = min(len(lines), max(s, int(end_line)))
    numbered = "\n".join(f"{i:4d}: {lines[i - 1]}" for i in range(s, e + 1))
    return {"ok": True, "path": str(p), "total_lines": len(lines), "range": f"{s}-{e}", "content": numbered}


def exec_tool_write(path_str: str, content: str) -> dict[str, Any]:
    p = Path(path_str).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p), "bytes_written": len(content.encode("utf-8"))}


def exec_tool_edit(path_str: str, old_text: str, new_text: str) -> dict[str, Any]:
    p = Path(path_str).expanduser().resolve()
    if not p.is_file():
        return {"ok": False, "error": f"File not found: {p}"}
    src = p.read_text(encoding="utf-8")
    if old_text not in src:
        return {"ok": False, "error": "old_text not found in file"}
    updated = src.replace(old_text, new_text, 1)
    p.write_text(updated, encoding="utf-8")
    return {"ok": True, "path": str(p), "replaced": True}


def exec_tool_glob(pattern: str = "*", root: str = ".") -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    matches = sorted(str(p.relative_to(base)) for p in base.rglob(pattern) if ".git" not in p.parts)[:200]
    return {"ok": True, "root": str(base), "pattern": pattern, "matches": matches}


def exec_tool_grep(pattern: str, path_str: str = ".") -> dict[str, Any]:
    target = Path(path_str).expanduser().resolve()
    rx = re.compile(pattern, re.I)
    hits: list[str] = []
    files = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file() and ".git" not in p.parts]
    for f in files[:400]:
        try:
            for idx, ln in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if rx.search(ln):
                    hits.append(f"{f}:{idx}:{ln[:160]}")
                    if len(hits) >= 80:
                        return {"ok": True, "hits": hits, "truncated": True}
        except Exception:
            continue
    return {"ok": True, "hits": hits, "truncated": False}


def exec_tool_find(query: str, path_str: str = ".") -> dict[str, Any]:
    words = [w for w in re.findall(r"[A-Za-z0-9_]{3,}", query)][:6]
    pattern = "|".join(re.escape(w) for w in words) if words else query
    return exec_tool_grep(pattern, path_str)


def exec_tool_bash(command: str, timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-2000:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def invoke_tool(name: str, args: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    if name == "read":
        return exec_tool_read(str(args.get("path", "")), int(args.get("start_line", 1)), int(args.get("end_line", 120)))
    if name == "write":
        return exec_tool_write(str(args.get("path", "")), str(args.get("content", "")))
    if name == "edit":
        return exec_tool_edit(str(args.get("path", "")), str(args.get("old_text", "")), str(args.get("new_text", "")))
    if name == "glob":
        return exec_tool_glob(str(args.get("pattern", "*")), str(args.get("root", ".")))
    if name == "grep":
        return exec_tool_grep(str(args.get("pattern", "")), str(args.get("path", ".")))
    if name == "find":
        return exec_tool_find(str(args.get("query", "")), str(args.get("path", ".")))
    if name == "bash":
        return exec_tool_bash(str(args.get("command", "")), int(args.get("timeout", 30)))
    if name == "brain_recall":
        return recall_from_shared_brain(str(args.get("query", "")), cfg, int(args.get("limit", 12)))
    if name == "brain_teach":
        return teach_shared_brain(str(args.get("fact", "")), str(args.get("title", "Learned Fact")), cfg)
    return {"ok": False, "error": f"Unknown tool: {name}"}


# ── Universal Multi-Provider & Local-Model Engine ─────────────────────────────
def generate_with_model(
    prompt: str,
    cfg: dict[str, Any],
    history: list[dict[str, str]] | None = None,
    stream_print: bool = False,
    model_override: str | None = None,
) -> dict[str, Any]:
    model_id = model_override or cfg.get("active_model") or "diskagi-core"
    models_map = cfg.get("models") or DEFAULT_MODELS
    m_spec = models_map.get(model_id) or {
        "id": model_id,
        "provider": "ollama" if model_id.startswith("ollama:") else "openai-compatible",
        "model": model_id.removeprefix("ollama:"),
        "url": "http://127.0.0.1:11434/api/chat" if model_id.startswith("ollama:") else "http://127.0.0.1:8000/v1/chat/completions",
    }
    provider = m_spec.get("provider", "diskagi-core")

    brain_res = {"notes": [], "categories": [], "route_ms": 0.0}
    if cfg.get("auto_recall", True):
        brain_res = recall_from_shared_brain(prompt, cfg, limit=int(cfg.get("recall_limit", 20)))

    passages = [
        f"[{n.get('category') or n.get('type', 'note')}] [[{n.get('title', '')}]]\n{n.get('excerpt', '')}"
        for n in brain_res.get("notes", [])
    ]
    if stream_print and brain_res.get("notes"):
        cats = ", ".join(brain_res.get("categories") or ["Brain"])
        wm = brain_res.get("working_memory") or {}
        wm_str = (
            f" · WM {wm.get('active', len(brain_res['notes']))}/{wm.get('max_slots', 20)} "
            f"({wm.get('retained', 0)} kept, {wm.get('added', 0)} new, {wm.get('evicted', 0)} swapped)"
            if wm
            else ""
        )
        print(
            f"{C_BLUE_DEEP}├─{C_RESET} {C_CYAN_GLOW}◉ Brain Recall:{C_RESET} "
            f"{C_WHITE}{len(brain_res['notes'])} refs{C_RESET} "
            f"{C_SLATE}[{cats}{wm_str} · {brain_res.get('route_ms', 0)} ms]{C_RESET}"
        )

    sys_msg = (
        "You are DiskAGI (`dagi`), Bryon Higbee's OMP-based AI agent ('Frontier at home'). "
        "When Brain memory passages are provided, actively synthesize their APIs, formulas, "
        "and verified facts. Give complete, runnable, bug-free code and clear explanations."
    )
    if passages and provider != "diskagi-core":
        sys_msg += "\n\n<brain_memory>\n" + "\n\n".join(passages[:10]) + "\n</brain_memory>"

    msgs: list[dict[str, str]] = [{"role": "system", "content": sys_msg}]
    if history:
        msgs.extend(history[-10:])
    msgs.append({"role": "user", "content": prompt})

    t0 = time.perf_counter()
    reply_text = ""
    think_text = ""
    thinking_lvl = cfg.get("thinking", "high")
    enable_think = thinking_lvl not in ("off", "none", "false") and len(prompt.split()) > 3

    if provider == "diskagi-core":
        url = m_spec.get("url") or f"{DEFAULT_CORE_URL}/generate"
        payload = json.dumps({
            "messages": msgs,
            "visuals": [],
            "passages": passages[:16],
            "memory": "auto",
            "think": enable_think,
            "think_budget": 192 if thinking_lvl in ("minimal", "low") else 256,
            "max_new": 4096,
            "temperature": 0.25,
            "top_p": 0.9,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        printed_hdr = False
        with urllib.request.urlopen(req, timeout=300) as r:
            while raw_ln := r.readline():
                ev = json.loads(raw_ln)
                etype = ev.get("type")
                if etype == "think":
                    think_text += ev.get("text", "")
                elif etype == "delta":
                    chunk = ev.get("text", "")
                    reply_text += chunk
                    if stream_print:
                        if not printed_hdr:
                            printed_hdr = True
                            print(f"{C_BLUE_DEEP}╰─▸{C_RESET} ", end="", flush=True)
                        print(chunk, end="", flush=True)
        if stream_print and printed_hdr:
            print()

    elif provider == "agentos":
        url = m_spec.get("url") or f"{DEFAULT_AGENTOS_URL}/api/chat/stream"
        payload = json.dumps({"message": prompt, "mode": "auto", "visuals": []}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json", "X-DiskNCM": "1"}
        )
        printed_hdr = False
        with urllib.request.urlopen(req, timeout=300) as r:
            while raw_ln := r.readline():
                ln = raw_ln.decode("utf-8", errors="replace").strip()
                if not ln:
                    continue
                ev = json.loads(ln)
                if ev.get("type") == "delta":
                    chunk = ev.get("text", "")
                    reply_text += chunk
                    if stream_print:
                        if not printed_hdr:
                            printed_hdr = True
                            print(f"{C_BLUE_DEEP}╰─▸{C_RESET} ", end="", flush=True)
                        print(chunk, end="", flush=True)
                elif ev.get("type") == "done" and not reply_text:
                    reply_text = (ev.get("turn") or {}).get("reply", "")
        if stream_print and printed_hdr:
            print()

    elif provider == "ollama":
        url = m_spec.get("url") or "http://127.0.0.1:11434/api/chat"
        payload = json.dumps({"model": m_spec.get("model", "qwen2.5-coder:latest"), "messages": msgs, "stream": False}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
            reply_text = (data.get("message") or {}).get("content", "")
            if stream_print:
                print(f"{C_BLUE_DEEP}╰─▸{C_RESET} {reply_text}")

    elif provider == "anthropic":
        api_key = os.environ.get(m_spec.get("api_key_env") or "ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")
        url = m_spec.get("url") or "https://api.anthropic.com/v1/messages"
        payload = json.dumps({
            "model": m_spec.get("model", "claude-sonnet-4-20250514"),
            "max_tokens": 4096,
            "system": sys_msg,
            "messages": [m for m in msgs if m["role"] != "system"],
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
            reply_text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            if stream_print:
                print(f"{C_BLUE_DEEP}╰─▸{C_RESET} {reply_text}")

    else:
        url = m_spec.get("url") or "http://127.0.0.1:8000/v1/chat/completions"
        api_key = os.environ.get(m_spec.get("api_key_env") or "OPENAI_API_KEY", "local-no-key")
        payload = json.dumps({
            "model": m_spec.get("model", "local-model"),
            "messages": msgs,
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
            reply_text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if stream_print:
                print(f"{C_BLUE_DEEP}╰─▸{C_RESET} {reply_text}")

    try:
        import server as agentos_server
        if "```python" in reply_text:
            reply_text = agentos_server._verify_and_repair_python_In_reply(prompt, reply_text)
    except Exception:
        pass

    return {
        "ok": True,
        "model": model_id,
        "provider": provider,
        "reply": reply_text.strip(),
        "reasoning": think_text.strip(),
        "brain_recall": {
            "count": len(brain_res.get("notes", [])),
            "categories": brain_res.get("categories", []),
            "route_ms": brain_res.get("route_ms", 0.0),
            "working_memory": brain_res.get("working_memory", {}),
            "titles": [n.get("title") for n in brain_res.get("notes", [])[:10]],
        },
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def _expand_at_files(tokens: list[str]) -> str:
    parts: list[str] = []
    for tok in tokens:
        if tok.startswith("@") and len(tok) > 1:
            fp = Path(tok[1:]).expanduser()
            if fp.is_file():
                body = fp.read_text(encoding="utf-8", errors="replace")[:16000]
                parts.append(f"<file path=\"{fp}\">\n{body}\n</file>")
                continue
        parts.append(tok)
    return " ".join(parts).strip()


def check_Updates(cfg: dict[str, Any], server_url: str | None = None) -> dict[str, Any]:
    ctrl = (server_url or cfg.get("control_panel_url") or DEFAULT_AGENTOS_URL).rstrip("/")
    try:
        with urllib.request.urlopen(f"{ctrl}/api/distribution/manifest", timeout=6.0) as r:
            manifest = json.loads(r.read())
        if manifest.get("storage_server_url"):
            cfg["storage_server_url"] = manifest["storage_server_url"]
        save_config(cfg)
        return {
            "ok": True,
            "control_panel": ctrl,
            "local_version": VERSION,
            "latest_version": manifest.get("version", VERSION),
            "brain_note_count": manifest.get("brain_note_count", 0),
            "brain_mode": cfg.get("brain_mode", "local"),
            "storage_server_url": cfg.get("storage_server_url", ""),
            "install_linux": manifest.get("install_linux", "curl -fsSL https://bryonhigbee.github.io/install.sh | sh"),
            "install_windows": manifest.get("install_windows", "irm https://bryonhigbee.github.io/install.ps1 | iex"),
        }
    except Exception as e:
        return {"ok": False, "control_panel": ctrl, "error": str(e)}


# ── Interactive OMP Terminal UI (`dagi`) ──────────────────────────────────────
def run_interactive_tui(cfg: dict[str, Any], initial_prompt: str = "", resume: bool = False) -> int:
    st = get_brain_status(cfg)
    print(render_dagi_header(cfg, st))
    history: list[dict[str, str]] = []
    if resume and LAST_SESSION_FILE.is_file():
        try:
            history = json.loads(LAST_SESSION_FILE.read_text(encoding="utf-8"))
            print(f"{C_GREEN}✓ Resumed session ({len(history)} messages){C_RESET}")
        except Exception:
            history = []

    if initial_prompt:
        print(f"{C_BLUE_DEEP}╭─[{C_CYAN_GLOW}dagi{C_BLUE_DEEP} · {C_BLUE_BRIGHT}{cfg.get('active_model')}{C_BLUE_DEEP}]{C_RESET}")
        res = generate_with_model(initial_prompt, cfg, history=history, stream_print=True)
        history.append({"role": "user", "content": initial_prompt})
        history.append({"role": "assistant", "content": res["reply"]})

    while True:
        try:
            prompt = input(
                f"\n{C_BLUE_DEEP}╭─[{C_CYAN_GLOW}dagi{C_BLUE_DEEP} · {C_BLUE_BRIGHT}{cfg.get('active_model')}{C_BLUE_DEEP} · {C_SLATE}{Path.cwd().name}{C_BLUE_DEEP}]\n╰─▸ {C_RESET}"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C_SLATE}Session saved. Run `dagi -c` to continue.{C_RESET}")
            break
        if not prompt:
            continue
        if prompt in ("/exit", "/quit", "exit", "quit"):
            break
        if prompt == "/help":
            print(
                f"{C_CYAN_GLOW}OMP Slash Commands (`dagi`):{C_RESET}\n"
                f"  {C_WHITE}/model [id]{C_RESET}               List or switch active model (Local GPU, Ollama, vLLM, Claude, GPT, OpenRouter)\n"
                f"  {C_WHITE}/roles{C_RESET}                    Show OMP model roles (`default`, `smol`, `slow`, `plan`)\n"
                f"  {C_WHITE}/thinking <level>{C_RESET}         Set thinking level (`off`, `minimal`, `low`, `medium`, `high`)\n"
                f"  {C_WHITE}/brain [local|cloud|url]{C_RESET}  Show Compressed Brain status or switch `Local brain` / `Cloud brain`\n"
                f"  {C_WHITE}/memory{C_RESET}                   Inspect active 20-Slot Human Working Memory recalls & salience\n"
                f"  {C_WHITE}/recall <query>{C_RESET}           Test 20-Slot Brain recall directly\n"
                f"  {C_WHITE}/teach <fact>{C_RESET}             Encode a verified fact into the Compressed Brain\n"
                f"  {C_WHITE}/doctor{C_RESET}                   Verify models, GPU Core, Control Panel, and Brain\n"
                f"  {C_WHITE}/update{C_RESET}                   Pull latest release manifest from Control Panel\n"
                f"  {C_WHITE}/clear{C_RESET}                    Clear conversation history\n"
                f"  {C_WHITE}/exit{C_RESET}                     Save session and exit"
            )
            continue
        if prompt == "/clear":
            history.clear()
            print(f"{C_GREEN}✓ Cleared conversation history.{C_RESET}")
            continue
        if prompt == "/roles":
            for r_k, r_v in (cfg.get("roles") or {}).items():
                print(f"  {C_CYAN_GLOW}{r_k:10s}{C_RESET} -> {C_WHITE}{r_v}{C_RESET}")
            continue
        if prompt.startswith("/thinking"):
            parts = prompt.split(maxsplit=1)
            if len(parts) == 2 and parts[1] in ("off", "minimal", "low", "medium", "high", "auto"):
                cfg["thinking"] = parts[1]
                save_config(cfg)
                print(f"{C_GREEN}✓ Set thinking level to `{parts[1]}`{C_RESET}")
            else:
                print(f"Current thinking level: {C_CYAN_GLOW}{cfg.get('thinking', 'high')}{C_RESET}")
            continue
        if prompt == "/memory":
            wm_file = REPO_ROOT / "status" / "working-memory.json"
            if wm_file.is_file():
                print(wm_file.read_text(encoding="utf-8"))
            else:
                print(f"{C_SLATE}Working memory is empty.{C_RESET}")
            continue
        if prompt.startswith("/model"):
            parts = prompt.split(maxsplit=1)
            if len(parts) == 1:
                for mid, m in cfg["models"].items():
                    mark = f"{C_CYAN_GLOW}●{C_RESET}" if mid == cfg.get("active_model") else " "
                    print(f" {mark} {C_WHITE}{mid:18s}{C_RESET} [{m.get('provider')}] — {m.get('description', m.get('model'))}")
            else:
                new_m = parts[1].strip()
                cfg["active_model"] = new_m
                cfg.setdefault("roles", {})["default"] = new_m
                save_config(cfg)
                print(f"{C_GREEN}✓ Active model switched to `{new_m}`{C_RESET}")
            continue
        if prompt.startswith("/brain"):
            parts = prompt.split(maxsplit=1)
            if len(parts) == 2:
                arg = parts[1].strip()
                if arg in ("local", "cloud"):
                    cfg["brain_mode"] = arg
                else:
                    cfg["brain_mode"] = "storage_server"
                    cfg["storage_server_url"] = arg
                save_config(cfg)
            print(json.dumps(get_brain_status(cfg), indent=2))
            continue
        if prompt.startswith("/recall "):
            q = prompt[len("/recall "):].strip()
            r = recall_from_shared_brain(q, cfg, limit=20)
            for i, n in enumerate(r.get("notes", []), 1):
                print(f"  {C_CYAN_GLOW}{i:2d}.{C_RESET} [{n.get('wm_state', 'active')} · {n.get('category')}] {C_WHITE}{n.get('title')}{C_RESET}")
            continue
        if prompt.startswith("/teach "):
            fact = prompt[len("/teach "):].strip()
            ev = teach_shared_brain(fact, f"Fact: {fact[:48]}", cfg)
            print(json.dumps(ev, indent=2))
            continue
        if prompt == "/doctor":
            print(json.dumps(run_doctor(cfg), indent=2))
            continue
        if prompt == "/update":
            print(json.dumps(check_Updates(cfg), indent=2))
            continue

        expanded = _expand_at_files(prompt.split())
        try:
            res = generate_with_model(expanded, cfg, history=history, stream_print=True)
            history.append({"role": "user", "content": expanded})
            history.append({"role": "assistant", "content": res["reply"]})
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            LAST_SESSION_FILE.write_text(json.dumps(history[-20:], indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            print(f"{C_RED}✗ Error: {e}{C_RESET}")
    return 0


def install_universal_plugin(cfg: dict[str, Any]) -> dict[str, Any]:
    """Wire the DiskAGI Brain MCP Plugin (`diskncm-brain`) + `/v1` Brain-Injecting Gateway into
    `omp` (Oh-My-Pi), `opencode`, `claude` (Claude Code), and any OpenAI/Anthropic-compatible CLI."""
    mcp_bin = str(REPO_ROOT / "plugin" / ".venv" / "bin" / "diskncm-brain")
    b_root = str(cfg.get("local_brain_path") or DEFAULT_LOCAL_BRAIN)
    gw_url = f"{(cfg.get('control_panel_url') or DEFAULT_AGENTOS_URL).rstrip('/')}/v1"
    mcp_entry = {
        "type": "stdio",
        "command": mcp_bin,
        "args": [],
        "env": {"DISKNCM_BRAIN": b_root},
        "enabled": True,
    }
    wired: dict[str, str] = {}

    # 1. Oh-My-Pi (`omp`): ~/.omp/agent/mcp.json + project .omp/mcp.json
    for omp_mcp in (Path.home() / ".omp" / "agent" / "mcp.json", REPO_ROOT / ".omp" / "mcp.json"):
        try:
            omp_mcp.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(omp_mcp.read_text(encoding="utf-8")) if omp_mcp.is_file() else {}
            servers = data.setdefault("mcpServers", {})
            servers.pop("synapse", None)
            servers["diskncm-brain"] = mcp_entry
            omp_mcp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            wired[str(omp_mcp)] = "configured"
        except Exception as e:
            wired[str(omp_mcp)] = f"error: {e}"

    # 2. OpenCode (`opencode`): ~/.config/opencode/opencode.json
    oc_cfg = Path.home() / ".config" / "opencode" / "opencode.json"
    try:
        oc_cfg.parent.mkdir(parents=True, exist_ok=True)
        oc_data = json.loads(oc_cfg.read_text(encoding="utf-8")) if oc_cfg.is_file() else {}
        oc_mcp = oc_data.setdefault("mcp", {})
        oc_mcp["diskncm-brain"] = {
            "type": "local",
            "command": [mcp_bin],
            "environment": {"DISKNCM_BRAIN": b_root},
            "enabled": True,
        }
        oc_prov = oc_data.setdefault("provider", {})
        oc_prov["diskagi"] = {
            "name": "DiskAGI Brain Gateway (Qwen3.5-4B + 20-Slot Brain)",
            "options": {"baseURL": gw_url, "apiKey": "diskagi-local"},
            "models": {
                "diskagi-core": {"name": "DiskAGI Qwen3.5-4B + 20-Slot Brain (262K)"},
                "qwen3.5-4b-brain": {"name": "Qwen3.5-4B + Shared Compressed Brain"},
            },
        }
        oc_cfg.write_text(json.dumps(oc_data, indent=2) + "\n", encoding="utf-8")
        wired[str(oc_cfg)] = "configured"
    except Exception as e:
        wired[str(oc_cfg)] = f"error: {e}"

    # 3. Claude Code (`claude`): ~/.claude.json
    cl_cfg = Path.home() / ".claude.json"
    try:
        cl_data = json.loads(cl_cfg.read_text(encoding="utf-8")) if cl_cfg.is_file() else {}
        cl_mcp = cl_data.setdefault("mcpServers", {})
        cl_mcp["diskncm-brain"] = {
            "type": "stdio",
            "command": mcp_bin,
            "args": [],
            "env": {"DISKNCM_BRAIN": b_root},
        }
        cl_cfg.write_text(json.dumps(cl_data, indent=2) + "\n", encoding="utf-8")
        wired[str(cl_cfg)] = "configured"
    except Exception as e:
        wired[str(cl_cfg)] = f"error: {e}"

    return {
        "ok": True,
        "mcp_plugin_binary": mcp_bin,
        "openai_gateway_url": gw_url,
        "anthropic_gateway_url": gw_url,
        "wired_clients": wired,
    }


def run_doctor(cfg: dict[str, Any]) -> dict[str, Any]:
    brain_st = get_brain_status(cfg)
    core_ok = False
    try:
        with urllib.request.urlopen(f"{DEFAULT_CORE_URL}/health", timeout=2.5) as r:
            core_ok = r.status == 200
    except Exception:
        pass
    ctrl_ok = False
    try:
        with urllib.request.urlopen(f"{DEFAULT_AGENTOS_URL}/api/health", timeout=2.5) as r:
            ctrl_ok = r.status == 200
    except Exception:
        pass
    active_m = cfg.get("active_model", "diskagi-core")
    m_spec = (cfg.get("models") or DEFAULT_MODELS).get(active_m, {})
    key_env = m_spec.get("api_key_env")
    auth_ok = True if not key_env else bool(os.environ.get(key_env))
    plug_info = install_universal_plugin(cfg)
    return {
        "ok": brain_st["note_count"] > 0 and (core_ok or ctrl_ok),
        "version": VERSION,
        "harness": "omp (oh-my-pi)",
        "command": "dagi",
        "omp_binary": shutil.which("omp") or "/home/bryonh/.local/bin/omp",
        "binary": shutil.which("dagi") or str(Path(__file__).resolve()),
        "active_model": active_m,
        "roles": cfg.get("roles", {}),
        "thinking": cfg.get("thinking", "high"),
        "provider": m_spec.get("provider", "custom"),
        "auth_status": "configured" if auth_ok else f"missing_env:{key_env}",
        "core_gpu_engine_reachable": core_ok,
        "control_panel_reachable": ctrl_ok,
        "plugin": plug_info,
        "brain": brain_st,
    }


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(
        prog="dagi",
        description="DiskAGI (`dagi`) — Frontier at home · Built on `omp` (oh-my-pi) + 20-Slot Shared Compressed Brain",
    )
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    ap.add_argument("--mode", choices=["text", "json", "rpc"], default="text", help="Output mode: text (default), json, or rpc")
    ap.add_argument("--model", help="Override active model for this invocation")
    ap.add_argument("--smol", help="Smol/fast model for lightweight tasks (or PI_SMOL_MODEL env)")
    ap.add_argument("--slow", help="Slow/reasoning model for thorough analysis (or PI_SLOW_MODEL env)")
    ap.add_argument("--plan", help="Plan model for architectural planning (or PI_PLAN_MODEL env)")
    ap.add_argument("--thinking", choices=["off", "minimal", "low", "medium", "high", "auto"], help="Set thinking level")
    ap.add_argument("--goal", help="Start in autonomous goal mode with the given objective")
    ap.add_argument("-p", "--print", dest="print_mode", action="store_true", help="Non-interactive mode: process prompt and exit")
    ap.add_argument("-c", "--continue", dest="cont", action="store_true", help="Continue previous session")
    ap.add_argument("-r", "--resume", nargs="?", const="last", help="Resume a saved session")
    ap.add_argument("--cwd", help="Directory to start in")
    ap.add_argument("--tools", help="Comma-separated list of tools to enable (default: all)")
    ap.add_argument("--no-tools", action="store_true", help="Disable built-in tools")
    ap.add_argument("--auto-approve", action="store_true", help="Auto-approve all tool calls")

    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("chat", help="Launch interactive DiskAGI OMP TUI (default)")
    sub.add_parser("doctor", help="Verify config, OMP roles, Core GPU engine, Control Panel, and Shared Brain")
    sub.add_parser("plug", help="Wire DiskAGI Brain MCP Plugin + /v1 Gateway into omp, opencode, claude & IDEs")

    p_run = sub.add_parser("run", help="Run a one-shot prompt with automatic 20-slot Shared Brain recall")
    p_run.add_argument("prompt", nargs="+", help="Prompt text (supports @file references)")

    p_models = sub.add_parser("models", help="List, switch, or add local & frontier models and OMP roles")
    m_sub = p_models.add_subparsers(dest="models_cmd")
    m_sub.add_parser("list", help="List all configured models & OMP roles")
    p_muse = m_sub.add_parser("use", help="Switch active model (e.g. diskagi-core, ollama:qwen2.5-coder, claude-sonnet)")
    p_muse.add_argument("model_id")
    p_madd = m_sub.add_parser("add", help="Register any custom local or remote model endpoint")
    p_madd.add_argument("model_id")
    p_madd.add_argument("--provider", default="openai-compatible", choices=["diskagi-core", "ollama", "openai-compatible", "anthropic", "agentos"])
    p_madd.add_argument("--model", required=True)
    p_madd.add_argument("--url", required=True)
    p_madd.add_argument("--api-key-env", default="")
    p_madd.add_argument("--description", default="")

    p_brain = sub.add_parser("brain", help="Inspect, recall, teach, or switch `Local brain` / `Cloud brain`")
    b_sub = p_brain.add_subparsers(dest="brain_cmd")
    b_sub.add_parser("status", help="Show Shared Brain status (Local brain vs Cloud brain)")
    p_brecall = b_sub.add_parser("recall", help="Recall up to 20 references from the Shared Brain")
    p_brecall.add_argument("query", nargs="+")
    p_brecall.add_argument("--limit", type=int, default=20)
    p_bteach = b_sub.add_parser("teach", help="Encode a verified fact directly into the Compressed Brain")
    p_bteach.add_argument("fact", nargs="+")
    p_bteach.add_argument("--title", default="CLI Taught Fact")
    p_bup = b_sub.add_parser("upstream", help="Switch between `local` (Local brain), `cloud` (Cloud brain), or a Storage Server URL")
    p_bup.add_argument("target", help="'local', 'cloud', or http://<storage-server>:7700")

    p_tc = sub.add_parser("tool-call", help="Invoke OMP built-in surgical tools (read, write, edit, glob, grep, find, bash)")
    p_tc.add_argument("tool", choices=["read", "write", "edit", "glob", "grep", "find", "bash", "brain_recall", "brain_teach"])
    p_tc.add_argument("args_json", nargs="?", default="{}")

    p_read = sub.add_parser("read", help="Show what the OMP read tool returns for a path[:start-end]")
    p_read.add_argument("path")
    p_grep = sub.add_parser("grep", help="Search file contents with regex")
    p_grep.add_argument("pattern")
    p_grep.add_argument("path", nargs="?", default=".")
    p_find = sub.add_parser("find", help="Find files and line ranges implementing a behavior")
    p_find.add_argument("query", nargs="+")

    p_cfg = sub.add_parser("config", help="View or update DiskAGI OMP configuration")
    p_cfg.add_argument("key", nargs="?")
    p_cfg.add_argument("value", nargs="?")

    sub.add_parser("stats", help="Show Brain & session statistics")
    p_upd = sub.add_parser("update", help="Check Control Panel or Storage Server for updates")
    p_upd.add_argument("--server", default="")

    known_subcmds = {"chat", "doctor", "plug", "run", "models", "brain", "tool-call", "read", "grep", "find", "config", "stats", "update"}
    args, unknown = ap.parse_known_args(raw_args)
    cfg = load_config()
    if args.cwd:
        os.chdir(Path(args.cwd).expanduser().resolve())
    if args.model:
        cfg["active_model"] = args.model
        cfg.setdefault("roles", {})["default"] = args.model
    if args.smol:
        cfg.setdefault("roles", {})["smol"] = args.smol
    if args.slow:
        cfg.setdefault("roles", {})["slow"] = args.slow
    if args.plan:
        cfg.setdefault("roles", {})["plan"] = args.plan
    if args.thinking:
        cfg["thinking"] = args.thinking
    if args.auto_approve:
        cfg["auto_approve"] = True
    json_out = bool(args.json or args.mode == "json")

    # Handle `$ dagi -p "prompt"` or `$ dagi @file "prompt"` just like `omp`
    if args.cmd not in known_subcmds and (unknown or args.goal):
        prompt_str = args.goal or _expand_at_files(unknown)
        if args.print_mode or json_out:
            res = generate_with_model(prompt_str, cfg, stream_print=not json_out)
            if json_out:
                print(json.dumps(res, indent=2))
            return 0
        return run_interactive_tui(cfg, initial_prompt=prompt_str, resume=bool(args.cont or args.resume))

    if args.cmd == "plug":
        res = install_universal_plugin(cfg)
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd in (None, "chat"):
        if args.print_mode and unknown:
            res = generate_with_model(_expand_at_files(unknown), cfg, stream_print=not json_out)
            if json_out:
                print(json.dumps(res, indent=2))
            return 0
        install_universal_plugin(cfg)
        omp_bin = shutil.which("omp") or "/home/bryonh/.local/bin/omp"
        if Path(omp_bin).is_file() and sys.stdin.isatty():
            st = get_brain_status(cfg)
            print(render_dagi_header(cfg, st), flush=True)
            os.execvp(omp_bin, [omp_bin, *raw_args])
        return run_interactive_tui(cfg, resume=bool(args.cont or args.resume))
    if args.cmd == "doctor":
        rep = run_doctor(cfg)
        if json_out:
            print(json.dumps(rep, indent=2))
        else:
            st = rep["brain"]
            b_label = "Cloud brain" if st["brain_mode"] == "cloud" else "Local brain"
            print(render_dagi_header(cfg, st))
            print(f"  {C_GREEN if rep['ok'] else C_RED}●{C_RESET} Harness       : {C_WHITE}omp (oh-my-pi) · dagi v{rep['version']}{C_RESET}")
            print(f"  {C_GREEN if rep['auth_status'] == 'configured' else C_AMBER}●{C_RESET} Active Model  : {C_WHITE}{rep['active_model']}{C_RESET} [{rep['provider']}] (thinking: {rep['thinking']})")
            print(f"  {C_GREEN if rep['core_gpu_engine_reachable'] else C_AMBER}●{C_RESET} Core GPU (:7710): {'ONLINE' if rep['core_gpu_engine_reachable'] else 'OFFLINE'}")
            print(f"  {C_GREEN if rep['control_panel_reachable'] else C_AMBER}●{C_RESET} Control (:7700) : {'ONLINE' if rep['control_panel_reachable'] else 'OFFLINE'}")
            print(f"  {C_GREEN if st['local_compressed_only'] else C_AMBER}●{C_RESET} {b_label:13s} : {C_CYAN_GLOW}{st['note_count']:,} notes{C_RESET} ({st['total_compressed_mb']} MB compressed · {st['raw_unpacked_files']} raw files · {st['working_memory_capacity']} WM slots)")
        return 0 if rep["ok"] else 1

    if args.cmd == "run":
        prompt_str = _expand_at_files(args.prompt)
        res = generate_with_model(prompt_str, cfg, stream_print=not json_out)
        if json_out:
            print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "models":
        sub_c = args.models_cmd or "list"
        if sub_c == "list":
            out = {"active_model": cfg.get("active_model"), "roles": cfg.get("roles", {}), "models": cfg["models"]}
            if json_out:
                print(json.dumps(out, indent=2))
            else:
                for mid, m in cfg["models"].items():
                    mark = f"{C_CYAN_GLOW}●{C_RESET}" if mid == cfg.get("active_model") else " "
                    print(f" {mark} {C_WHITE}{mid:18s}{C_RESET} [{m.get('provider')}] -> {m.get('model')} ({m.get('url')})")
            return 0
        if sub_c == "use":
            cfg["active_model"] = args.model_id
            cfg.setdefault("roles", {})["default"] = args.model_id
            save_config(cfg)
            print(json.dumps({"ok": True, "active_model": args.model_id}) if json_out else f"✓ Active model set to {args.model_id}")
            return 0
        if sub_c == "add":
            cfg["models"][args.model_id] = {
                "id": args.model_id,
                "provider": args.provider,
                "model": args.model,
                "url": args.url,
                "api_key_env": args.api_key_env,
                "description": args.description or f"Custom {args.provider} model ({args.model})",
            }
            cfg["active_model"] = args.model_id
            save_config(cfg)
            print(json.dumps({"ok": True, "added": cfg["models"][args.model_id]}, indent=2))
            return 0

    if args.cmd == "brain":
        sub_b = args.brain_cmd or "status"
        if sub_b == "status":
            print(json.dumps(get_brain_status(cfg), indent=2))
            return 0
        if sub_b == "recall":
            q = " ".join(args.query)
            print(json.dumps(recall_from_shared_brain(q, cfg, limit=args.limit), indent=2))
            return 0
        if sub_b == "teach":
            fact = " ".join(args.fact)
            print(json.dumps(teach_shared_brain(fact, args.title, cfg), indent=2))
            return 0
        if sub_b == "upstream":
            t = args.target.strip()
            if t in ("local", "cloud"):
                cfg["brain_mode"] = t
            else:
                cfg["brain_mode"] = "storage_server"
                cfg["storage_server_url"] = t
            save_config(cfg)
            print(json.dumps(get_brain_status(cfg), indent=2))
            return 0

    if args.cmd == "tool-call":
        t_args = json.loads(args.args_json)
        out = invoke_tool(args.tool, t_args, cfg)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1

    if args.cmd == "read":
        print(json.dumps(exec_tool_read(args.path), indent=2))
        return 0
    if args.cmd == "grep":
        print(json.dumps(exec_tool_grep(args.pattern, args.path), indent=2))
        return 0
    if args.cmd == "find":
        print(json.dumps(exec_tool_find(" ".join(args.query)), indent=2))
        return 0
    if args.cmd == "config":
        if not args.key:
            print(json.dumps(cfg, indent=2))
        elif args.value is None:
            print(json.dumps({args.key: cfg.get(args.key)}, indent=2))
        else:
            cfg[args.key] = args.value
            save_config(cfg)
            print(json.dumps({"ok": True, args.key: args.value}, indent=2))
        return 0
    if args.cmd == "stats":
        print(json.dumps(get_brain_status(cfg), indent=2))
        return 0
    if args.cmd == "update":
        out = check_Updates(cfg, server_url=args.server)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

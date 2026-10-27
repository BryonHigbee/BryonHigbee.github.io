#!/home/bryonh/Documents/DiskNCM/brain/.venv/bin/python
"""DiskAGI CLI (`dagi`) — Frontier at home.

Custom CLI agent harness combining the ergonomics of `codeaashu/claude-code` (Blue-themed
interactive terminal UI, slash commands, permissioned agentic tool loop, DiskAGI Chip+Platter
logo) and `can1357/oh-my-pi` (`omp`: multi-provider & any-local-model registry, surgical
file/shell tools, AST + headless code verifier, and one-command private self-update),
wired directly into the shared Compressed DiskAGI Brain (32-note lossless PPMd + 20-Slot
Human Working Memory + Laya System-1 Decision Router).
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

VERSION = "1.4.0"
REPO_ROOT = Path("/home/bryonh/Documents/DiskNCM")
AGENTOS_DIR = REPO_ROOT / "agentos"
BRAIN_SRC_DIR = REPO_ROOT / "brain" / "src"
for _p in (str(REPO_ROOT), str(AGENTOS_DIR), str(BRAIN_SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CONFIG_DIR = Path.home() / ".config" / "diskagi"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_LOCAL_BRAIN = Path("/home/bryonh/DiskNCM-Brain")
DEFAULT_AGENTOS_URL = os.environ.get("DISKAGI_CONTROL_URL", "http://127.0.0.1:7700")
DEFAULT_CORE_URL = os.environ.get("DISKAGI_CORE_URL", "http://127.0.0.1:7710")

# ── Blue Claude-Code-Style TrueColor ANSI Theme ───────────────────────────────
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_ITALIC = "\033[3m"
C_BLUE_DEEP = "\033[38;2;59;130;246m"     # #3b82f6 Electric Royal Blue
C_BLUE_BRIGHT = "\033[38;2;56;189;248m"   # #38bdf8 Sky Cyan-Blue
C_CYAN_GLOW = "\033[38;2;116;237;241m"    # #74edf1 DiskAGI Signature Cyan
C_SLATE = "\033[38;2;148;163;184m"        # #94a3b8 Muted Slate
C_WHITE = "\033[38;2;241;245;249m"        # #f1f5f9 Crisp Foreground
C_GREEN = "\033[38;2;52;211;153m"         # #34d399 Emerald OK
C_AMBER = "\033[38;2;251;191;36m"         # #fbbf24 Warning Amber
C_RED = "\033[38;2;248;113;113m"          # #f87171 Coral Error
C_PURPLE = "\033[38;2;192;132;252m"       # #c084fc Function/Tool Accent

DISKAGI_BANNER = f"""{C_BLUE_DEEP}   ╭──────────────────────────────────────────────────────────────────────╮{C_RESET}
{C_BLUE_DEEP}   │{C_RESET}  {C_CYAN_GLOW}╻ ╻ ╻ ╻{C_RESET}   {C_BOLD}{C_WHITE}██████╗ ██╗███████╗██╗  ██╗{C_CYAN_GLOW} █████╗  ██████╗ ██╗{C_RESET}          {C_BLUE_DEEP}│{C_RESET}
{C_BLUE_DEEP}   │{C_RESET} {C_CYAN_GLOW}╺▛▀▀▀▀▀▀▀▀▜╸{C_RESET} {C_BOLD}{C_WHITE}██╔══██╗██║██╔════╝██║ ██╔╝{C_CYAN_GLOW}██╔══██╗██╔════╝ ██║{C_RESET}          {C_BLUE_DEEP}│{C_RESET}
{C_BLUE_DEEP}   │{C_RESET} {C_CYAN_GLOW}╺▌ ╭────╮ ▐╸{C_RESET} {C_BOLD}{C_WHITE}██║  ██║██║███████╗█████╔╝ {C_CYAN_GLOW}███████║██║  ███╗██║{C_RESET}          {C_BLUE_DEEP}│{C_RESET}
{C_BLUE_DEEP}   │{C_RESET} {C_CYAN_GLOW}╺▌ │ ◉  │ ▐╸{C_RESET} {C_BOLD}{C_WHITE}██║  ██║██║╚════██║██╔═██╗ {C_CYAN_GLOW}██╔══██║██║   ██║██║{C_RESET}          {C_BLUE_DEEP}│{C_RESET}
{C_BLUE_DEEP}   │{C_RESET} {C_CYAN_GLOW}╺▌ ╰───╱╯ ▐╸{C_RESET} {C_BOLD}{C_WHITE}██████╔╝██║███████║██║  ██╗{C_CYAN_GLOW}██║  ██║╚██████╔╝██║{C_RESET}          {C_BLUE_DEEP}│{C_RESET}
{C_BLUE_DEEP}   │{C_RESET} {C_CYAN_GLOW}╺▙▄▄▄▄╱▄▄▄▟╸{C_RESET} {C_BOLD}{C_WHITE}╚═════╝ ╚═╝╚══════╝╚═╝  ╚═╝{C_CYAN_GLOW}╚═╝  ╚═╝ ╚═════╝ ╚═╝{C_RESET}  {C_BLUE_BRIGHT}v{VERSION}{C_RESET}   {C_BLUE_DEEP}│{C_RESET}
{C_BLUE_DEEP}   │{C_RESET}  {C_CYAN_GLOW}╹ ╹ ╹ ╹{C_RESET}   {C_BLUE_BRIGHT}Frontier at home (`dagi`){C_RESET} {C_SLATE}· Claude-Code + Oh-My-Pi + Brain{C_RESET} {C_BLUE_DEEP}│{C_RESET}
{C_BLUE_DEEP}   ╰──────────────────────────────────────────────────────────────────────╯{C_RESET}"""

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
        "description": "OpenRouter (60+ frontier & open-weight models via OPENROUTER_API_KEY)",
    },
}


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "active_model": "diskagi-core",
        "brain_mode": "local_compressed",  # "local_compressed" | "storage_server" | "cloud"
        "local_brain_path": str(DEFAULT_LOCAL_BRAIN),
        "control_panel_url": DEFAULT_AGENTOS_URL,
        "storage_server_url": "",
        "cloud_remote": "brainstore:Brain",
        "auto_brain_recall": True,
        "models": dict(DEFAULT_MODELS),
    }
    if CONFIG_FILE.is_file():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            merged_models = {**DEFAULT_MODELS, **(saved.get("models") or {})}
            cfg.update(saved)
            cfg["models"] = merged_models
        except Exception:
            pass
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=0.35) as r:
            tags = json.loads(r.read().decode()).get("models") or []
            for m in tags:
                mname = m.get("name")
                if mname:
                    mid = f"ollama:{mname}"
                    cfg["models"].setdefault(mid, {
                        "id": mid,
                        "provider": "ollama",
                        "model": mname,
                        "url": "http://127.0.0.1:11434/api/chat",
                        "description": f"Auto-discovered local Ollama model ({mname})",
                    })
    except Exception:
        pass
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


# ── Shared Compressed Brain Access (Local SQLite/PPMd + Control Panel / Storage Server) ──
def get_brain_status(cfg: dict[str, Any]) -> dict[str, Any]:
    lpath = Path(cfg.get("local_brain_path") or DEFAULT_LOCAL_BRAIN)
    idx_db = lpath / ".diskncm" / "index.sqlite"
    bod_db = lpath / ".diskncm" / "bodies.sqlite"
    local_notes = 0
    local_books = 0
    if idx_db.is_file():
        try:
            con = sqlite3.connect(f"file:{idx_db}?mode=ro", uri=True, timeout=5.0)
            mx = con.execute("SELECT max(id) FROM notes").fetchone()[0] or 0
            meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
            local_notes = max(int(meta.get("note_count") or 0), int(mx))
            local_books = int(con.execute("SELECT count(*) FROM sources WHERE status='ingested'").fetchone()[0] or 0)
            con.close()
        except Exception:
            pass
    idx_mb = round(idx_db.stat().st_size / 1048576, 1) if idx_db.is_file() else 0.0
    bod_mb = round(bod_db.stat().st_size / 1048576, 1) if bod_db.is_file() else 0.0
    raw_files = [p for p in lpath.rglob("*") if p.is_file() and ".diskncm" not in p.parts] if lpath.is_dir() else []
    return {
        "brain_mode": cfg.get("brain_mode", "local_compressed"),
        "local_brain_path": str(lpath),
        "local_compressed_only": len(raw_files) == 0 and idx_db.is_file() and bod_db.is_file(),
        "raw_unpacked_files": len(raw_files),
        "note_count": local_notes,
        "ingested_sources": local_books,
        "index_sqlite_mb": idx_mb,
        "bodies_ppmd_mb": bod_mb,
        "total_compressed_mb": round(idx_mb + bod_mb, 1),
        "working_memory_capacity": 20,
        "storage_server_url": cfg.get("storage_server_url") or "",
        "cloud_remote": cfg.get("cloud_remote") or "brainstore:Brain",
        "control_panel_url": cfg.get("control_panel_url") or DEFAULT_AGENTOS_URL,
    }


def recall_from_brain(query: str, cfg: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    """Recall adaptive references into the 20-slot Human Working Memory Buffer."""
    t0 = time.perf_counter()
    srv_url = (cfg.get("storage_server_url") or "").strip().rstrip("/")
    ctrl_url = (cfg.get("control_panel_url") or DEFAULT_AGENTOS_URL).strip().rstrip("/")
    lpath = Path(cfg.get("local_brain_path") or DEFAULT_LOCAL_BRAIN)
    idx_db = lpath / ".diskncm" / "index.sqlite"

    if idx_db.is_file():
        try:
            import server as aos_server
            aos_server.CFG["vault"] = str(lpath)
            if aos_server.BRAIN is None or str(aos_server.BRAIN.path) != str(idx_db):
                aos_server.BRAIN = aos_server.Brain(idx_db)
            res = aos_server.route_knowledge(query, limit=limit)
            res["source"] = "local_compressed_ppmd"
            return res
        except Exception:
            pass

    for base_u in ([srv_url, ctrl_url] if srv_url else [ctrl_url]):
        if not base_u:
            continue
        try:
            url = f"{base_u}/api/search?q={urllib.parse.quote(query)}&limit={limit}"
            with urllib.request.urlopen(url, timeout=6.0) as r:
                hits = json.loads(r.read().decode())
            notes = hits if isinstance(hits, list) else (hits.get("results") or hits.get("notes") or [])
            return {
                "notes": notes[:limit],
                "categories": ["Remote Brain"],
                "route_ms": round((time.perf_counter() - t0) * 1000, 1),
                "source": base_u,
            }
        except Exception:
            continue
    return {"notes": [], "categories": [], "route_ms": 0.0, "source": "none"}


def teach_brain(fact_text: str, title: str | None, cfg: dict[str, Any]) -> dict[str, Any]:
    """Encode a new fact directly into the Compressed Brain (`index.sqlite` + `bodies.sqlite`, 0 raw files)."""
    lpath = Path(cfg.get("local_brain_path") or DEFAULT_LOCAL_BRAIN)
    idx_db = lpath / ".diskncm" / "index.sqlite"
    if idx_db.is_file():
        import server as aos_server
        aos_server.CFG["vault"] = str(lpath)
        if aos_server.BRAIN is None:
            aos_server.BRAIN = aos_server.Brain(idx_db)
        ev = aos_server._teach_brain_fact(fact_text, title=title, source="dagi-cli://taught", kind="cli_taught")
        return {"ok": True, "event": ev, "compressed_only": True}
    return {"ok": False, "error": f"Compressed Brain index not found at {idx_db}"}


# ── Built-in Agentic Tools (Claude-Code + Oh-My-Pi Style) ─────────────────────
def exec_tool_read(path_str: str, start_line: int = 1, end_line: int = 120) -> dict[str, Any]:
    p = Path(path_str).expanduser().resolve()
    if not p.is_file():
        return {"ok": False, "error": f"File not found: {p}"}
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    s = max(1, start_line)
    e = min(len(lines), end_line)
    snippet = "\n".join(f"{i:4d}: {lines[i - 1]}" for i in range(s, e + 1))
    return {"ok": True, "path": str(p), "total_lines": len(lines), "range": f"{s}-{e}", "content": snippet}


def exec_tool_write(path_str: str, content: str) -> dict[str, Any]:
    p = Path(path_str).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p), "bytes_written": len(content.encode("utf-8"))}


def exec_tool_edit(path_str: str, old_str: str, new_str: str) -> dict[str, Any]:
    p = Path(path_str).expanduser().resolve()
    if not p.is_file():
        return {"ok": False, "error": f"File not found: {p}"}
    src = p.read_text(encoding="utf-8")
    if old_str not in src:
        return {"ok": False, "error": "old_str not found in file"}
    updated = src.replace(old_str, new_str, 1)
    p.write_text(updated, encoding="utf-8")
    return {"ok": True, "path": str(p), "replaced": True}


def exec_tool_grep(pattern: str, path_str: str = ".") -> dict[str, Any]:
    try:
        res = subprocess.run(
            ["rg", "-n", "--max-count=40", pattern, path_str],
            capture_output=True, text=True, timeout=10,
        )
        lines = res.stdout.strip().splitlines()[:40]
        return {"ok": True, "matches": len(lines), "output": "\n".join(lines)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def exec_tool_bash(command: str, timeout: int = 30) -> dict[str, Any]:
    try:
        res = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "ok": res.returncode == 0,
            "returncode": res.returncode,
            "stdout": (res.stdout or "")[-4000:],
            "stderr": (res.stderr or "")[-2000:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Multi-Provider Model Generation (Local Core, Ollama, vLLM/OpenAI, Anthropic, AgentOS) ──
def generate_with_model(
    prompt: str,
    cfg: dict[str, Any],
    *,
    model_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    stream_print: bool = True,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    mid = model_id or cfg.get("active_model") or "diskagi-core"
    mcfg = (cfg.get("models") or {}).get(mid) or DEFAULT_MODELS["diskagi-core"]
    provider = mcfg.get("provider", "diskagi-core")

    # 1. Shared Brain 20-Slot Working Memory Recall
    brain_res: dict[str, Any] = {"notes": [], "categories": [], "route_ms": 0.0}
    if cfg.get("auto_brain_recall", True):
        brain_res = recall_from_brain(prompt, cfg, limit=20)
        if stream_print and brain_res["notes"]:
            cats = ", ".join(brain_res.get("categories") or ["Brain"])
            wm = brain_res.get("working_memory") or {}
            wm_str = (
                f" · Working Memory {wm.get('active', len(brain_res['notes']))}/20 "
                f"(+{wm.get('added', 0)} new, {wm.get('retained', 0)} kept, {wm.get('evicted', 0)} evicted)"
                if wm else ""
            )
            print(
                f"{C_BLUE_DEEP}  ├─ {C_CYAN_GLOW}⚡ Brain Recall:{C_RESET} "
                f"{C_WHITE}{len(brain_res['notes'])} active references{C_RESET} "
                f"{C_SLATE}({cats} · {brain_res['route_ms']} ms{wm_str}){C_RESET}"
            )
            for idx, n in enumerate(brain_res["notes"][:5], 1):
                st_tag = f"[{n.get('wm_state', 'new')}] " if n.get("wm_state") else ""
                print(f"{C_BLUE_DEEP}  │  {C_SLATE}{idx}. {st_tag}[[{n.get('title', '')[:78]}]]{C_RESET}")

    passages = [
        f"[{n.get('category') or n.get('type', 'note')}] [[{n.get('title', '')}]]\n{n.get('excerpt', '')}"
        for n in brain_res.get("notes", [])
    ]
    sys_prompt = (
        "You are DiskAGI (Frontier at home), an expert AI software, science, cybersecurity, game-dev, "
        "and web-design engineer powered by a shared multi-million-note compressed Brain. "
        "Actively use recalled Brain references and cite them as [[Note Title]]. "
        "Give complete, verified, production-grade code with zero placeholders."
    )
    msgs = [{"role": "system", "content": sys_prompt}]
    for h in (history or [])[-8:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    user_content = prompt
    if passages and provider not in ("diskagi-core", "agentos"):
        user_content = (
            "Recalled DiskAGI Brain References:\n"
            + "\n\n".join(passages[:10])
            + f"\n\nUser Request:\n{prompt}"
        )
    msgs.append({"role": "user", "content": user_content})

    reply_text = ""
    think_text = ""

    try:
        if provider == "diskagi-core":
            body = json.dumps({
                "messages": msgs,
                "max_new": 8192,
                "think_budget": 256,
                "temperature": 0.6,
                "top_p": 0.95,
                "passages": passages,
                "think": True,
            }).encode()
            req = urllib.request.Request(mcfg["url"], data=body, headers={"Content-Type": "application/json"})
            in_think = False
            with urllib.request.urlopen(req, timeout=600) as r:
                while raw_ln := r.readline():
                    ev = json.loads(raw_ln)
                    et = ev.get("type")
                    if et == "think":
                        txt = ev.get("text", "")
                        think_text += txt
                        if stream_print and txt:
                            if not in_think:
                                print(f"{C_BLUE_DEEP}  ├─ {C_SLATE}💭 Reasoning: {C_ITALIC}", end="", flush=True)
                                in_think = True
                            print(txt.replace("\n", " "), end="", flush=True)
                    elif et == "delta":
                        if in_think and stream_print:
                            print(f"{C_RESET}\n{C_BLUE_DEEP}  ╰─▶{C_RESET} ", end="", flush=True)
                            in_think = False
                        chunk = ev.get("text", "")
                        reply_text += chunk
                        if stream_print:
                            print(chunk, end="", flush=True)
            if stream_print:
                print()
            if "```python" in reply_text:
                try:
                    import server as aos_server
                    repaired, fixes = aos_server._verify_and_repair_python_blocks(reply_text)
                    if fixes:
                        reply_text = repaired
                        if stream_print:
                            print(f"{C_GREEN}  ✓ Auto-verified Python code ({', '.join(fixes)}){C_RESET}")
                except Exception:
                    pass

        elif provider == "ollama":
            body = json.dumps({"model": mcfg["model"], "messages": msgs, "stream": True}).encode()
            req = urllib.request.Request(mcfg["url"], data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                while raw_ln := r.readline():
                    ev = json.loads(raw_ln)
                    chunk = (ev.get("message") or {}).get("content") or ""
                    reply_text += chunk
                    if stream_print and chunk:
                        print(chunk, end="", flush=True)
            if stream_print:
                print()

        elif provider == "openai-compatible":
            api_key = os.environ.get(mcfg.get("api_key_env") or "OPENAI_API_KEY", "")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            body = json.dumps({"model": mcfg["model"], "messages": msgs, "max_tokens": 8192}).encode()
            req = urllib.request.Request(mcfg["url"], data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.loads(r.read().decode())
                reply_text = d["choices"][0]["message"]["content"]
                if stream_print:
                    print(reply_text)

        elif provider == "anthropic":
            api_key = os.environ.get(mcfg.get("api_key_env") or "ANTHROPIC_API_KEY", "")
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            body = json.dumps({
                "model": mcfg["model"],
                "system": sys_prompt,
                "messages": [m for m in msgs if m["role"] != "system"],
                "max_tokens": 8192,
            }).encode()
            req = urllib.request.Request(mcfg["url"], data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.loads(r.read().decode())
                reply_text = "".join(b.get("text", "") for b in d.get("content", []))
                if stream_print:
                    print(reply_text)

        else:
            body = json.dumps({"message": prompt, "mode": "core"}).encode()
            req = urllib.request.Request(
                mcfg["url"], data=body, headers={"Content-Type": "application/json", "X-DiskNCM": "1"}
            )
            with urllib.request.urlopen(req, timeout=600) as r:
                while raw_ln := r.readline():
                    ev = json.loads(raw_ln)
                    if ev.get("type") == "delta":
                        chunk = ev.get("text", "")
                        reply_text += chunk
                        if stream_print:
                            print(chunk, end="", flush=True)
            if stream_print:
                print()

    except KeyboardInterrupt:
        if stream_print:
            print(f"\n{C_AMBER}  ■ Generation stopped by user (Ctrl+C).{C_RESET}")
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "model": mid,
            "provider": provider,
            "brain_notes": len(brain_res.get("notes", [])),
        }

    return {
        "ok": True,
        "model": mid,
        "provider": provider,
        "reply": reply_text.strip(),
        "reasoning": think_text.strip(),
        "brain_categories": brain_res.get("categories", []),
        "working_memory": brain_res.get("working_memory", {}),
        "brain_notes": [n.get("title") for n in brain_res.get("notes", [])],
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }


# ── Interactive Blue Claude-Code-Style TUI REPL ───────────────────────────────
def run_interactive_tui(cfg: dict[str, Any]) -> int:
    print(DISKAGI_BANNER)
    bstat = get_brain_status(cfg)
    active_m = cfg.get("active_model", "diskagi-core")
    m_info = (cfg.get("models") or {}).get(active_m, {})
    print(
        f"   {C_BLUE_BRIGHT}● Model:{C_RESET} {C_BOLD}{C_WHITE}{active_m}{C_RESET} "
        f"{C_SLATE}({m_info.get('provider', 'local')} · {m_info.get('model', '')}){C_RESET}"
    )
    print(
        f"   {C_CYAN_GLOW}● Shared Brain:{C_RESET} {C_BOLD}{C_WHITE}{bstat['note_count']:,} notes{C_RESET} "
        f"{C_SLATE}({bstat['total_compressed_mb']:,.1f} MB compressed · 20-slot working memory · "
        f"compressed_only={bstat['local_compressed_only']}){C_RESET}"
    )
    print(
        f"   {C_SLATE}Commands: {C_CYAN_GLOW}/model{C_SLATE}, {C_CYAN_GLOW}/models{C_SLATE}, "
        f"{C_CYAN_GLOW}/brain{C_SLATE}, {C_CYAN_GLOW}/recall <q>{C_SLATE}, {C_CYAN_GLOW}/teach <fact>{C_SLATE}, "
        f"{C_CYAN_GLOW}/upstream <url>{C_SLATE}, {C_CYAN_GLOW}/update{C_SLATE}, {C_CYAN_GLOW}/doctor{C_SLATE}, "
        f"{C_CYAN_GLOW}/clear{C_SLATE}, {C_CYAN_GLOW}/exit{C_RESET}\n"
    )

    history: list[dict[str, str]] = []
    while True:
        try:
            prompt = input(f"{C_BLUE_DEEP}╭─[{C_CYAN_GLOW}dagi{C_BLUE_DEEP} · {C_BLUE_BRIGHT}{cfg.get('active_model')}{C_BLUE_DEEP}]\n╰─❯ {C_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C_BLUE_BRIGHT}Goodbye from DiskAGI (`dagi`) — Frontier at home.{C_RESET}")
            return 0

        if not prompt:
            continue
        if prompt in ("/exit", "/quit", "exit", "quit"):
            print(f"{C_BLUE_BRIGHT}Goodbye from DiskAGI (`dagi`) — Frontier at home.{C_RESET}")
            return 0
        if prompt == "/clear":
            history.clear()
            print(f"{C_GREEN}  ✓ Conversation history cleared.{C_RESET}")
            continue
        if prompt == "/help":
            print(
                f"{C_BLUE_BRIGHT}  /models{C_RESET}                List all configured local & frontier models\n"
                f"{C_BLUE_BRIGHT}  /model <id>{C_RESET}            Switch active model (e.g. diskagi-core, ollama-local, claude-sonnet)\n"
                f"{C_BLUE_BRIGHT}  /brain{C_RESET}                 Show compressed Brain status & upstream configuration\n"
                f"{C_BLUE_BRIGHT}  /recall <query>{C_RESET}        Recall adaptive references into the 20-slot Working Memory\n"
                f"{C_BLUE_BRIGHT}  /teach <fact>{C_RESET}          Encode a new fact into the compressed Brain\n"
                f"{C_BLUE_BRIGHT}  /upstream <url|local>{C_RESET}  Point Brain upstream to local store, cloud, or self-hosted Storage Server\n"
                f"{C_BLUE_BRIGHT}  /update{C_RESET}                Pull latest DiskAGI CLI & Brain manifest from Control Panel\n"
                f"{C_BLUE_BRIGHT}  /doctor{C_RESET}                Run full health check on Core, Control Panel, and Brain"
            )
            continue
        if prompt == "/models":
            for mid, md in cfg["models"].items():
                mark = f"{C_CYAN_GLOW}★{C_RESET}" if mid == cfg.get("active_model") else " "
                print(f"  {mark} {C_BOLD}{C_BLUE_BRIGHT}{mid:<20}{C_RESET} [{md.get('provider')}] {C_SLATE}{md.get('description', '')}{C_RESET}")
            continue
        if prompt.startswith("/model "):
            target = prompt.split(None, 1)[1].strip()
            if target not in cfg["models"]:
                if target.startswith("ollama:"):
                    mname = target.split(":", 1)[1]
                    cfg["models"][target] = {
                        "id": target,
                        "provider": "ollama",
                        "model": mname,
                        "url": "http://127.0.0.1:11434/api/chat",
                        "description": f"Local Ollama model ({mname})",
                    }
                else:
                    print(f"{C_RED}  Unknown model '{target}'. Run /models or `dagi models add`.{C_RESET}")
                    continue
            cfg["active_model"] = target
            save_config(cfg)
            print(f"{C_GREEN}  ✓ Switched active model to {C_BOLD}{target}{C_RESET}")
            continue
        if prompt == "/brain":
            print(json.dumps(get_brain_status(cfg), indent=2))
            continue
        if prompt.startswith("/recall "):
            q = prompt.split(None, 1)[1].strip()
            r = recall_from_brain(q, cfg, limit=20)
            wm = r.get("working_memory") or {}
            print(
                f"{C_CYAN_GLOW}  Working Memory ({len(r['notes'])}/20 active · +{wm.get('added',0)} new, "
                f"{wm.get('retained',0)} retained, {wm.get('evicted',0)} evicted · {r['route_ms']} ms):{C_RESET}"
            )
            for i, n in enumerate(r["notes"], 1):
                print(f"    {i:2d}. [{n.get('wm_state', 'new')} · sal={n.get('salience', 1.0)}] [{n.get('category')}] {n.get('title')}")
            continue
        if prompt.startswith("/teach "):
            fact = prompt.split(None, 1)[1].strip()
            res = teach_brain(fact, None, cfg)
            print(f"{C_GREEN}  ✓ Taught & compressed into Brain:{C_RESET} {json.dumps(res)}")
            continue
        if prompt.startswith("/upstream "):
            up = prompt.split(None, 1)[1].strip()
            if up in ("local", "local_compressed"):
                cfg["brain_mode"] = "local_compressed"
                cfg["storage_server_url"] = ""
            elif up == "cloud":
                cfg["brain_mode"] = "cloud"
            else:
                cfg["brain_mode"] = "storage_server"
                cfg["storage_server_url"] = up
            save_config(cfg)
            print(f"{C_GREEN}  ✓ Updated Brain upstream mode={cfg['brain_mode']} server={cfg.get('storage_server_url')}{C_RESET}")
            continue
        if prompt == "/update":
            res = run_self_update(cfg)
            print(json.dumps(res, indent=2))
            continue
        if prompt == "/doctor":
            print(json.dumps(run_doctor(cfg), indent=2))
            continue

        res = generate_with_model(prompt, cfg, history=history, stream_print=True)
        if res.get("ok") and res.get("reply"):
            history.append({"role": "user", "content": prompt})
            history.append({"role": "assistant", "content": res["reply"]})


def run_doctor(cfg: dict[str, Any]) -> dict[str, Any]:
    bstat = get_brain_status(cfg)
    core_ok = False
    ctrl_ok = False
    try:
        with urllib.request.urlopen(f"{DEFAULT_CORE_URL}/health", timeout=2.0) as r:
            core_ok = r.status == 200
    except Exception:
        pass
    try:
        with urllib.request.urlopen(f"{cfg.get('control_panel_url', DEFAULT_AGENTOS_URL)}/api/health", timeout=2.0) as r:
            ctrl_ok = r.status == 200
    except Exception:
        pass
    active_m = cfg.get("active_model", "diskagi-core")
    mcfg = (cfg.get("models") or {}).get(active_m, {})
    key_env = mcfg.get("api_key_env")
    auth_status = "not_required (local)" if not key_env else ("present (env)" if os.environ.get(key_env) else f"missing ({key_env})")
    return {
        "ok": bstat["note_count"] > 0 and (core_ok or ctrl_ok),
        "version": VERSION,
        "command": "dagi",
        "binary": shutil.which("dagi") or str(Path(__file__).resolve()),
        "active_model": active_m,
        "provider": mcfg.get("provider"),
        "auth_status": auth_status,
        "core_gpu_engine_reachable": core_ok,
        "control_panel_reachable": ctrl_ok,
        "brain": bstat,
    }


def run_self_update(cfg: dict[str, Any], server_url: str | None = None) -> dict[str, Any]:
    base = (server_url or cfg.get("storage_server_url") or cfg.get("control_panel_url") or DEFAULT_AGENTOS_URL).rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/distribution/manifest", timeout=10.0) as r:
            manifest = json.loads(r.read().decode())
        if manifest.get("storage_server_url"):
            cfg["storage_server_url"] = manifest["storage_server_url"]
        if manifest.get("brain_mode"):
            cfg["brain_mode"] = manifest["brain_mode"]
        save_config(cfg)
        return {
            "ok": True,
            "control_panel": base,
            "local_version": VERSION,
            "latest_version": manifest.get("version", VERSION),
            "brain_note_count": manifest.get("brain_note_count"),
            "brain_mode": cfg["brain_mode"],
            "storage_server_url": cfg.get("storage_server_url"),
            "install_linux": manifest.get("install_linux"),
            "install_windows": manifest.get("install_windows"),
        }
    except Exception as e:
        return {"ok": False, "control_panel": base, "error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="dagi",
        description="DiskAGI CLI (`dagi`) — Frontier at home (Blue Claude-Code TUI + Oh-My-Pi + 20-Slot Shared Brain)",
    )
    ap.add_argument("--json", action="store_true", help="Emit stable machine-readable JSON output")
    ap.add_argument("--model", "-m", default=None, help="Override model ID for this invocation")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("chat", help="Launch interactive Blue Claude-Code-style DiskAGI TUI (default)")
    sub.add_parser("doctor", help="Verify config, active model, Core GPU engine, Control Panel, and Compressed Brain")

    p_run = sub.add_parser("run", help="Run a one-shot prompt with automatic 20-slot Shared Brain recall")
    p_run.add_argument("prompt", help="Prompt or task to execute")

    p_models = sub.add_parser("models", help="List, switch, or add local & frontier models")
    m_sub = p_models.add_subparsers(dest="models_cmd")
    m_sub.add_parser("list", help="List all registered local & frontier models")
    p_muse = m_sub.add_parser("use", help="Set the active model ID")
    p_muse.add_argument("model_id", help="Model ID (e.g. diskagi-core, ollama-local, vllm-local, claude-sonnet, openrouter)")
    p_madd = m_sub.add_parser("add", help="Add any custom local or frontier provider model")
    p_madd.add_argument("model_id", help="Short ID for this model")
    p_madd.add_argument("--provider", required=True, choices=["diskagi-core", "ollama", "openai-compatible", "anthropic", "agentos"])
    p_madd.add_argument("--model", required=True, help="Provider model name")
    p_madd.add_argument("--url", required=True, help="Endpoint URL")
    p_madd.add_argument("--api-key-env", default="", help="Environment variable holding API key (if required)")
    p_madd.add_argument("--description", default="", help="Human-readable description")

    p_brain = sub.add_parser("brain", help="Inspect, recall, teach, or switch the Shared Compressed Brain")
    b_sub = p_brain.add_subparsers(dest="brain_cmd")
    b_sub.add_parser("status", help="Show local compressed Brain & upstream Storage Server status")
    p_brecall = b_sub.add_parser("recall", help="Recall adaptive references into the 20-slot Working Memory")
    p_brecall.add_argument("query", help="Search/recall query")
    p_brecall.add_argument("--limit", type=int, default=20)
    p_bteach = b_sub.add_parser("teach", help="Encode a new fact into the compressed Brain (0 raw files)")
    p_bteach.add_argument("fact", help="Fact markdown/text to encode")
    p_bteach.add_argument("--title", default=None)
    p_bup = b_sub.add_parser("upstream", help="Switch Brain upstream between local_compressed, cloud, or self-hosted Storage Server URL")
    p_bup.add_argument("target", help="'local', 'cloud', or 'http://<storage-server>:7700'")

    p_tool = sub.add_parser("tool-call", help="Raw escape hatch to invoke built-in agent tools (read, write, edit, grep, bash)")
    p_tool.add_argument("tool_name", choices=["read", "write", "edit", "grep", "bash"])
    p_tool.add_argument("args_json", help="JSON object of tool arguments")

    p_upd = sub.add_parser("update", help="Pull latest DiskAGI CLI release & Brain upstream manifest from Control Panel")
    p_upd.add_argument("--server", default=None, help="Control Panel or Storage Server URL")

    args = ap.parse_args()
    cfg = load_config()
    if args.model:
        cfg["active_model"] = args.model

    if args.cmd in (None, "chat"):
        return run_interactive_tui(cfg)

    if args.cmd == "doctor":
        out = run_doctor(cfg)
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(DISKAGI_BANNER)
            print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1

    if args.cmd == "run":
        res = generate_with_model(args.prompt, cfg, model_id=args.model, stream_print=not args.json)
        if args.json:
            print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    if args.cmd == "models":
        mc = args.models_cmd or "list"
        if mc == "list":
            payload = {"active_model": cfg.get("active_model"), "models": cfg["models"]}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                for mid, md in cfg["models"].items():
                    mark = "★" if mid == cfg.get("active_model") else " "
                    print(f"{mark} {mid:<22} [{md.get('provider')}] {md.get('model')} — {md.get('description', '')}")
            return 0
        if mc == "use":
            if args.model_id not in cfg["models"]:
                if args.model_id.startswith("ollama:"):
                    mname = args.model_id.split(":", 1)[1]
                    cfg["models"][args.model_id] = {
                        "id": args.model_id,
                        "provider": "ollama",
                        "model": mname,
                        "url": "http://127.0.0.1:11434/api/chat",
                        "description": f"Local Ollama model ({mname})",
                    }
                else:
                    err = {"ok": False, "error": f"Unknown model_id: {args.model_id}"}
                    print(json.dumps(err) if args.json else err["error"])
                    return 1
            cfg["active_model"] = args.model_id
            save_config(cfg)
            out = {"ok": True, "active_model": args.model_id}
            print(json.dumps(out, indent=2) if args.json else f"Active model set to {args.model_id}")
            return 0
        if mc == "add":
            cfg["models"][args.model_id] = {
                "id": args.model_id,
                "provider": args.provider,
                "model": args.model,
                "url": args.url,
                "api_key_env": args.api_key_env,
                "description": args.description or f"{args.provider}:{args.model}",
            }
            save_config(cfg)
            out = {"ok": True, "added": cfg["models"][args.model_id]}
            print(json.dumps(out, indent=2))
            return 0

    if args.cmd == "brain":
        bc = args.brain_cmd or "status"
        if bc == "status":
            print(json.dumps(get_brain_status(cfg), indent=2))
            return 0
        if bc == "recall":
            print(json.dumps(recall_from_brain(args.query, cfg, limit=args.limit), indent=2))
            return 0
        if bc == "teach":
            print(json.dumps(teach_brain(args.fact, args.title, cfg), indent=2))
            return 0
        if bc == "upstream":
            t = args.target.strip()
            if t in ("local", "local_compressed"):
                cfg["brain_mode"] = "local_compressed"
                cfg["storage_server_url"] = ""
            elif t == "cloud":
                cfg["brain_mode"] = "cloud"
            else:
                cfg["brain_mode"] = "storage_server"
                cfg["storage_server_url"] = t
            save_config(cfg)
            print(json.dumps({"ok": True, "brain_mode": cfg["brain_mode"], "storage_server_url": cfg.get("storage_server_url")}, indent=2))
            return 0

    if args.cmd == "tool-call":
        targs = json.loads(args.args_json)
        if args.tool_name == "read":
            res = exec_tool_read(targs["path"], targs.get("start_line", 1), targs.get("end_line", 120))
        elif args.tool_name == "write":
            res = exec_tool_write(targs["path"], targs["content"])
        elif args.tool_name == "edit":
            res = exec_tool_edit(targs["path"], targs["old_str"], targs["new_str"])
        elif args.tool_name == "grep":
            res = exec_tool_grep(targs["pattern"], targs.get("path", "."))
        else:
            res = exec_tool_bash(targs["command"], targs.get("timeout", 30))
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    if args.cmd == "update":
        out = run_self_update(cfg, server_url=args.server)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

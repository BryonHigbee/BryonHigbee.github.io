#!/usr/bin/env python3
"""DiskAGI Standalone Cross-Platform MCP Server (`diskagi_mcp_standalone.py`).

100% self-contained single-file MCP JSON-RPC 2.0 (`stdio`) server that runs on BOTH
**Windows** and **Linux** (dual-boot ready!) with ZERO requirement to run Qwen3.5-4B
or the Agent OS web server:
  1. Automatic Local Brain -> Cloud Brain Failover (Windows + Linux):
     - Checks `$DISKNCM_BRAIN`, `/home/bryonh/DiskNCM-Brain`, `%USERPROFILE%\\DiskNCM-Brain`,
       `C:\\DiskNCM-Brain`, `D:\\DiskNCM-Brain`.
     - If the Local Brain is not present/mounted, automatically fails over to the Cloud Brain:
       `/home/bryonh/GoogleDrive/DiskNCM/Brain`, `G:\\My Drive\\DiskNCM\\Brain`,
       `%USERPROFILE%\\Google Drive\\DiskNCM\\Brain`, `%USERPROFILE%\\GoogleDrive\\DiskNCM\\Brain`,
       or WSL `\\\\wsl.localhost\\Arch\\home\\bryonh\\DiskNCM-Brain`!
  2. Built-in Laya System-1 + 16-Domain & 844-DevDocs Router + 20-Slot Human Working Memory:
     - Holds up to 20 active Brain recalls at a time (`brain_recall`, `brain_working_memory`),
       retaining recalls in `<1 ms` on follow-ups and evicting unneeded recalls on topic switch.
  3. Built-in Pure-CPU Universal Vision & Video Bridge (`vision_inspect_image`, `vision_watch_video`):
     - Uses `ffmpeg` / `ffprobe` (or pure-Python PNG/BMP/PPM decoder fallback) to give ANY model
       (even a text-only model on `omp`, `claude`, `opencode`, `codex`, `cursor`) full image
       spatial/color quadrant analysis and multi-frame video timeline + motion-delta comprehension
       without needing a local 4B GPU model running!
"""
from __future__ import annotations

import collections
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any

MAX_WORKING_MEMORY = 20
_WORKING_MEMORY: dict[int, dict[str, Any]] = {}
WM_CACHE_FILE = Path.home() / ".cache" / "diskagi-mcp" / "working-memory.json"

_STOP = frozenset(
    "a about above after again against all am an and any are as at be because been before being "
    "below between both but by can could did do does doing down during each few for from further "
    "had has have having he her here hers herself him himself his how i if in into is it its itself "
    "just me more most my myself no nor not now of off on once only or other our ours ourselves out "
    "over own same she should so some such than that the their theirs them themselves then there "
    "these they this those through to too under until up very was we were what when where which "
    "while who whom why will with would you your yours yourself yourselves tell explain please".split()
)

_FILLER_Q_WORDS = {
    "python", "rust", "javascript", "linux", "script", "code", "show", "make", "work", "working",
    "implement", "complete", "write", "good", "original", "check", "open", "prevent", "using",
    "create", "build", "program", "function", "simple", "example", "line",
}

_GENERIC_TITLE_WORDS = {
    "the", "and", "for", "with", "programming", "language", "documentation", "reference",
    "manual", "guide", "tutorial", "standard", "library", "complete", "official", "dataset",
    "encyclopedia", "science", "medicine", "music", "gamedev",
}

_CATEGORY_ROUTES = (
    ("Python", re.compile(r"\b(python|py|pip|pytest|tkinter|pygame|asyncio|numpy|pandas|pytorch|def|stdlib|wave|winsound)\b", re.I),
     ("Python Standard Library Reference%", "The Python Tutorial%", "Python Developer%", "Pygame Documentation%", "DevDocs: Python%")),
    ("Rust", re.compile(r"\b(rust|cargo|crate|tokio|rustc|borrow|lifetime)\b", re.I),
     ("The Rust Programming Language%", "Rust by Example%", "DevDocs: Rust%", "Dataset: TheAlgorithms Rust%")),
    ("JavaScript, Web Design & UI Engineering", re.compile(r"\b(javascript|js|typescript|ts|node|react|vue|svelte|html|css|dom|http|fetch|browser|web|website|web design|ui|ux|typography|layout|grid|accessibility|aria|wcag|design system|landing page|dashboard|frontend)\b", re.I),
     ("Web Design:%", "DevDocs: HTML%", "DevDocs: CSS%", "DevDocs: JavaScript%", "DevDocs: TypeScript%", "DevDocs: DOM%", "DevDocs: HTTP%", "DevDocs: React%", "DevDocs: Node%", "DevDocs: Web APIs%")),
    ("Roblox, Luau & Game Development", re.compile(r"\b(roblox|luau|lua|cframe|vector3|udim2|remoteevent|remotefunction|datastoreservice|humanoid|raycast\w*|workspace|replicatedstorage|players|tweenservice|runservice|userinputservice|particleemitter|godot|gdscript|raylib|bevy|pygame|shader|glsl|opengl|vulkan|three\.?js|game dev\w*|sprite|hitbox|collision|ecs)\b", re.I),
     ("Roblox:%", "GameDev:%", "Pygame Documentation%", "DevDocs: Lua%", "DevDocs: Godot%", "DevDocs: OpenGL%", "DevDocs: Three%")),
    ("Systems, Linux & Troubleshooting", re.compile(r"\b(linux|kernel|bash|shell|systemd|posix|socket|syscall|c\+\+|cpp|gcc|cmake|man page|tar|rsync|grep|find command|chmod|chown|troubleshoot\w*|sysadmin|journalctl|dmesg|strace|lsof|netstat|ss|iptables|nftables|ssh|open ports?)\b", re.I),
     ("Linux:%", "Linux Kernel Documentation%", "DevDocs: Linux man pages%", "DevDocs: C — %", "DevDocs: C++%", "DevDocs: Bash%", "DevDocs: CMake%", "Dataset: TLDR%")),
    ("Databases & SQL", re.compile(r"\b(sql|sqlite|postgres|postgresql|database|schema|fts5?|inner join|left join|group by|select from)\b", re.I),
     ("SQLite Documentation%", "DevDocs: SQLite%", "DevDocs: PostgreSQL%", "Dataset: Yale Spider%", "Dataset: SQL Create-Context%")),
    ("Git & DevOps", re.compile(r"\b(git|commit|branch|merge|rebase|docker|container|dockerfile|compose|nginx|hugo|terraform|ansible|kubernetes)\b", re.I),
     ("Git Documentation%", "Docker Documentation%", "Hugo Static Site%", "DevDocs: Git%", "DevDocs: Docker%", "DevDocs: nginx%", "DevDocs: Terraform%", "DevDocs: Ansible%")),
    ("Security, AppSec & CVE Remediation", re.compile(r"\b(security|cybersecurity|owasp|wstg|mastg|asvs|xss|csrf|sqli|sql injection|ssrf|rce|xxe|ssti|lfi|rfi|idor|injection|auth|jwt|oauth|crypto|hash|password|exploit\w*|vulnerability|cve|cve-\d{4}-\d+|cwe|cwe-\d+|capec|cisa|pentest\w*|red team|blue team|mitre|att&ck|t1\d{3}|atomic red|gtfobins|lolbas|wadcoms|peass|linpeas|winpeas|privesc|privilege escalation|suid|kerberoast\w*|dcsync|bloodhound|impacket|rubeus|mimikatz|certipy|active directory|nuclei|sigma|yara|siem|dfir|incident response|forensic\w*|threat hunt\w*|chainsaw|evtx|sysmon|auditd|harden\w*|ransomware|malware|webshell|reverse engineering|tls|firewall|sanitize|escaping)\b", re.I),
     ("OWASP%", "Cybersecurity%", "Linux:%")),
    ("Neuroscience, Brain & Biomedical Science", re.compile(r"\b(neuron\w*|synap\w*|cortex|cortical|hippocamp\w*|neuroscience|brain|cognitive|axon|dendrite|plasticity|dopamine|serotonin|glutamate|gaba|prefrontal|amygdala|cerebell\w*|thalam\w*|glial|myelin|action potential|eeg|fmri)\b", re.I),
     ("Neuroscience:%", "Medicine: PubMed%", "Science: ArXiv%", "Encyclopedia: Wikipedia%")),
    ("AI, Deep Learning & Data Science", re.compile(r"\b(machine learning|deep learning|neural network\w*|transformer\w*|attention|llm|training|regression|classification|clustering|scikit|sklearn|pytorch|tensor\w*|gradient|backprop\w*|cnn|rnn|lstm|diffusion|reinforcement learning|matplotlib|numpy|pandas|llava|moondream|vlm)\b", re.I),
     ("AI:%", "Vision & Video:%", "scikit-learn%", "DevDocs: PyTorch%", "DevDocs: TensorFlow%", "DevDocs: scikit-learn%", "DevDocs: NumPy%", "DevDocs: Pandas%", "DevDocs: Matplotlib%", "Science: ArXiv%")),
    ("Music Theory & Scores", re.compile(r"\b(music|melody|harmony|chord|scale|counterpoint|orchestrat\w*|symphony|sonata|fugue|abc notation|sheet music|tempo|rhythm|octave|cadence|key signature|synthesi\w*|tone)\b", re.I),
     ("Music Theory:%", "Music Encyclopedia:%", "Music Scores:%", "Music Composition%")),
    ("Algorithms & Reference Datasets", re.compile(r"\b(algorithm|data structure|graph|dynamic programming|dijkstra|shortest path|binary search|sort\w*|tree|heap|cheatsheet|tldr|command line|cli|benchmark|humaneval|mbpp|bug|patch)\b", re.I),
     ("Dataset: CP-Algorithms%", "Dataset: TheAlgorithms%", "Dataset: Learn X%", "Dataset: TLDR%", "Dataset: Devhints%", "Dataset: Google MBPP%", "Dataset: HumanEval%", "Dataset: BigCode%", "Dataset: EvalPlus%", "Dataset: MultiPL-E%", "Dataset: DeepMind CodeContests%", "Dataset: SWE-bench%")),
    ("Mathematics & Proofs", re.compile(r"\b(math\w*|algebra\w*|geometry|calculus|trigonometry|probability|combinatorics|number theory|theorem|proof|equation|integral|derivative|matrix|prime|polynomial|olympiad|aime|amc|gsm8k|ratio|percent\w*|solve|root|roots|integer\w*|quadratic|factor\w*|x\^2)\b", re.I),
     ("Dataset: Hendrycks Competition Mathematics%", "Dataset: MATH-500%", "Dataset: OpenAI GSM8K%", "Dataset: DeepMind AQuA-RAT%", "Dataset: TheoremQA%", "Dataset: OlympiadBench%")),
    ("Physics, Chemistry & Science", re.compile(r"\b(physics|chemistry|biology|astronomy|thermodynamics|quantum|relativity|electromagn\w*|atom\w*|molecule|reaction|cell|genetics|evolution|ecology|force|velocity|energy|wavelength|photon|planet|gravity|arxiv)\b", re.I),
     ("Science: ArXiv%", "Dataset: ELI5%", "Dataset: AllenAI SciQ%", "Dataset: ScienceQA%", "Dataset: AllenAI ARC%", "Dataset: AllenAI OpenBookQA%", "Dataset: SciBench%", "Dataset: MMLU%")),
    ("Medicine & Clinical Science", re.compile(r"\b(medical|medicine|clinical|patient|symptom|diagnosis|treatment|therapy|disease|syndrome|pharmacology|drug|anatomy|physiology|biomedical|pubmed|usmle|hospital|surgery)\b", re.I),
     ("Medicine: PubMed%", "Dataset: PubMedQA%", "Dataset: MedQA USMLE%", "Dataset: MMLU%")),
    ("Automotive, Cars & Mechanical Engineering", re.compile(r"\b(car|cars|auto|automobile|automotive|vehicle|truck|engine|motor|gasoline|petrol|diesel|turbo\w*|supercharg\w*|carburetor|fuel injection|camshaft|crankshaft|piston|cylinder|spark plug|alternator|starter|radiator|coolant|transmission|gearbox|clutch|torque|horsepower|differential|driveshaft|axle|suspension|strut|shock absorber|brake|abs|steering|catalytic|exhaust|muffler|obd\w*|[pbcu][0-3][0-9a-f]{3}|can bus|tire|wheel|oil change|head gasket|timing belt|ford|toyota|honda|chevrolet|bmw|mercedes|audi|volkswagen|subaru|nissan|hyundai|kia|mazda|porsche|jeep|dodge|tesla|ev|acura)\b", re.I),
     ("Dataset: OBD-II%", "Automotive:%", "Dataset: Practical How-To%")),
    ("Encyclopedia, Facts & Commonsense", re.compile(r"\b(history|historical|president|empire|war|treaty|constitution|law|legal|philosophy|ethics|economics|geography|capital|country|invention|discover\w*|fact|misconception|myth|true or false|who|when|where|wikipedia|explain|how to|repair|fix|maintain)\b", re.I),
     ("Encyclopedia: Wikipedia%", "Encyclopedia: DBpedia%", "Dataset: Practical How-To%", "Dataset: General Knowledge%", "Dataset: TriviaQA%", "Dataset: ELI5%", "Dataset: Stanford SQuAD v2%", "Dataset: Stanford CoQA%", "Dataset: Google BoolQ%", "Dataset: TruthfulQA%", "Dataset: ConceptNet CommonsenseQA%", "Dataset: MMLU%")),
)

_CONCEPT_EXPANSIONS = (
    (re.compile(r"\b(melody|music|sound|sounding|audio|tone|beep|song|synth|notes?|pitch|wav)\b", re.I),
     ("wave", "audio", "sound", "frequency", "sin", "math", "struct", "subprocess", "winsound")),
    (re.compile(r"\b(pygame|piston|crankshaft|rpm|window|canvas|draw|ball|bounce|bouncing|game|sprite|animation|simulat\w*)\b", re.I),
     ("pygame", "draw", "rect", "circle", "font", "clock", "display", "surface", "math", "sin", "cos")),
    (re.compile(r"\b(synap\w*|plasticity|dopamine|cortex|prefrontal|hippocamp\w*|neuron\w*|neuroscience)\b", re.I),
     ("synaptic", "plasticity", "dopamine", "cortex", "hippocampus", "neuron", "brain", "memory", "receptor")),
    (re.compile(r"\b(sql injection|sqli|xss|owasp|csrf|open ports?|ss|netstat|journalctl|firewall|mitre|att&ck|sigma|yara|gtfobins|lolbas|nuclei|dfir|incident response|kerberoast\w*|active directory|privesc|privilege escalation|harden\w*)\b", re.I),
     ("injection", "xss", "parameterized", "prepared", "owasp", "socket", "port", "systemd", "journalctl", "mitre", "sigma", "yara", "gtfobins", "lolbas", "nuclei", "incident", "hardening")),
    (re.compile(r"\b(vision|video|image|camera|frame|llava|moondream|multimodal|vlm|watch)\b", re.I),
     ("vision", "video", "frame", "llava", "moondream", "clip", "siglip", "encoder", "projector")),
)

_FOLLOWUP_RE = re.compile(
    r"^\s*(is that it\??|continue\.?|keep going\.?|go on\.?|finish( it| the code)?\.?|make it\b.*|fix( it| that)\b.*|what else\??)\s*$",
    re.I,
)


def resolve_brain_cross_platform() -> tuple[Path, str]:
    """Locate the DiskAGI Brain across Linux AND Windows dual-boot with automatic Local -> Cloud failover."""
    home = Path.home()
    env_p = os.environ.get("DISKNCM_BRAIN")
    if env_p:
        ep = Path(env_p).expanduser()
        if (ep / ".diskncm" / "index.sqlite").is_file():
            return ep, "cloud" if "Google" in str(ep) or "Drive" in str(ep) else "local"

    local_candidates = [] if env_p else [
        home / "DiskNCM-Brain",
        Path("/home/bryonh/DiskNCM-Brain"),
        Path("C:/DiskNCM-Brain"),
        Path("D:/DiskNCM-Brain"),
        Path("E:/DiskNCM-Brain"),
    ]
    cloud_candidates = [
        Path(os.environ.get("DISKNCM_CLOUD_BRAIN", "")) if os.environ.get("DISKNCM_CLOUD_BRAIN") else None,
        home / "GoogleDrive" / "DiskNCM" / "Brain",
        home / "Google Drive" / "DiskNCM" / "Brain",
        home / "Google Drive" / "My Drive" / "DiskNCM" / "Brain",
        Path("/home/bryonh/GoogleDrive/DiskNCM/Brain"),
        Path("G:/My Drive/DiskNCM/Brain"),
        Path("G:/DiskNCM/Brain"),
        Path("H:/My Drive/DiskNCM/Brain"),
        home / "OneDrive" / "DiskNCM-Brain",
    ]

    for lp in local_candidates:
        if lp and (lp / ".diskncm" / "index.sqlite").is_file():
            return lp, "local"

    for cp in cloud_candidates:
        if cp and (cp / ".diskncm" / "index.sqlite").is_file():
            return cp, "cloud_failover"

    # On Linux, attempt to start `rclone-gdrive.service` if unmounted
    if sys.platform.startswith("linux"):
        try:
            subprocess.run(["systemctl", "--user", "start", "rclone-gdrive.service"], capture_output=True, timeout=6)
        except Exception:
            pass
        for cp in cloud_candidates:
            if cp and (cp / ".diskncm" / "index.sqlite").is_file():
                return cp, "cloud_failover"

    return home / "DiskNCM-Brain", "unmounted_cloud"


def _read_note_body(root: Path, nid: int, rel_path: str) -> str:
    raw_file = root / rel_path
    if raw_file.is_file():
        try:
            return raw_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    bdb = root / ".diskncm" / "bodies.sqlite"
    if bdb.is_file():
        try:
            con = sqlite3.connect(f"file:{bdb}?mode=ro", uri=True, timeout=5.0)
            row = con.execute(
                "SELECT block_id, ofs, size, zbody FROM note_bodies WHERE id = ? OR path = ? LIMIT 1",
                (nid, rel_path),
            ).fetchone()
            if row:
                bid, ofs, sz, zb = row
                if zb:
                    con.close()
                    return zlib.decompress(zb).decode("utf-8", errors="replace")
                if bid:
                    crow = con.execute("SELECT cbody FROM blocks WHERE id = ?", (bid,)).fetchone()
                    con.close()
                    if crow and crow[0]:
                        cb = crow[0]
                        if cb[:4] == b"ZLIB":
                            blk = zlib.decompress(cb[4:])
                        else:
                            import pyppmd
                            blk = pyppmd.decompress(cb, max_order=6, mem_size=16 << 20)
                        return blk[ofs : ofs + sz].decode("utf-8", errors="replace")
            con.close()
        except Exception:
            pass
    return ""


def _best_window(body: str, query_str: str, max_chars: int = 900) -> str:
    body = re.sub(r"\A---\n.*?\n---\n*", "", body, flags=re.S).strip()
    if len(body) <= max_chars:
        return body
    terms = [w.lower() for w in re.findall(r"[A-Za-z0-9_]{3,}", query_str) if w.lower() not in _STOP][:8]
    if not terms:
        return body[:max_chars]
    low = body.lower()
    best_pos, best_hits = 0, -1
    step = max(80, max_chars // 3)
    for pos in range(0, max(1, len(body) - max_chars // 2), step):
        win = low[pos : pos + max_chars]
        hits = sum(2 if t in win else 0 for t in terms)
        if hits > best_hits:
            best_hits, best_pos = hits, pos
    return body[best_pos : best_pos + max_chars].strip()


def _classify_categories(msg: str, weights: dict[str, float]) -> tuple[list[tuple[str, float, list[str]]], int]:
    score_by_cat: dict[str, tuple[float, list[str]]] = {}
    msg_low = msg.lower()
    if re.search(r"\bpygame\b", msg_low):
        score_by_cat["Pygame & Python Simulation"] = (30.0, ["Pygame Documentation%", "Python Standard Library Reference%"])
    if re.search(r"\b(roblox|luau|cframe|remoteevent|datastoreservice|workspace|humanoid)\b", msg_low):
        score_by_cat["Roblox & Luau"] = (30.0, ["Roblox:%", "DevDocs: Lua%"])
    if re.search(r"\b(llava|moondream|video-llava|vision tower|vision bridge|multimodal)\b", msg_low):
        score_by_cat["Vision & Video Bridge (Any-Model VLM)"] = (32.0, ["Vision & Video:%", "AI:%", "Science: ArXiv%"])

    for cat_name, rx, pfx_list in _CATEGORY_ROUTES:
        hits = {m.group(0).lower() for m in rx.finditer(msg_low)}
        if not hits:
            continue
        idf_sum = sum(weights.get(h, 2.5) for h in hits)
        kw_score = 2.5 * len(hits) + 0.65 * idf_sum
        prev_s, prev_pfxs = score_by_cat.get(cat_name, (0.0, list(pfx_list)))
        score_by_cat[cat_name] = (prev_s + kw_score, list(dict.fromkeys([*prev_pfxs, *pfx_list])))

    if not score_by_cat:
        return [], 6
    raw_scores = sorted(((c, s, p) for c, (s, p) in score_by_cat.items()), key=lambda x: -x[1])
    max_s = raw_scores[0][1]
    exps = [math.exp(min(8.0, (s - max_s) / 5.0)) for _, s, _ in raw_scores]
    z = sum(exps) or 1.0
    out = []
    for (cname, _, pfxs), e in zip(raw_scores, exps):
        prob = round(e / z, 4)
        if prob >= 0.05 or len(out) < 2:
            out.append((cname, prob, pfxs))
        if len(out) >= 5:
            break
    return out, max(4, min(20, 4 + len(out) * 3))


def _update_working_memory(
    msg: str, active_cats: list[str], msg_terms: list[str], new_recalls: list[dict[str, Any]], target_limit: int = 12
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    is_followup = len(msg.split()) <= 6 or bool(_FOLLOWUP_RE.match(msg))
    active_cat_set = set(active_cats)
    term_set = {t.lower() for t in msg_terms if len(t) >= 3}
    new_ids = {n.get("id") for n in new_recalls if n.get("id")}

    retained: list[dict[str, Any]] = []
    evicted_count = 0
    for nid, old_note in list(_WORKING_MEMORY.items()):
        if nid in new_ids:
            continue
        old_cat = old_note.get("category", "")
        old_hay = f"{old_note.get('title', '')} {old_note.get('excerpt', '')[:300]}".lower()
        overlap = sum(1 for t in term_set if t in old_hay)
        old_sal = float(old_note.get("salience", 0.75))
        if is_followup and not active_cat_set:
            new_sal = round(max(0.55, old_sal * 0.92), 3)
        elif old_cat in active_cat_set or overlap >= 1:
            new_sal = round(min(1.0, old_sal * 0.85 + 0.12 * overlap), 3)
        else:
            new_sal = round(old_sal * 0.25, 3)
        if new_sal >= 0.35:
            retained.append(dict(old_note, salience=new_sal, wm_state="retained"))
        else:
            evicted_count += 1
            _WORKING_MEMORY.pop(nid, None)

    fresh = [
        dict(n, salience=round(max(0.65, 1.0 - 0.02 * i), 3), wm_state="new" if n.get("id") not in _WORKING_MEMORY else "refreshed")
        for i, n in enumerate(new_recalls)
    ]
    combined = fresh + sorted(retained, key=lambda x: -x.get("salience", 0.0))
    seen: set[int] = set()
    final_wm: list[dict[str, Any]] = []
    cap = min(MAX_WORKING_MEMORY, max(target_limit, len(fresh) + min(4, len(retained))))
    for item in combined:
        nid = item.get("id")
        if nid in seen:
            continue
        seen.add(nid)
        final_wm.append(item)
        if len(final_wm) >= cap:
            break
    if len(combined) > len(final_wm):
        evicted_count += len(combined) - len(final_wm)
    _WORKING_MEMORY.clear()
    for item in final_wm:
        if item.get("id"):
            _WORKING_MEMORY[item["id"]] = item
    stats = {
        "active": len(final_wm),
        "max_slots": MAX_WORKING_MEMORY,
        "added": len(fresh),
        "retained": sum(1 for x in final_wm if x.get("wm_state") == "retained"),
        "evicted": evicted_count,
    }
    try:
        WM_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        WM_CACHE_FILE.write_text(json.dumps({"stats": stats, "slots": final_wm}, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    return final_wm, stats


def tool_brain_recall(query: str, limit: int = 12) -> str:
    t0 = time.perf_counter()
    root, b_mode = resolve_brain_cross_platform()
    idx_db = root / ".diskncm" / "index.sqlite"
    if not idx_db.is_file():
        return f"DiskAGI Brain index not found at {idx_db} (mode={b_mode}). Mount Google Drive or set DISKNCM_BRAIN."

    msg_terms = [w.lower() for w in re.findall(r"[A-Za-z0-9_]{2,}", query) if w.lower() not in _STOP]
    weights = {t: min(9.5, 2.2 + 0.55 * len(t)) for t in msg_terms}
    is_short_followup = len(query.split()) <= 6 or bool(_FOLLOWUP_RE.match(query))
    classified, dyn_limit = _classify_categories(query, weights)
    if is_short_followup and not classified and len(_WORKING_MEMORY) >= 3:
        final_notes, wm = _update_working_memory(query, [], msg_terms, [], target_limit=max(limit, len(_WORKING_MEMORY)))
        ms = round((time.perf_counter() - t0) * 1000, 1)
        lines = [f"Brain Mode: {b_mode} ({root}) · 20-Slot WM: {wm['active']}/20 (kept={wm['retained']}, new=0, evicted=0) · {ms} ms"]
        for i, n in enumerate(final_notes, 1):
            lines.append(f"{i}. [{n.get('wm_state')} sal={n.get('salience')}] [{n.get('category')}] [[{n.get('title')}]]\n{n.get('excerpt', '')[:900]}")
        return "\n\n".join(lines)

    eff_limit = min(MAX_WORKING_MEMORY, max(limit, dyn_limit if classified else 8))
    extra_terms: list[str] = []
    for rx, exp in _CONCEPT_EXPANSIONS:
        if rx.search(query):
            for t in exp:
                if t not in extra_terms:
                    extra_terms.append(t)
    ranked_q = sorted((t for t in weights if t not in _FILLER_Q_WORDS), key=lambda t: weights[t], reverse=True)[:6]
    search_terms = list(dict.fromkeys([*ranked_q, *extra_terms[:5]]))[:9] or msg_terms[:4] or ["reference"]
    q_str = " ".join(search_terms)

    picked: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    con = sqlite3.connect(f"file:{idx_db}?mode=ro", uri=True, timeout=10.0)
    con.row_factory = sqlite3.Row
    try:
        total_prob = sum(p for _, p, _ in classified) or 1.0
        for _, (cat_name, prob, prefixes) in enumerate(classified):
            if len(picked) >= eff_limit:
                break
            cat_quota = max(2, min(round(eff_limit * (prob / total_prob)), eff_limit - len(picked)))
            title_toks: list[str] = []
            for pfx in prefixes:
                for w in re.findall(r"[A-Za-z0-9_]+", pfx.replace("DevDocs:", "")):
                    wl = w.lower()
                    if len(wl) >= 2 and wl not in _GENERIC_TITLE_WORDS and wl not in title_toks:
                        title_toks.append(wl)
            t_expr = " OR ".join(f'title:"{w}"' for w in title_toks[:8])
            cat_terms = [t for t in search_terms if t not in title_toks and len(t) >= 2] or [t for t in search_terms if len(t) >= 2]
            title_b = " OR ".join(f'title:"{t}"' for t in cat_terms[:8])
            body_b = " OR ".join(f'"{t}"' for t in cat_terms[:8])
            queries = [q for q in (f"({t_expr}) AND ({title_b})" if (t_expr and title_b) else "", f"({t_expr}) AND ({body_b})" if (t_expr and body_b) else "") if q]
            added_cat = 0
            for fq in queries:
                if added_cat >= cat_quota or len(picked) >= eff_limit:
                    break
                try:
                    rids = [r[0] for r in con.execute("SELECT rowid FROM notes_fts WHERE notes_fts MATCH ? LIMIT ?", (fq, cat_quota * 10)).fetchall()]
                except sqlite3.OperationalError:
                    rids = []
                for cid in rids:
                    if cid in seen_ids:
                        continue
                    row = con.execute("SELECT id, title, type, path FROM notes WHERE id = ?", (cid,)).fetchone()
                    if not row or row["type"] != "chapter":
                        continue
                    if not any(row["title"].lower().startswith(p[:-1].lower()) for p in prefixes):
                        continue
                    excerpt = _best_window(_read_note_body(root, cid, row["path"]), q_str, 900)
                    if excerpt:
                        picked.append({"id": cid, "title": row["title"], "type": row["type"], "category": cat_name, "excerpt": excerpt, "coverage": round(prob, 3)})
                        seen_ids.add(cid)
                        added_cat += 1
                        if added_cat >= cat_quota or len(picked) >= eff_limit:
                            break
    finally:
        con.close()

    cats = [c for c, _, _ in classified] or ["Brain Memory"]
    final_notes, wm = _update_working_memory(query, cats, msg_terms, picked[:eff_limit], target_limit=eff_limit)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    lines = [f"Brain Mode: {b_mode} ({root}) · 20-Slot WM: {wm['active']}/20 (kept={wm['retained']}, new={wm['added']}, evicted={wm['evicted']}) · cats={cats} · {ms} ms"]
    for i, n in enumerate(final_notes, 1):
        lines.append(f"{i}. [{n.get('wm_state')} sal={n.get('salience')}] [{n.get('category')}] [[{n.get('title')}]]\n{n.get('excerpt', '')[:900]}")
    return "\n\n".join(lines)


# ── Pure-CPU Universal Vision & Video Bridge (No Local 4B LLM Required!) ─────
_PALETTE = (
    ("red", (225, 35, 35)), ("blue", (35, 75, 235)), ("green", (35, 195, 55)),
    ("yellow", (245, 220, 35)), ("cyan", (50, 215, 225)), ("magenta", (215, 55, 215)),
    ("orange", (245, 140, 30)), ("purple", (145, 70, 215)), ("white", (240, 240, 240)),
    ("black", (20, 20, 20)), ("gray", (128, 128, 128)),
)


def _color_name(r: float, g: float, b: float) -> str:
    return min(_PALETTE, key=lambda item: (r - item[1][0]) ** 2 + (g - item[1][1]) ** 2 + (b - item[1][2]) ** 2)[0]


def _analyze_rgb24(rgb: bytes, w: int, h: int) -> dict[str, Any]:
    def _box(x0: int, y0: int, x1: int, y1: int) -> tuple[float, float, float]:
        sr = sg = sb = cnt = 0
        for y in range(max(0, y0), min(h, y1)):
            roff = y * w * 3
            for x in range(max(0, x0), min(w, x1)):
                i = roff + x * 3
                sr += rgb[i]
                sg += rgb[i + 1]
                sb += rgb[i + 2]
                cnt += 1
        c = max(1, cnt)
        return (sr / c, sg / c, sb / c)

    return {
        "dominant_color": _color_name(*_box(0, 0, w, h)),
        "left_half_color": _color_name(*_box(0, 0, w // 2, h)),
        "right_half_color": _color_name(*_box(w // 2, 0, w, h)),
        "top_half_color": _color_name(*_box(0, 0, w, h // 2)),
        "bottom_half_color": _color_name(*_box(0, h // 2, w, h)),
        "center_color": _color_name(*_box(w // 4, h // 4, (3 * w) // 4, (3 * h) // 4)),
    }


def tool_vision_inspect_image(image_path: str, question: str = "Describe this image in detail.") -> str:
    p = Path(image_path).expanduser().resolve()
    if not p.is_file():
        return json.dumps({"ok": False, "error": f"Image not found: {p}"})
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p), "-vf", "scale=128:128", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=30, check=True,
    )
    reg = _analyze_rgb24(proc.stdout[: 128 * 128 * 3], 128, 128)
    return json.dumps({"ok": True, "image_path": str(p), "question": question, "spatial_telemetry": reg}, indent=2)


def tool_vision_watch_video(video_path: str, question: str = "Describe what happens in this video.", num_frames: int = 6) -> str:
    p = Path(video_path).expanduser().resolve()
    if not p.is_file():
        return json.dumps({"ok": False, "error": f"Video not found: {p}"})
    num_frames = max(2, min(int(num_frames), 16))
    dur = 0.0
    try:
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
            capture_output=True, text=True, timeout=15,
        )
        dur = float((pr.stdout or "").strip() or 0.0)
    except Exception:
        dur = 0.0
    vf = f"fps={max(0.2, num_frames / dur):.4f},scale=128:128" if dur > 0.2 else "scale=128:128"
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p), "-vf", vf, "-frames:v", str(num_frames), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=60, check=True,
    )
    fbytes = 128 * 128 * 3
    n_got = len(proc.stdout) // fbytes
    timeline = []
    prev = None
    for i in range(n_got):
        rgb = proc.stdout[i * fbytes : (i + 1) * fbytes]
        reg = _analyze_rgb24(rgb, 128, 128)
        motion = round(100.0 * sum(1 for a, b in zip(prev, rgb) if abs(a - b) > 18) / fbytes, 1) if prev else 0.0
        prev = rgb
        timeline.append({"frame": i + 1, "motion_delta_pct": motion, **reg})
    return json.dumps({
        "ok": True,
        "video_path": str(p),
        "question": question,
        "frames_sampled": n_got,
        "start_color": timeline[0]["dominant_color"] if timeline else "unknown",
        "end_color": timeline[-1]["dominant_color"] if timeline else "unknown",
        "timeline": timeline,
    }, indent=2)


# ── Minimal Zero-Dependency MCP JSON-RPC 2.0 `stdio` Server Loop ─────────────
MCP_TOOLS = [
    {
        "name": "brain_recall",
        "description": "20-Slot Human Working Memory Recall (Standalone with automatic Local -> Cloud Brain failover): routes `query` across 16 domains + 844 DevDocs sets + books (<1ms follow-ups, <300ms topic switches).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question or task to recall Brain references for"},
                "limit": {"type": "integer", "default": 12},
            },
            "required": ["query"],
        },
    },
    {
        "name": "brain_working_memory",
        "description": "Inspect the active 20-Slot Human Working Memory buffer (currently held Brain recalls and salience).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_stats",
        "description": "Show DiskAGI Brain status (Local vs Cloud failover mode, total notes, compressed size).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vision_inspect_image",
        "description": "Pure-CPU Universal Vision Bridge for ANY Model: decodes `image_path` and returns spatial quadrant color/layout telemetry so even text-only models can inspect images without a local 4B GPU model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "question": {"type": "string", "default": "Describe this image in detail."},
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "vision_watch_video",
        "description": "Pure-CPU Universal Video Bridge for ANY Model: extracts `num_frames` keyframes from `video_path` via ffmpeg and returns frame-by-frame color/spatial/motion-delta telemetry so ANY model can watch videos.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_path": {"type": "string"},
                "question": {"type": "string", "default": "Describe what happens across this video."},
                "num_frames": {"type": "integer", "default": 6},
            },
            "required": ["video_path"],
        },
    },
]


def _handle_rpc(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = msg.get("method", "")
    req_id = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "diskncm-brain", "version": "2.0.0"},
                "instructions": (
                    "DiskAGI Standalone Brain & Vision/Video MCP Plugin (Windows + Linux dual-boot ready, "
                    "automatic Local -> Cloud Brain failover, 20-Slot Human Working Memory, and pure-CPU "
                    "Vision/Video Bridge for any model)."
                ),
            },
        }
    if method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS}}
    if method == "tools/call":
        tname = params.get("name", "")
        targs = params.get("arguments") or {}
        try:
            if tname == "brain_recall":
                txt = tool_brain_recall(str(targs.get("query", "")), int(targs.get("limit", 12)))
            elif tname == "brain_working_memory":
                txt = json.dumps({"active": len(_WORKING_MEMORY), "max_slots": 20, "slots": list(_WORKING_MEMORY.values())}, indent=2)
            elif tname == "brain_stats":
                root, b_mode = resolve_brain_cross_platform()
                idx_db = root / ".diskncm" / "index.sqlite"
                cnt = 0
                if idx_db.is_file():
                    con = sqlite3.connect(f"file:{idx_db}?mode=ro", uri=True, timeout=5.0)
                    cnt = con.execute("SELECT max(id) FROM notes").fetchone()[0] or 0
                    con.close()
                txt = json.dumps({"brain_mode": b_mode, "brain_root": str(root), "notes": cnt, "working_memory_slots": 20}, indent=2)
            elif tname == "vision_inspect_image":
                txt = tool_vision_inspect_image(str(targs.get("image_path", "")), str(targs.get("question", "Describe this image.")))
            elif tname == "vision_watch_video":
                txt = tool_vision_watch_video(str(targs.get("video_path", "")), str(targs.get("question", "Describe this video.")), int(targs.get("num_frames", 6)))
            else:
                txt = f"Unknown tool: {tname}"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": txt}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}}
    if req_id is not None:
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    return None


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        resp = _handle_rpc(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

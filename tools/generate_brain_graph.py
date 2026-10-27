#!/usr/bin/env python3
"""Generate brain.json for the DiskAGI site: a live-sampled, brain-shaped 3D graph.

Reads the local DiskNCM master index (read-only, WAL-safe) and emits:
  - meta: live note/edge/source counts + compressed bytes (the real brain size)
  - nodes: a stratified sample (high-degree hubs + deterministic stride sample),
    each with a title, 16-domain classification (the router's own categories),
    and a position ON a folded brain surface (two hemispheres, cerebellum, stem)
    that preserves cluster adjacency from the precomputed 2D layout (notes.x/y)
  - links: real edges between sampled nodes

Deterministic: same index state -> same output. Re-run whenever the brain grows:
    .venv python tools/generate_brain_graph.py   (from the site repo root)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sqlite3
import time

DEFAULT_DB = "/home/bryonh/DiskNCM-Brain/.diskncm/index.sqlite"
SAMPLE_HUBS = 1100
SAMPLE_STRIDE = 2300
LINK_CAP = 6500

# The router's own 16 domains (mirrors _CATEGORY_ROUTES in diskagi_mcp_standalone.py).
DOMAINS = (
    ("Python", r"\b(python|py|pip|pytest|tkinter|pygame|asyncio|numpy|pandas|pytorch|stdlib|winsound)\b", re.I),
    ("Rust", r"\b(rust|cargo|crate|tokio|rustc|borrow|lifetime)\b", re.I),
    ("JavaScript & Web UI", r"\b(javascript|js|typescript|ts|node|react|vue|svelte|html|css|dom|http|fetch|browser|web|website|web design|ui|ux|typography|layout|grid|accessibility|aria|wcag|frontend)\b", re.I),
    ("Roblox & Game Dev", r"\b(roblox|luau|lua|cframe|vector3|udim2|remoteevent|datastoreservice|humanoid|raycast\w*|replicatedstorage|tweenservice|runservice|godot|gdscript|raylib|bevy|shader|glsl|opengl|vulkan|three\.?js|game dev\w*|sprite|hitbox|collision|ecs)\b", re.I),
    ("Systems & Linux", r"\b(linux|kernel|bash|shell|systemd|posix|socket|syscall|c\+\+|cpp|gcc|cmake|man page|sysadmin|journalctl|dmesg|strace|iptables|nftables|ssh)\b", re.I),
    ("Databases & SQL", r"\b(sql|sqlite|postgres|postgresql|database|schema|fts5?|inner join|left join|group by)\b", re.I),
    ("Git & DevOps", r"\b(git|commit|branch|merge|rebase|docker|container|dockerfile|compose|nginx|hugo|terraform|ansible|kubernetes)\b", re.I),
    ("Security & AppSec", r"\b(security|cybersecurity|owasp|wstg|mastg|asvs|xss|csrf|sqli|sql injection|ssrf|rce|xxe|ssti|jwt|oauth|exploit\w*|vulnerability|cve|cwe|capec|cisa|pentest\w*|red team|mitre|att&ck|atomic red|gtfobins|lolbas|peass|sigma|yara|nuclei|dfir|forensic\w*|malware|ransomware|reverse engineering)\b", re.I),
    ("Neuroscience", r"\b(neuron\w*|synap\w*|cortex|cortical|hippocamp\w*|neuroscience|brain|cognitive|axon|dendrite|plasticity|dopamine|serotonin|glutamate|gaba|prefrontal|amygdala|cerebell\w*|thalam\w*|glial|myelin|action potential|eeg|fmri)\b", re.I),
    ("AI & Data Science", r"\b(machine learning|deep learning|neural network\w*|transformer\w*|attention|llm|training|regression|classification|clustering|scikit|sklearn|pytorch|tensor\w*|gradient|backprop\w*|cnn|rnn|lstm|diffusion|reinforcement learning|vlm|multimodal)\b", re.I),
    ("Music", r"\b(music|melody|harmony|chord|scale|counterpoint|orchestrat\w*|symphony|sonata|fugue|abc notation|sheet music|tempo|rhythm|octave|cadence|key signature)\b", re.I),
    ("Algorithms & Datasets", r"\b(algorithm|data structure|graph|dynamic programming|dijkstra|shortest path|binary search|sort\w*|tree|heap|cheatsheet|tldr|benchmark|humaneval|mbpp|swe-bench|code contests)\b", re.I),
    ("Mathematics", r"\b(math\w*|algebra\w*|geometry|calculus|trigonometry|probability|combinatorics|number theory|theorem|proof|equation|integral|derivative|matrix|prime|polynomial|olympiad|aime|amc|gsm8k)\b", re.I),
    ("Physics & Science", r"\b(physics|chemistry|biology|astronomy|thermodynamics|quantum|relativity|electromagn\w*|atoms?|molecule|reaction|cell|genetics|evolution|ecology|wavelength|photon|planet|gravity|arxiv)\b", re.I),
    ("Medicine", r"\b(medical|medicine|clinical|patient|symptom|diagnosis|treatment|therapy|disease|syndrome|pharmacology|drug|anatomy|physiology|biomedical|pubmed|usmle|hospital|surgery)\b", re.I),
    ("Encyclopedia & Facts", r"\b(history|historical|president|empire|war|treaty|constitution|law|legal|philosophy|ethics|economics|geography|country|invention|discover\w*|fact|misconception|myth|wikipedia|encyclopedia)\b", re.I),
)
DOMAIN_RE = [(name, re.compile(pat, flags)) for name, pat, flags in DOMAINS]
TYPE_NAMES = ("chapter", "concept", "book", "author", "news", "theme")

TITLE_STRIP = re.compile(r"^(Dataset|DevDocs|Encyclopedia|Science|Medicine|Music (Theory|Encyclopedia|Scores|Composition)|Web Design|Automotive|AI|Vision & Video|Cybersecurity|Linux|GameDev|Roblox|OWASP|Git|Docker|Hugo|Linux Kernel Documentation|Linux man pages|The Python Tutorial|Python Developer|The Rust Programming Language|Rust by Example|SQLite Documentation| scikit-learn|Music)\s*:\s*", re.I)


def domain_of(text: str) -> int:
    for i, (_, rx) in enumerate(DOMAIN_RE):
        if rx.search(text):
            return i
    return len(DOMAIN_RE)  # Other


def clean_title(t: str) -> str:
    t = TITLE_STRIP.sub("", t or "").strip() or "Untitled note"
    if len(t) > 84:
        t = t[:81].rsplit(" ", 1)[0] + "…"
    return t


# ---------------------------------------------------------------- brain shape
RNG = random.Random(42)

ANCHORS = [  # unit dirs, brain faces +z
    (0.00, 0.50, 0.86),   # prefrontal
    (-0.50, 0.72, 0.42), (-0.50, 0.72, 0.42),  # frontal L/R (dummy dup replaced below)
    (-0.35, 0.95, 0.05), (0.35, 0.95, 0.05),   # motor crown
    (-0.45, 0.78, -0.42), (0.45, 0.78, -0.42), # parietal
    (-0.40, 0.28, -0.90), (0.40, 0.28, -0.90), # occipital
    (-0.97, -0.20, 0.10), (0.97, -0.20, 0.10), # temporal L/R
    (-0.60, -0.45, 0.50), (0.60, -0.45, 0.50), # ventral L/R
    (0.00, 0.90, -0.25),                        # precuneus
]
ANCHORS[1] = (-0.50, 0.72, 0.42)
ANCHORS[2] = (0.50, 0.72, 0.42)


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _basis(a):
    up = (0.0, 1.0, 0.0) if abs(a[1]) < 0.9 else (1.0, 0.0, 0.0)
    t1 = _norm((up[1] * a[2] - up[2] * a[1], up[2] * a[0] - up[0] * a[2], up[0] * a[1] - up[1] * a[0]))
    t2 = (a[1] * t1[2] - a[2] * t1[1], a[2] * t1[0] - a[0] * t1[2], a[0] * t1[1] - a[1] * t1[0])
    return t1, t2


def fold(dirv, cerebellum=False):
    x, y, z = dirv
    t = math.acos(max(-1.0, min(1.0, y)))
    p = math.atan2(z, x)
    if cerebellum:
        f = 1 + 0.10 * math.sin(9 * t) * math.sin(11 * p) + 0.05 * math.sin(17 * p + 3 * t)
    else:
        f = (1 + 0.075 * math.sin(5 * t + 2 * math.sin(3 * p))
             + 0.05 * math.sin(7 * p + 1.5 * t)
             + 0.03 * math.sin(11 * p - 2 * t))
    return f


def cortex_point(anchor_dir, frac, angle, spread=0.62, interior=False, cerebellum=False):
    """Point at `frac` (0..1) around a region cone, folded onto the brain surface."""
    r = spread * math.sqrt(frac)
    t1, t2 = _basis(anchor_dir)
    cr, sr = math.cos(r), math.sin(r)
    ca, sa = math.cos(angle), math.sin(angle)
    d = (
        cr * anchor_dir[0] + sr * (ca * t1[0] + sa * t2[0]),
        cr * anchor_dir[1] + sr * (ca * t1[1] + sa * t2[1]),
        cr * anchor_dir[2] + sr * (ca * t1[2] + sa * t2[2]),
    )
    d = _norm(d)
    if interior:
        depth = RNG.uniform(0.30, 0.72)
        f = 1.0
    else:
        depth = RNG.uniform(0.94, 1.0)
        f = fold(d, cerebellum)
    if cerebellum:
        c = (0.0, -0.60, -0.72)
        s = (0.50, 0.34, 0.40)
    else:
        c = (0.0, 0.02, 0.0)
        s = (1.12, 0.88, 1.00)
    x, y, z = (d[0] * f * s[0] * depth + c[0], d[1] * f * s[1] * depth + c[1], d[2] * f * s[2] * depth + c[2])
    if not cerebellum and abs(x) < 0.055:  # longitudinal fissure
        x = 0.055 * (1 if x >= 0 else -1)
    return (x, y, z)


def stem_point(frac):
    a = RNG.uniform(0, math.tau)
    rad = 0.10 * (0.6 + 0.4 * RNG.random())
    return (rad * math.cos(a), -0.45 - 0.62 * frac, -0.38 + 0.16 * frac + rad * math.sin(a) * 0.4)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out", default="brain.json")
    args = ap.parse_args()

    t0 = time.time()
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=60.0)
    cur = db.cursor()
    meta = dict(cur.execute("SELECT key, value FROM meta"))
    notes_total = int(meta.get("note_count") or cur.execute("SELECT COUNT(*) FROM notes").fetchone()[0])
    edges_total = int(meta.get("edge_count") or cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0])
    sources_total = cur.execute("SELECT COUNT(*) FROM sources").fetchone()[0]

    # sources: source_id -> corpus title (the router's ground truth for domains)
    src_title = {
        sid: (title or "")
        for sid, title in cur.execute("SELECT id, title FROM sources")
    }

    # --- sample nodes: hubs first, then a deterministic stride sample
    hub_rows = cur.execute(
        "SELECT id, title, type, source_id, degree, cluster, x, y FROM notes ORDER BY degree DESC LIMIT ?",
        (SAMPLE_HUBS,),
    ).fetchall()
    max_id = cur.execute("SELECT COALESCE(MAX(id), 1) FROM notes").fetchone()[0]
    stride = max(1, max_id // SAMPLE_STRIDE)
    stride_rows = cur.execute(
        "SELECT id, title, type, source_id, degree, cluster, x, y FROM notes WHERE id % ? = 0 LIMIT ?",
        (stride, SAMPLE_STRIDE),
    ).fetchall()

    seen, rows = set(), []
    for r in hub_rows + stride_rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        rows.append(r)
    rows.sort(key=lambda r: r[0])  # ingest order -> growth reveal

    # cluster packing: big sampled clusters claim region anchors; nodes keep (x,y) order in-cluster
    by_cluster: dict[int, list] = {}
    for r in rows:
        by_cluster.setdefault(r[5] if r[5] is not None else -1, []).append(r)
    clusters = sorted(by_cluster.items(), key=lambda kv: -len(kv[1]))
    cluster_anchor = {}
    for i, (cid, members) in enumerate(clusters):
        cluster_anchor[cid] = ANCHORS[i % len(ANCHORS)]

    idx_of = {}
    nodes = []
    domain_counts = [0] * (len(DOMAIN_RE) + 1)
    type_counts = {}
    for pos, r in enumerate(rows):
        nid, title, ntype, src, deg, cid, px, py = r
        corpus = src_title.get(src, "")
        d = domain_of(f"{corpus} {title}")
        domain_counts[d] += 1
        tidx = TYPE_NAMES.index(ntype) if ntype in TYPE_NAMES else 1
        type_counts[ntype] = type_counts.get(ntype, 0) + 1

        members = by_cluster[cid if cid is not None else -1]
        anchor = cluster_anchor[cid if cid is not None else -1]
        frac = ((pos * 2654435761) % 1000) / 1000.0  # golden-ratio hash -> even cone spread
        angle = pos * 2.399963  # golden angle
        roll = RNG.random()
        if roll < 0.012:
            p = stem_point(frac)
        elif roll < 0.082:
            p = cortex_point((0.0, -0.55, -0.82), frac, angle, spread=1.1, cerebellum=True)
        elif roll < 0.20:
            p = cortex_point(anchor, frac, angle, interior=True)
        else:
            p = cortex_point(anchor, frac, angle)
        idx_of[nid] = len(nodes)
        nodes.append([nid, clean_title(title), d, tidx, int(deg or 0), round(p[0], 4), round(p[1], 4), round(p[2], 4)])

    # --- links: real edges between sampled nodes
    keep = idx_of.keys()
    links = []
    for src, dst, kind in cur.execute("SELECT src, dst, kind FROM edges"):
        a, b = idx_of.get(src), idx_of.get(dst)
        if a is None or b is None or a == b:
            continue
        links.append([a, b, 0 if kind == "mentions" else (1 if kind == "contains" else 2)])
        if len(links) >= LINK_CAP:
            break
    db.close()

    # compressed brain bytes on disk (the "size" the site quotes)
    machine = os.path.dirname(args.db)
    brain_bytes = 0
    for f in os.listdir(machine):
        if f.startswith(("index.sqlite", "bodies.sqlite", "corpus.sqlite")):
            brain_bytes += os.path.getsize(os.path.join(machine, f))

    out = {
        "meta": {
            "project": "DiskAGI",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "notes": notes_total,
            "edges": edges_total,
            "sources": sources_total,
            "bytes": brain_bytes,
            "sampled_nodes": len(nodes),
            "sampled_links": len(links),
            "build_seconds": round(time.time() - t0, 2),
            "layout": "folded-brain-v1 (cluster-preserving)",
        },
        "domains": [{"name": n, "count": c} for (n, _, _), c in zip(DOMAINS, domain_counts[:-1])]
        + [{"name": "Other", "count": domain_counts[-1]}],
        "types": type_counts,
        "nodes": nodes,
        "links": links,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(
        f"brain.json: {len(nodes):,} nodes / {len(links):,} links sampled from {notes_total:,} notes "
        f"({edges_total:,} edges, {sources_total:,} sources, {brain_bytes / 1e9:.2f} GB) "
        f"in {time.time() - t0:.1f}s -> {args.out} ({os.path.getsize(args.out) / 1024:.0f} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# src/texprep/io/discover.py
from __future__ import annotations
from pathlib import Path
import re
from typing import List, Tuple

MAGIC_ROOT = re.compile(r"^\s*%+\s*!TEX\s+root\s*=\s*(?P<root>[^\s]+)", re.I | re.M)
SUBFILES   = re.compile(r"\\documentclass\[(?P<main>[^]\s]+)\]\{subfiles\}")

NAME_HINTS = {"main.tex", "paper.tex", "root.tex", "ms.tex"}

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def signals(path: Path, text: str) -> dict:
    return {
        "documentclass": ("\\documentclass" in text),
        "begin_document": ("\\begin{document}" in text),
        "title_or_author": ("\\title{" in text or "\\author{" in text),
        "name_hint": (path.name.lower() in NAME_HINTS),
        "depth": len(path.parts),
        "magic_root": bool(MAGIC_ROOT.search(text)),
        "subfiles": bool(SUBFILES.search(text)),
    }

def score_from_signals(sig: dict) -> int:
    score = 0
    if sig["documentclass"]:   score += 20
    if sig["begin_document"]:  score += 40
    if sig["title_or_author"]: score += 10
    if sig["name_hint"]:       score += 50
    score += max(0, 20 - sig["depth"])  # 얕을수록 가산
    return score

def follow_magic_root(root: Path, p: Path, text: str) -> Path | None:
    m = MAGIC_ROOT.search(text)
    if not m:
        return None
    cand = (p.parent / m.group("root")).resolve()
    if cand.exists():
        return cand
    alt = (root / m.group("root")).resolve()
    return alt if alt.exists() else None

def follow_subfiles(p: Path, text: str) -> Path | None:
    m = SUBFILES.search(text)
    if not m:
        return None
    cand = (p.parent / m.group("main")).resolve()
    return cand if cand.exists() else None

def rank_candidates(root_dir: str) -> Tuple[Path, List[Tuple[int, Path, dict]]]:
    """
    루트 디렉토리에서 main .tex 후보를 찾아 점수화한 리스트 반환
    """
    root = Path(root_dir).resolve()
    cands = list(root.rglob("*.tex"))
    if not cands:
        raise FileNotFoundError(f".tex 없음: {root}")

    # magic root / subfiles 우선 처리
    specials = []
    for p in cands:
        t = read_text(p)
        if m := follow_magic_root(root, p, t):
            sig = signals(m, read_text(m))
            s = score_from_signals(sig)
            return m, [(s, m, sig)]
        if s := follow_subfiles(p, t):
            specials.append(s)
    if specials:
        scored = []
        seen = set()
        for m in specials:
            if m in seen:
                continue
            seen.add(m)
            sig = signals(m, read_text(m))
            s = score_from_signals(sig)
            scored.append((s, m, sig))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1], scored

    # 점수 기반 랭킹
    scored = []
    for p in cands:
        t = read_text(p)
        sig = signals(p, t)
        s = score_from_signals(sig)
        scored.append((s, p, sig))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1], scored

def guess_main(root_dir: str) -> str:
    """
    루트 디렉토리에서 가장 유력한 main.tex 경로 반환
    """
    best, _ = rank_candidates(root_dir)
    return str(best)

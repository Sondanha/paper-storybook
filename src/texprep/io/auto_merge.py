# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Any
import re, hashlib

from src.texprep.tex.expander import expand_file
from src.texprep.tex.strip import preclean_for_body, clean_text

DOCCLASS_RE = re.compile(r"\\documentclass\b", re.I)
BEGIN_DOC_RE = re.compile(r"\\begin\{document\}", re.I)


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except:
        return p.read_text(encoding="latin-1", errors="ignore")


def find_root_candidates(root_dir: str) -> list[Path]:
    """
    root_dir 안의 .tex 파일 중 documentclass 혹은 begin{document}가 있는 파일을 루트 후보로 선정
    """
    root = Path(root_dir).resolve()
    cands: set[Path] = set()
    for p in root.rglob("*.tex"):
        s = _read(p)
        if DOCCLASS_RE.search(s) or BEGIN_DOC_RE.search(s):
            cands.add(p.resolve())
    return sorted(cands)


def _score_name(p: Path) -> int:
    name = p.name.lower()
    pos = ("main", "paper", "camera", "arxiv", "acl", "iclr", "neurips", "emnlp")
    neg = ("supp", "appendix", "gen", "generation", "demo", "draft")
    sc = 0
    for k in pos:
        if k in name:
            sc += 5
    for k in neg:
        if k in name:
            sc -= 4
    sc += max(0, 6 - len(p.parts))  # 얕은 경로 선호
    return sc


def expand_to_body_clean(p: Path, drop_envs: list[str]) -> str:
    raw, _ = expand_file(str(p))
    body = preclean_for_body(raw)  # 본문만
    body = clean_text(body, drop_env_list=tuple(drop_envs), also_drop_inline_todos=True)
    return body.strip()


def _norm_para(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _paras(text: str) -> list[str]:
    return [t for t in re.split(r"\n\s*\n", text) if t.strip()]


def _para_hash(s: str) -> str:
    return hashlib.sha1(_norm_para(s).encode("utf-8")).hexdigest()


def fingerprint(text: str) -> tuple[list[str], set[str]]:
    paras = _paras(text)
    hs = {_para_hash(p) for p in paras}
    return paras, hs


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def group_near_duplicates(bodies: list[dict[str, Any]], threshold: float = 0.8) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for x in bodies:
        placed = False
        for g in groups:
            if jaccard(x["para_hashes"], g[0]["para_hashes"]) >= threshold:
                g.append(x)
                placed = True
                break
        if not placed:
            groups.append([x])
    return groups


def choose_best(group: list[dict[str, Any]]) -> dict[str, Any]:
    return max(group, key=lambda r: (len(r["text"]), r["name_score"]))


def merge_unique(bests: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    if not bests:
        return "", []
    bests = sorted(bests, key=lambda r: (-r["name_score"], -len(r["text"])))
    main = bests[0]
    used = set(main["para_hashes"])
    merged = list(_paras(main["text"]))
    provenance = [{"para_index": i, "source": str(main["path"]), "hash": _para_hash(p)} for i, p in enumerate(merged)]

    for b in bests[1:]:
        src_paras = _paras(b["text"])
        for p in src_paras:
            h = _para_hash(p)
            if h in used:
                continue
            used.add(h)
            provenance.append({"para_index": len(merged), "source": str(b["path"]), "hash": h})
            merged.append(p)
    return "\n\n".join(merged), provenance


def auto_merge_corpus(root_dir: str, drop_envs: list[str]) -> dict[str, Any]:
    cands = find_root_candidates(root_dir)
    bodies: list[dict[str, Any]] = []
    for p in cands:
        t = expand_to_body_clean(p, drop_envs)
        if not t:
            continue
        paras, hs = fingerprint(t)
        bodies.append({
            "path": p,
            "text": t,
            "para_hashes": hs,
            "name_score": _score_name(p),
        })

    if not bodies:
        return {"text": "", "provenance": [], "roots": []}

    groups = group_near_duplicates(bodies, threshold=0.8)
    bests = [choose_best(g) for g in groups]
    merged_text, prov = merge_unique(bests)

    return {
        "text": merged_text,
        "provenance": prov,
        "roots": [str(b["path"]) for b in bests],
    }

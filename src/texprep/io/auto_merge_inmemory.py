# src/texprep/io/auto_merge_inmemory.py
"""
In-memory auto-merge
- dict[str,str]로 받은 TeX 소스를 확장/정리 후 유사문단 제거 병합
"""

import re
import hashlib

from src.texprep.tex.expander_inmemory import expand_string_inmemory
from src.texprep.tex.strip import preclean_for_body, clean_text

_DOCCLASS_RE = re.compile(r"\\documentclass\b", re.I)
_BEGIN_DOC_RE = re.compile(r"\\begin\{document\}", re.I)

_POS_HINTS = ("main", "paper", "camera", "arxiv", "acl", "iclr", "neurips", "emnlp", "root", "ms")
_NEG_HINTS = ("supp", "appendix", "gen", "generation", "demo", "draft")

def _name_depth(name: str) -> int:
    return len([p for p in name.split("/") if p])

def _score_name(name: str) -> int:
    lo = name.lower()
    sc = 0
    for k in _POS_HINTS:
        if k in lo:
            sc += 5
    for k in _NEG_HINTS:
        if k in lo:
            sc -= 4
    sc += max(0, 6 - _name_depth(name))
    return sc

def _norm_para(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _split_paras(text: str) -> list[str]:
    return [t for t in re.split(r"\n\s*\n", text) if t.strip()]

def _para_hash(s: str) -> str:
    return hashlib.sha1(_norm_para(s).encode("utf-8")).hexdigest()

def fingerprint(text: str) -> tuple[list[str], set[str]]:
    paras = _split_paras(text)
    hs = {_para_hash(p) for p in paras}
    return paras, hs

def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def group_near_duplicates(bodies: list[dict], threshold: float = 0.8) -> list[list[dict]]:
    groups: list[list[dict]] = []
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

def choose_best(group: list[dict]) -> dict:
    return max(group, key=lambda r: (len(r["text"]), r["name_score"]))

def merge_unique(bests: list[dict]) -> tuple[str, list[dict]]:
    if not bests:
        return "", []
    bests = sorted(bests, key=lambda r: (-r["name_score"], -len(r["text"])))
    main = bests[0]
    used = set(main["para_hashes"])
    merged = list(_split_paras(main["text"]))
    provenance = [{"para_index": i, "source": str(main["path"]), "hash": _para_hash(p)} for i, p in enumerate(merged)]

    for b in bests[1:]:
        src_paras = _split_paras(b["text"])
        for p in src_paras:
            h = _para_hash(p)
            if h in used:
                continue
            used.add(h)
            provenance.append({"para_index": len(merged), "source": str(b["path"]), "hash": h})
            merged.append(p)
    return "\n\n".join(merged), provenance

def _is_root_candidate(name: str, text: str) -> bool:
    return bool(_DOCCLASS_RE.search(text) or _BEGIN_DOC_RE.search(text))

def auto_merge_corpus_inmemory(tex_files: dict[str, str], drop_envs: list[str]) -> dict:
    """
    tex_files: { "dir/main.tex": "...", ... }
    반환: { "text": merged_text, "provenance": [...], "roots": [names...] }
    """
    bodies: list[dict] = []

    for name, text in tex_files.items():
        if not _is_root_candidate(name, text):
            continue

        # 확장
        expanded, _ = expand_string_inmemory(text, filename=name, all_files=tex_files)
        # 본문 + 클린
        body = preclean_for_body(expanded)
        body = clean_text(body, drop_env_list=tuple(drop_envs), also_drop_inline_todos=True)
        body = body.strip()
        if not body:
            continue

        _, hs = fingerprint(body)
        bodies.append({
            "path": name,
            "text": body,
            "para_hashes": hs,
            "name_score": _score_name(name),
        })

    if not bodies:
        return {"text": "", "provenance": [], "roots": []}

    groups = group_near_duplicates(bodies, threshold=0.8)
    bests = [choose_best(g) for g in groups]
    merged_text, prov = merge_unique(bests)

    return {
        "text": merged_text,
        "provenance": prov,
        "roots": [b["path"] for b in bests],
    }

# src/texprep/tex/expander_inmemory.py
"""
In-memory TeX expander
- \input, \include, \InputIfFileExists 지원
- 파일 대신 dict[str, str]로 동작
- 보호 환경(mask) 처리
"""

import re
from typing import Iterable

INPUT_CMDS = (r"\input", r"\include")
PROTECT_ENVS = ("verbatim", "Verbatim", "lstlisting", "lstlisting*", "minted", "tikzpicture")
_PROTECT_TOKEN = "§§PROTECT_BLOCK_{}§§"
_VERB_INLINE_RE = re.compile(r"""\\verb\*?(?P<d>[^A-Za-z0-9\s])(?P<body>.*?)(?P=d)""")
_INPUT_RE = re.compile(rf"(?:{'|'.join(map(re.escape, INPUT_CMDS))})\{{([^}}]+)\}}")
_IF_EXISTS_RE = re.compile(r"\\InputIfFileExists\{([^}]+)\}\{([^}]*)\}\{([^}]*)\}", re.S)

def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

def _dirname_like(name: str) -> str:
    return name.rsplit("/", 1)[0] if "/" in name else ""

def _join_like(base: str, child: str) -> str:
    if child.startswith("/"):
        return child.lstrip("/")
    if not base:
        return child
    return f"{base.rstrip('/')}/{child}"

def _mask_inline_verbs(text: str):
    out = text
    masked = []
    i = 0
    while True:
        m = _VERB_INLINE_RE.search(out)
        if not m:
            break
        tok = f"§§PROTECT_VERB_{i}§§"
        masked.append((tok, m.group(0)))
        out = out[:m.start()] + tok + out[m.end():]
        i += 1
    return out, masked

def _mask_protect_envs(text: str, envs: Iterable[str]):
    out = text
    masked = []
    for env in envs:
        pat = re.compile(rf"\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}", re.S)
        while True:
            m = pat.search(out)
            if not m:
                break
            tok = _PROTECT_TOKEN.format(len(masked))
            masked.append((tok, m.group(0)))
            out = out[:m.start()] + tok + out[m.end():]
    return out, masked

def _unmask(text: str, masked_pairs):
    out = text
    for tok, block in masked_pairs:
        out = out.replace(tok, block)
    return out

def _resolve_candidates_inmemory(base_file: str, target: str, all_files: dict[str, str]) -> list[str]:
    """
    base_file 기준으로 target, target.tex 후보를 dict 키에서 찾는다.
    """
    target = target.strip()
    cand = []
    # 상대 경로 처리
    base_dir = _dirname_like(base_file)
    for t in (target, (target if target.endswith(".tex") else f"{target}.tex")):
        for key in (
            _join_like(base_dir, t),  # 상대
            t,                        # 딱 키로 적힌 경우
        ):
            if key in all_files and key not in cand:
                cand.append(key)
    return cand

def expand_string_inmemory(
    text: str,
    filename: str,
    all_files: dict[str, str],
    *,
    max_depth: int = 20,
):
    """
    문자열 입력을 메모리 dict 기반으로 확장한다.
    반환: (expanded_text, deps[list[str]])
    """
    text = _normalize_newlines(text)
    visited: set[str] = {filename}
    deps: list[str] = [filename]

    # 보호 마스크 적용
    masked_text, masked_envs = _mask_protect_envs(text, PROTECT_ENVS)
    masked_text, masked_verbs = _mask_inline_verbs(masked_text)

    cur = masked_text
    depth = 0
    while depth < max_depth:
        changed = False

        # \input / \include
        def repl_simple(m: re.Match) -> str:
            nonlocal changed
            target = m.group(1)
            cands = _resolve_candidates_inmemory(filename, target, all_files)
            if not cands:
                return m.group(0)
            key = cands[0]
            if key in visited:
                return ""  # 사이클 방지
            visited.add(key)
            changed = True
            content = _normalize_newlines(all_files[key])
            expanded, _ = expand_string_inmemory(content, key, all_files, max_depth=max_depth)
            if key not in deps:
                deps.append(key)
            return expanded

        cur2 = _INPUT_RE.sub(repl_simple, cur)

        # \InputIfFileExists{file}{then}{else}
        def repl_if(m: re.Match) -> str:
            nonlocal changed
            fname, then_part, else_part = m.group(1), m.group(2), m.group(3)
            cands = _resolve_candidates_inmemory(filename, fname, all_files)
            if cands:
                changed = True
                # then_part 안에도 포함이 있을 수 있으니 재귀 처리
                expanded_then, _ = expand_string_inmemory(then_part, filename, all_files, max_depth=max_depth)
                return expanded_then
            return else_part

        cur3 = _IF_EXISTS_RE.sub(repl_if, cur2)

        if cur3 == cur:
            break
        cur = cur3
        depth += 1

    if depth >= max_depth:
        cur = "% WARNING: max expansion depth reached\n" + cur

    # 마스크 복원
    cur = _unmask(cur, masked_envs)
    cur = _unmask(cur, masked_verbs)
    return cur, deps

# src/texprep/tex/strip.py


"""
코멘트/불필요 환경 제거 + 프리앰블 정리

권장 사용 순서:
  preclean_for_body()  ->  clean_text()
"""

from __future__ import annotations
import re
from typing import Iterable

__all__ = [
    "normalize_newlines",
    "extract_document_body",
    "drop_setup_blocks",
    "drop_noise_commands",
    "strip_comments",
    "drop_envs",
    "drop_inline_commands",
    "drop_after_markers",
    "clean_text",
    "preclean_for_body",
]

# 보호할 환경(안은 그대로 보존)
PROTECT_ENVS_DEFAULT = (
    "verbatim", "Verbatim", "lstlisting", "lstlisting*",
    "minted", "tikzpicture",
)

# \verb 인라인 보호
VERB_INLINE_RE = re.compile(
    r"""\\verb\*?(?P<delim>[^A-Za-z0-9\s])(?P<body>.*?)(?P=delim)"""
)
_PROTECT_BLOCK = "§§PROTECT_BLOCK_{}§§"
_PROTECT_VERB  = "§§PROTECT_VERB_{}§§"


def normalize_newlines(text: str) -> str:
    """윈도우/맥 개행을 LF로 통일"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_document_body(text: str) -> str:
    """\\begin{document} .. \\end{document} 사이만 추출. 없으면 원문 유지"""
    m = re.search(r"\\begin\{document\}(.*)\\end\{document\}", text, re.S)
    return m.group(1) if m else text


def drop_setup_blocks(text: str) -> str:
    """프리앰블 설정 블록 제거"""
    patterns = [
        r"\\lstdefinelanguage\{[^}]+\}\s*\{.*?\}",
        r"\\lstset\{.*?\}",
        r"\\makeatletter.*?\\makeatother",
    ]
    out = text
    for pat in patterns:
        out = re.sub(pat, "", out, flags=re.S)
    return out


def _mask_inline_verbs(text: str):
    out = text
    masked = []
    i = 0
    while True:
        m = VERB_INLINE_RE.search(out)
        if not m:
            break
        block = m.group(0)
        tok = _PROTECT_VERB.format(i)
        masked.append((tok, block))
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
            block = m.group(0)
            tok = _PROTECT_BLOCK.format(len(masked))
            masked.append((tok, block))
            out = out[:m.start()] + tok + out[m.end():]
    return out, masked


def _unmask(text: str, masked_pairs):
    out = text
    for tok, block in masked_pairs:
        out = out.replace(tok, block)
    return out


def strip_comments(text: str, protect_envs: Iterable[str] = PROTECT_ENVS_DEFAULT) -> str:
    """라인 코멘트(%) 제거, 단 보호된 구간 제외"""
    text = normalize_newlines(text)
    text, masked_verbs = _mask_inline_verbs(text)
    text, masked_envs  = _mask_protect_envs(text, protect_envs)

    PCT = "§§PERCENT_ESC§§"
    text = text.replace(r"\%", PCT)

    out_lines = []
    for line in text.split("\n"):
        if "%" not in line:
            out_lines.append(line)
        else:
            out_lines.append(line.split("%", 1)[0])
    text = "\n".join(out_lines)

    text = text.replace(PCT, r"\%")
    text = _unmask(text, masked_envs)
    text = _unmask(text, masked_verbs)
    return text


def drop_envs(text: str, envs: Iterable[str]) -> str:
    """지정된 LaTeX 환경을 통째로 삭제"""
    out = text
    for env in envs:
        out = re.sub(rf"\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}", "", out, flags=re.S)
    return out


TODO_CMDS_DEFAULT = (r"\todo", r"\marginpar")


def drop_inline_commands(text: str, commands: Iterable[str] = TODO_CMDS_DEFAULT) -> str:
    """\\todo{...} 같은 인라인 명령 삭제"""
    out = text
    for cmd in commands:
        out = re.sub(rf"{re.escape(cmd)}\{{[^{{}}]*\}}", "", out)
    out = re.sub(r"\\iffalse.*?\\fi", "", out, flags=re.S)
    return out


def drop_after_markers(text: str, patterns: list[str]) -> str:
    """특정 패턴 이후 내용 버리기 (appendix 등)"""
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return text[:m.start()]
    return text


def drop_noise_commands(text: str) -> str:
    """레이아웃 보조 명령 제거"""
    text = re.sub(r"\\looseness\s*=?\s*-?\d+", "", text)
    names = ["maketitle", "vspace", "phantom"]
    out = text
    for n in names:
        out = re.sub(rf"\\{n}\*?(?:\[[^\]]*\])?(?:\{{[^{{}}]*\}})?", "", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def clean_text(
    text: str,
    drop_env_list: Iterable[str] = PROTECT_ENVS_DEFAULT,
    also_drop_inline_todos: bool = True,
) -> str:
    """코멘트/환경/잡명령 제거 (본문 정리)"""
    s = strip_comments(text, protect_envs=drop_env_list)
    s = drop_envs(s, drop_env_list)
    if also_drop_inline_todos:
        s = drop_inline_commands(s)
    return s


def preclean_for_body(text: str) -> str:
    """expander 이후: 프리앰블 걷고 본문만 남기기"""
    s = extract_document_body(text)
    s = drop_setup_blocks(s)
    s = drop_noise_commands(s)
    return s

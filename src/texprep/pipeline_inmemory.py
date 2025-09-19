# src/texprep/pipeline_inmemory.py
"""
In-memory TeX pipeline
- dict[str,str] TeX 소스를 받아 merged 본문 텍스트를 반환
"""

from typing import Optional
import re

from src.texprep.io.auto_merge_inmemory import auto_merge_corpus_inmemory

def _guess_main_inmemory(tex_files: dict[str, str]) -> str:
    """
    파일명 힌트 기반으로 main tex 유추 (필요 시 사용).
    """
    priority = ("main.tex", "paper.tex", "root.tex", "ms.tex", "arxiv.tex")
    keys = list(tex_files.keys())
    lower_map = {k.lower(): k for k in keys}
    for p in priority:
        if p in lower_map:
            return lower_map[p]
    # 그래도 못 찾으면 가장 얕은 경로/짧은 이름
    return sorted(keys, key=lambda k: (k.count("/"), len(k)))[0]

def run_pipeline_inmemory(tex_files: dict[str, str], main_tex: Optional[str] = None) -> str:
    """
    tex_files: { "dir/main.tex": "...", ... }
    main_tex: 선택. 없으면 자동 추정하되, auto-merge는 후보군 전체를 사용.
    반환: 최종 후처리된 본문 텍스트(str)
    """
    if not tex_files:
        raise ValueError("빈 TeX 소스 dict")

    drop_envs = [
        "tikzpicture", "minted", "lstlisting", "verbatim", "Verbatim",
        "framed", "mdframed", "tcolorbox",
    ]

    # main_tex는 지금 파이프라인에서 직접 쓰진 않지만, 필요하면 검증 용도로 보관
    if main_tex is None:
        main_tex = _guess_main_inmemory(tex_files)

    merged = auto_merge_corpus_inmemory(tex_files, drop_envs)
    source_text = merged["text"]

    # appendix 이후 제거 같은 후처리
    source_text = re.split(r"\\appendix\b", source_text, flags=re.I)[0]

    return source_text.strip()

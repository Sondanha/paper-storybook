# src/texprep/pipeline_inmemory.py
from pathlib import Path
from io import BytesIO

from src.texprep.io.discover import guess_main
from src.texprep.io.auto_merge import auto_merge_corpus
from src.texprep.tex.expander import expand_file
from src.texprep.tex.strip import preclean_for_body, clean_text, drop_after_markers
from src.texprep.postprocess import run_postprocess


def run_pipeline_inmemory(tex_files: dict[str, str], main_tex: str | None = None) -> str:
    """
    tex_files: {파일명: 내용} 형태의 dict (메모리 상에서 제공된 TeX 소스)
    main_tex: 메인 .tex 파일명 (없으면 자동 추정)
    
    반환: 최종 후처리된 텍스트(str)
    """

    if not tex_files:
        raise ValueError("빈 TeX 소스 dict")

    # 1. 메인 TeX 추정
    if main_tex is None:
        main_tex = guess_main(list(tex_files.keys()))
    if main_tex not in tex_files:
        raise FileNotFoundError(f"main tex 없음: {main_tex}")

    main_content = tex_files[main_tex]

    drop_envs = [
        "tikzpicture", "minted", "lstlisting", "verbatim", "Verbatim",
        "framed", "mdframed", "tcolorbox"
    ]

    # 2. 병합 or 확장
    if True:  # 지금은 auto_merge만 지원
        merged = auto_merge_corpus(tex_files, drop_envs, in_memory=True)
        source_text = merged["text"]
    else:
        expanded_text, _ = expand_file(main_content, in_memory=True)
        body_only = preclean_for_body(expanded_text)
        body_only = drop_after_markers(body_only, [r"\\appendix\b"])
        source_text = clean_text(body_only, drop_env_list=tuple(drop_envs))

    # 3. 후처리 (in-memory)
    final_text = run_postprocess(source_text, in_memory=True)

    return final_text

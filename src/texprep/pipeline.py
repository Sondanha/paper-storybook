from __future__ import annotations
from pathlib import Path
from typing import Any

from src.texprep.io.discover import guess_main
from src.texprep.io.auto_merge import auto_merge_corpus
from src.texprep.tex.expander import expand_file
from src.texprep.tex.strip import preclean_for_body, clean_text, drop_after_markers
from src.texprep.postprocess import run_postprocess


def run_pipeline(cfg: dict[str, Any], main_tex: str | None = None) -> dict[str, Any]:
    root_dir = Path(cfg.get("root_dir", ".")).resolve()
    out_root = Path(cfg.get("out_dir", "./server/data/out")).resolve()

    drop_envs = ["tikzpicture","minted","lstlisting","verbatim","Verbatim",
                 "framed","mdframed","tcolorbox"]

    main_path = Path(main_tex).resolve() if main_tex else Path(guess_main(str(root_dir))).resolve()
    if not main_path.exists():
        raise FileNotFoundError(f"main tex 없음: {main_path}")

    doc_id = main_path.stem.replace(" ", "_")
    out_dir = out_root / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 병합 or 확장
    if cfg.get("select", {}).get("mode", "auto_merge") == "auto_merge":
        merged = auto_merge_corpus(str(main_path.parent), drop_envs)
        source_text = merged["text"]
    else:
        expanded_text, _ = expand_file(str(main_path))
        body_only = preclean_for_body(expanded_text)
        body_only = drop_after_markers(body_only, [r"\\appendix\b"])
        source_text = clean_text(body_only, drop_env_list=tuple(drop_envs))

    # 2) 저장 (postprocess 적용)
    merged_tex_path = out_dir / "merged_body.tex"   # ← 누락된 부분
    merged_tex_path.write_text(source_text, encoding="utf-8")

    # 후처리 적용
    processed_path = out_dir / "final_text.txt"
    run_postprocess(merged_tex_path, processed_path)

    return {
        "doc_id": doc_id,
        "main": str(main_path),
        "chars": len(source_text),
        "merged_body_tex": str(merged_tex_path),
        "final_text": str(processed_path),   # ✅ 후처리된 최종 산출물
        "out_dir": str(out_dir),
        "status": "done"
    }

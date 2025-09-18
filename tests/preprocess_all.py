#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
개발/테스트용 전처리 통합 실행기
- data/raw/*.pdf → 전처리 파이프라인 → data/processed/*.txt
- TeX 소스는 저장하지 않음 (중간 산출물 무시)
"""

import sys
from pathlib import Path
from src.services import preprocess_arxiv
from src.texprep.pipeline import run_pipeline


def process_pdf(pdf_path: Path, out_root: Path):
    # PDF 이름 (확장자 제외) → .txt 출력 파일명으로 사용
    paper_name = pdf_path.stem
    out_txt = out_root / f"{paper_name}.txt"

    # 1단계: PDF에서 TeX 소스 추출
    tmp_root = out_root / f"{paper_name}_tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)

    result = preprocess_arxiv.run_service(
        arxiv_id=None,
        pdf_to_extract_id=pdf_path,
        out_root=tmp_root,
        corp_ca_pem=None,
        left_margin_px=120,
        preview_lines=40,
        clean_extract_dir=True,
    )

    source_dir = Path(result["source_dir"])

    # 2단계: TeX 파이프라인 실행 → merged_body.tex
    cfg = {
        "root_dir": str(source_dir),
        "out_dir": str(tmp_root),
        "select": {"mode": "auto_merge"},
    }
    pipeline_result = run_pipeline(cfg)
    out_txt = out_root / f"{paper_name}.txt"

    final_text_path = Path(pipeline_result["final_text"])
    out_txt.write_text(final_text_path.read_text(encoding="utf-8"), encoding="utf-8")

    # # 3단계: 최종 txt를 data/processed에 저장
    # out_root.mkdir(parents=True, exist_ok=True)
    # out_txt.write_text(merged_txt_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"[OK] {pdf_path.name} → {out_txt}")
    return out_txt


def main():
    raw_dir = Path("data/raw")
    out_root = Path("data/processed")

    if len(sys.argv) < 2:
        print("사용법: python -m tests.preprocess_all <파일명.pdf>")
        return

    pdf_path = raw_dir / sys.argv[1]
    if not pdf_path.exists():
        print(f"❌ 파일 없음: {pdf_path}")
        return

    process_pdf(pdf_path, out_root)


if __name__ == "__main__":
    main()

# 실행 예시:
# (.venv) python -m tests.preprocess_all

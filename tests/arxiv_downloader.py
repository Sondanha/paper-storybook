#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
개발/테스트용 CLI 유틸리티
- arXiv ID 직접 지정 (--id)
- 또는 PDF 업로드 (--pdf) → ID 추출 후 처리
"""

import argparse
from pathlib import Path
from src.services import preprocess_arxiv


def main():
    parser = argparse.ArgumentParser(description="arXiv PDF/소스 다운로드 및 .tex 추정 (테스트용)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--id", help="arXiv ID (예: 1706.03762)")
    src.add_argument("--pdf", type=Path, help="기존 PDF 경로에서 arXiv ID 추출")

    parser.add_argument("--out-root", type=Path, default=Path("./data/processed"),
                        help="출력 루트 폴더 (기본: ./data/processed)")
    parser.add_argument("--corp-ca", type=Path, default=None,
                        help="회사/학교 자체 CA PEM 경로 (선택)")
    parser.add_argument("--left-margin", type=int, default=120,
                        help="PDF 왼쪽 여백(px) 판정값 (기본: 120)")
    parser.add_argument("--preview-lines", type=int, default=40,
                        help="메인 .tex 미리보기 줄 수 (기본: 40)")
    parser.add_argument("--keep-extract", action="store_true",
                        help="이미 존재하는 source 폴더 유지(기본은 재생성)")

    args = parser.parse_args()

    result = preprocess_arxiv.run_service(
        arxiv_id=args.id,
        pdf_to_extract_id=args.pdf,
        out_root=args.out_root,
        corp_ca_pem=str(args.corp_ca) if args.corp_ca else None,
        left_margin_px=args.left_margin,
        preview_lines=args.preview_lines,
        clean_extract_dir=not args.keep_extract,
    )

    print("\n=== 실행 결과 ===")
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()


# python -m tests.arxiv_downloader --pdf data/raw/t.pdf

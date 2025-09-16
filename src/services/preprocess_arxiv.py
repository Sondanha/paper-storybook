#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
arXiv 논문 전처리 서비스 모듈

기능 개요:
1) (선택) PDF에서 arXiv ID 추출 (버전 제거)
2) PDF + e-print(tar.gz) 다운로드
3) 소스(tar.gz) 안전 추출 → .tex 스캔 → 메인 .tex 추정
"""

from __future__ import annotations
import os
import re
import ssl
import tarfile
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import certifi
import requests
import fitz  # PyMuPDF
import urllib.request
import arxiv  # type: ignore

# ===== 정규식: arXiv ID (버전 포함/clean 그룹) =====
ARXIV_PAT = re.compile(r"arXiv:(\d{4}\.\d{4,5})(?:v\d+)?", re.I)


# ===== 1) PDF에서 arXiv ID 추출 =====
def extract_arxiv_id_from_pdf(pdf_path: Path, left_margin_px: int = 120) -> Optional[str]:
    def extract_vertical_text_from_left_margin(page, left_margin_px=120) -> str:
        data = page.get_text("dict")
        vertical_spans = []
        for block in data.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    dx, dy = span.get("dir", (1, 0))
                    sx0, _, _, _ = span.get("bbox", (0, 0, 0, 0))
                    is_left = sx0 <= left_margin_px
                    is_vertical = abs(dx) < 0.5 and abs(dy) > 0.5
                    if is_left and is_vertical:
                        vertical_spans.append(span)
        if not vertical_spans:
            return ""
        vertical_spans.sort(key=lambda s: (round(s["bbox"][0], 1), s["bbox"][1]))
        return re.sub(r"\s+", "", "".join(s["text"] for s in vertical_spans))

    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        # 1) 왼쪽 수직 텍스트
        raw_vertical = extract_vertical_text_from_left_margin(page, left_margin_px)
        m = ARXIV_PAT.search(raw_vertical)
        if m:
            return m.group(1)
        # 2) 왼쪽 여백 전체 텍스트
        left_text = page.get_text("text", clip=fitz.Rect(0, 0, left_margin_px, page.rect.height))
        m2 = ARXIV_PAT.search(left_text or "")
        if m2:
            return m2.group(1)
        # 3) 페이지 전체 텍스트
        full_text = page.get_text("text")
        m3 = ARXIV_PAT.search(full_text or "")
        if m3:
            return m3.group(1)
        return None
    finally:
        doc.close()


# ===== 2) urllib SSL 컨텍스트 =====
def install_global_urllib_ssl_context(corp_ca_pem: Optional[str]) -> None:
    if corp_ca_pem and os.path.exists(corp_ca_pem):
        ctx = ssl.create_default_context(cafile=corp_ca_pem)
    else:
        ctx = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    urllib.request.install_opener(opener)


# ===== 3) 다운로드 =====
def download_with_arxiv_lib(arxiv_id: str, pdf_path: Path, src_tar: Path) -> None:
    search = arxiv.Search(id_list=[arxiv_id])
    result = next(search.results())
    result.download_pdf(filename=str(pdf_path))
    result.download_source(filename=str(src_tar))


def download_direct(arxiv_id: str, pdf_path: Path, src_tar: Path, corp_ca_pem: Optional[str]) -> None:
    verify_arg = corp_ca_pem if (corp_ca_pem and os.path.exists(corp_ca_pem)) else certifi.where()
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    src_url = f"https://arxiv.org/e-print/{arxiv_id}"

    with requests.get(pdf_url, stream=True, timeout=60, verify=verify_arg) as r:
        r.raise_for_status()
        with open(pdf_path, "wb") as f:
            for chunk in r.iter_content(1024 * 64):
                if chunk:
                    f.write(chunk)

    with requests.get(src_url, stream=True, timeout=60, verify=verify_arg) as r:
        r.raise_for_status()
        with open(src_tar, "wb") as f:
            for chunk in r.iter_content(1024 * 64):
                if chunk:
                    f.write(chunk)


# ===== 4) e-print 해제 & 메인 tex 추정 =====
def safe_extract_tar(tar_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode="r:*") as tar:
        def is_within_directory(directory: str, target: str) -> bool:
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
            return os.path.commonprefix([abs_directory, abs_target]) == abs_directory

        for member in tar.getmembers():
            member_path = os.path.join(out_dir, member.name)
            if not is_within_directory(str(out_dir), member_path):
                raise RuntimeError(f"경로 탈출 의심 항목: {member.name}")
        tar.extractall(out_dir)


def find_all_tex(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.tex") if p.is_file()]


def guess_main_tex(tex_files: List[Path]) -> Optional[Path]:
    priority = ["main.tex", "ms.tex", "paper.tex", "arxiv.tex", "root.tex"]
    name_rank = {n: i for i, n in enumerate(priority)}

    best: Tuple[int, int, int, Path] = (999, 999, 10**9, tex_files[0])
    for p in tex_files:
        name_score = name_rank.get(p.name.lower(), 999)
        content_score = 50
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            score = 0
            if re.search(r"\\documentclass", text):
                score -= 2
            if re.search(r"\\begin\{document\}", text):
                score -= 1
            content_score = score if score != 0 else 10
        except Exception:
            pass

        path_len = len(str(p))
        cand = (name_score, content_score, path_len, p)
        if cand < best:
            best = cand

    return best[3]


# ===== 5) 서비스 함수 =====
def run_service(
    arxiv_id: Optional[str],
    pdf_to_extract_id: Optional[Path],
    out_root: Path,
    corp_ca_pem: Optional[str] = None,
    left_margin_px: int = 120,
    preview_lines: int = 40,
    clean_extract_dir: bool = True,
) -> Dict:
    """서비스용 전처리 실행 (JSON-friendly dict 반환)"""
    if not arxiv_id and not pdf_to_extract_id:
        raise ValueError("arXiv ID나 PDF 경로 중 하나는 반드시 제공해야 합니다.")

    if not arxiv_id and pdf_to_extract_id:
        arxiv_id = extract_arxiv_id_from_pdf(pdf_to_extract_id, left_margin_px)
        if not arxiv_id:
            raise RuntimeError("PDF에서 arXiv ID를 찾지 못했습니다.")

    out_dir = out_root / arxiv_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{arxiv_id}.pdf"
    src_tar = out_dir / f"{arxiv_id}_source.tar.gz"

    install_global_urllib_ssl_context(corp_ca_pem)

    try:
        download_with_arxiv_lib(arxiv_id, pdf_path, src_tar)
    except Exception:
        download_direct(arxiv_id, pdf_path, src_tar, corp_ca_pem)

    src_out = out_dir / "source"
    if src_out.exists() and clean_extract_dir:
        shutil.rmtree(src_out)
    safe_extract_tar(src_tar, src_out)

    tex_list = find_all_tex(src_out)
    main_tex = guess_main_tex(tex_list) if tex_list else None

    return {
        "arxiv_id": arxiv_id,
        "pdf_path": str(pdf_path.resolve()),
        "src_tar": str(src_tar.resolve()),
        "source_dir": str(src_out.resolve()),
        "tex_files": [str(p.relative_to(src_out)) for p in tex_list[:10]],
        "main_tex": str(main_tex) if main_tex else None,
        "status": "done",
    }

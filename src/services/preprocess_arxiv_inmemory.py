# src/services/preprocess_arxiv_inmemory.py

"""
인메모리 기반 arXiv 전처리 모듈 (with fallback)
- PDF 바이트에서 arXiv ID 추출 (수직 텍스트 포함)
- PDF + e-print tar.gz 다운로드 (arxiv 라이브러리 → 실패 시 direct 요청)
- e-print에서 .tex 파일만 인메모리로 읽어 dict 반환
"""

from io import BytesIO
import re
import fitz  # PyMuPDF
import requests
import tarfile
import certifi
import arxiv  # pip install arxiv

# ===== 정규식: arXiv ID =====
ARXIV_PAT = re.compile(r"arXiv:(\d{4}\.\d{4,5})(?:v\d+)?", re.I)


def extract_vertical_text_from_left_margin(page, left_margin_px: int = 120) -> str:
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


def extract_arxiv_id_from_pdf_bytes(pdf_bytes: bytes, left_margin_px: int = 120) -> str | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[0]

        # 1) 왼쪽 수직 텍스트
        raw_vertical = extract_vertical_text_from_left_margin(page, left_margin_px)
        if m := ARXIV_PAT.search(raw_vertical):
            return m.group(1)

        # 2) 왼쪽 여백 텍스트
        left_text = page.get_text("text", clip=fitz.Rect(0, 0, left_margin_px, page.rect.height))
        if m2 := ARXIV_PAT.search(left_text or ""):
            return m2.group(1)

        # 3) 전체 텍스트
        full_text = page.get_text("text")
        if m3 := ARXIV_PAT.search(full_text or ""):
            return m3.group(1)

        return None
    finally:
        doc.close()


def fetch_arxiv_sources(arxiv_id: str) -> dict[str, str]:
    """
    e-print에서 .tex 소스를 인메모리 dict로 반환
    - return: {filename: text}
    """
    src_bytes: bytes | None = None

    # 1) arxiv 라이브러리 우선 시도
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(search.results())
        src_buf = BytesIO()
        result.download_source(filename=src_buf)   # type: ignore
        src_bytes = src_buf.getvalue()
    except Exception:
        # 2) direct fallback
        src_url = f"https://arxiv.org/e-print/{arxiv_id}"
        src_r = requests.get(src_url, timeout=60, verify=certifi.where())
        src_r.raise_for_status()
        src_bytes = src_r.content

    # e-print tar.gz 해제
    tex_files: dict[str, str] = {}
    with tarfile.open(fileobj=BytesIO(src_bytes), mode="r:*") as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.endswith(".tex"):
                f = tar.extractfile(member)
                if f:
                    tex_files[member.name] = f.read().decode("utf-8", "ignore")

    return tex_files


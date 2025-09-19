# src/services/preprocess_arxiv_inmemory.py

"""
인메모리 기반 arXiv 전처리 모듈
- PDF 바이트에서 arXiv ID 추출
- e-print tar.gz 다운로드 후 메모리에서 바로 .tex 파일 읽기
"""

from io import BytesIO
import re
import fitz  # PyMuPDF
import requests
import tarfile
import certifi

# ===== 정규식: arXiv ID =====
ARXIV_PAT = re.compile(r"arXiv:(\d{4}\.\d{4,5})(?:v\d+)?", re.I)


def extract_arxiv_id_from_pdf_bytes(pdf_bytes: bytes, left_margin_px: int = 120) -> str | None:
    """
    PDF 바이트에서 arXiv ID 추출
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[0]

        # 왼쪽 여백 텍스트
        left_text = page.get_text("text", clip=fitz.Rect(0, 0, left_margin_px, page.rect.height))
        if m := ARXIV_PAT.search(left_text or ""):
            return m.group(1)

        # 전체 텍스트
        full_text = page.get_text("text")
        if m2 := ARXIV_PAT.search(full_text or ""):
            return m2.group(1)

        return None
    finally:
        doc.close()


def fetch_arxiv_sources(arxiv_id: str) -> dict[str, str]:
    """
    e-print tar.gz 다운로드 후 {filename: text} dict 반환
    """
    src_url = f"https://arxiv.org/e-print/{arxiv_id}"
    r = requests.get(src_url, timeout=60, verify=certifi.where())
    r.raise_for_status()

    tex_files: dict[str, str] = {}
    with tarfile.open(fileobj=BytesIO(r.content), mode="r:*") as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.endswith(".tex"):
                f = tar.extractfile(member)
                if f:
                    tex_files[member.name] = f.read().decode("utf-8", "ignore")
    return tex_files

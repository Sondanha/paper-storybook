from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from src.services import preprocess_arxiv

router = APIRouter()

# 1) ID 직접 지정
@router.post("/v1/papers/{arxiv_id}/preprocess")
async def preprocess_by_id(arxiv_id: str):
    out_root = Path("data/processed")
    try:
        preprocess_arxiv.run(
            arxiv_id=arxiv_id,
            pdf_to_extract_id=None,
            out_root=out_root,
            corp_ca_pem=None,
            left_margin_px=120,
            preview_lines=40,
            clean_extract_dir=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"arxiv_id": arxiv_id, "status": "done"}

# 2) 업로드 PDF에서 ID 추출
@router.post("/v1/papers/preprocess")
async def preprocess_by_pdf(pdf: UploadFile = File(...)):
    out_root = Path("data/processed")
    pdf_path = out_root / pdf.filename
    out_root.mkdir(parents=True, exist_ok=True)
    with open(pdf_path, "wb") as f:
        f.write(await pdf.read())

    arxiv_id = preprocess_arxiv.extract_arxiv_id_from_pdf(pdf_path)
    if not arxiv_id:
        raise HTTPException(status_code=400, detail="arXiv ID not found in PDF")

    try:
        preprocess_arxiv.run(
            arxiv_id=arxiv_id,
            pdf_to_extract_id=pdf_path,
            out_root=out_root,
            corp_ca_pem=None,
            left_margin_px=120,
            preview_lines=40,
            clean_extract_dir=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"arxiv_id": arxiv_id, "status": "done"}

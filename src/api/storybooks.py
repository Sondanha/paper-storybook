# src/api/storybooks.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
import traceback

from src.services.preprocess_arxiv_inmemory import extract_arxiv_id_from_pdf_bytes, fetch_arxiv_sources
from src.texprep.pipeline_inmemory import run_pipeline_inmemory
from src.services.llm.scene_splitter import split_into_scenes_with_narration
from src.services.llm.viz_classifier import classify_scenes_iteratively
from src.services.visualization.dot_cleaner import clean_viz_entry
from src.services.visualization.diagram import render_diagram
from src.services.compositor.scene_composer import compose_scene
from src.services.compositor.pdf_exporter import export_pdf

router = APIRouter()

@router.post("/v1/storybook")
async def create_storybook(pdf: UploadFile = File(...)):
    try:
        pdf_bytes = await pdf.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="빈 PDF")

        # 1) PDF → arXiv ID → 소스 텍스트 in-memory
        arxiv_id = extract_arxiv_id_from_pdf_bytes(pdf_bytes)
        if not arxiv_id:
            raise HTTPException(status_code=400, detail="arXiv ID 추출 실패")

        tex_files = fetch_arxiv_sources(arxiv_id)  # dict[str,str]

        # 2) TeX 파이프라인 in-memory
        full_text = run_pipeline_inmemory(tex_files)

        # 3) Scene split & viz classify
        scenes = split_into_scenes_with_narration(full_text)
        viz_results = classify_scenes_iteratively(scenes)

        # 4) 렌더링 in-memory → PDF 합성
        scene_pngs = []
        for scene in viz_results:
            cleaned = clean_viz_entry(scene)
            dot_code = cleaned.get("diagram", "digraph G { dummy; }")
            scene_id = scene.get("scene_id", 0)

            diagram_png = render_diagram(dot_code, scene_id=scene_id, in_memory=True)
            composed_png = compose_scene(diagram_png, scene.get("narration", ""), in_memory=True)
            if hasattr(composed_png, "seek"):
                composed_png.seek(0)
            scene_pngs.append(composed_png)

        pdf_buf = export_pdf(scene_pngs, in_memory=True)
        return StreamingResponse(
            pdf_buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{arxiv_id}_storybook.pdf"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        # 예외 로그를 서버 콘솔에 출력
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"처리 실패: {e}")

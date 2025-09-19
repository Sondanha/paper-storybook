# src/services/compositor/pdf_exporter.py

from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

def export_pdf(scene_paths: list[Path], out_path: Path) -> Path:
    """
    PNG 씬들을 순서대로 모아 하나의 PDF로 합친다.
    """
    c = canvas.Canvas(str(out_path), pagesize=A4)
    W, H = A4

    for scene in scene_paths:
        img = ImageReader(str(scene))
        iw, ih = img.getSize()

        # 비율 유지, A4 페이지 안에 맞춤
        scale = min(W / iw, H / ih)
        nw, nh = iw * scale, ih * scale
        x, y = (W - nw) / 2, (H - nh) / 2

        c.drawImage(img, x, y, width=nw, height=nh)
        c.showPage()

    c.save()
    return out_path

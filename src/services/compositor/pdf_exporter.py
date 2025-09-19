from pathlib import Path
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

def export_pdf(scene_inputs, out_path: Path | None = None, *, in_memory: bool = False):
    W, H = A4

    if in_memory:
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
    else:
        if out_path is None:
            raise ValueError("out_path must be provided when in_memory=False")
        c = canvas.Canvas(str(out_path), pagesize=A4)

    for scene in scene_inputs:
        if isinstance(scene, BytesIO):
            img = ImageReader(scene)
        else:
            img = ImageReader(str(scene))
        iw, ih = img.getSize()
        scale = min(W / iw, H / ih)
        nw, nh = iw * scale, ih * scale
        x, y = (W - nw) / 2, (H - nh) / 2
        c.drawImage(img, x, y, width=nw, height=nh)
        c.showPage()

    c.save()

    if in_memory:
        buf.seek(0)
        return buf
    else:
        return out_path

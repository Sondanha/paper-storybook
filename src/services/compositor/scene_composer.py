from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError


def _wrap_text_to_width(draw, text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        test_line = f"{line} {word}".strip()
        if draw.textlength(test_line, font=font) <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return "\n".join(lines)


def _make_fallback_scene(message: str, size=(1280, 720)) -> BytesIO:
    """Diagram PNG 로딩 실패 시 fallback 캔버스"""
    W, H = size
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), f"[Fallback Scene]\n{message}", fill="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def compose_scene(
    diagram_input,  # Path 또는 BytesIO
    narration: str,
    out_path: Path | None = None,
    *,
    canvas_size=(1280, 720),
    font_path: Path = Path("assets/NanumGothic.ttf"),
    margin: int = 40,
    in_memory: bool = False,
):
    W, H = canvas_size
    canvas = Image.new("RGB", (W, H), (255, 255, 255))

    img_area_h = int(H * 5 / 6)
    text_area_h = H - img_area_h

    # 🔥 diagram PNG 로딩
    try:
        if isinstance(diagram_input, BytesIO):
            diagram = Image.open(diagram_input).convert("RGBA")
        else:
            diagram = Image.open(diagram_input).convert("RGBA")
    except (UnidentifiedImageError, OSError) as e:
        # fallback 이미지 생성
        return _make_fallback_scene(f"Diagram load failed: {e}", size=canvas_size)

    # 비율 맞춰 리사이즈
    dw, dh = diagram.size
    scale = min((W - 2 * margin) / dw, (img_area_h - 2 * margin) / dh)
    new_w, new_h = int(dw * scale), int(dh * scale)
    diagram = diagram.resize((new_w, new_h), Image.LANCZOS)

    dx = (W - new_w) // 2
    dy = (img_area_h - new_h) // 2
    canvas.paste(diagram, (dx, dy), diagram)

    # 텍스트 렌더링
    draw = ImageDraw.Draw(canvas)
    try:
        if font_path and Path(font_path).exists():
            font_size = max(18, int(text_area_h * 0.2))
            font = ImageFont.truetype(str(font_path), font_size)
        else:
            font = ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()

    wrapped_text = _wrap_text_to_width(draw, narration, font, W - 2 * margin)
    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=6, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_x = (W - tw) // 2
    text_y = img_area_h + (text_area_h - th) // 2

    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill=(0, 0, 0), spacing=6, align="center")

    if in_memory:
        buf = BytesIO()
        canvas.save(buf, format="PNG")
        buf.seek(0)
        return buf
    else:
        if out_path is None:
            raise ValueError("out_path must be provided when in_memory=False")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path)
        return out_path

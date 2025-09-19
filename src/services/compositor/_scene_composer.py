# src/services/compositor/scene_composer.py

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from src.services.compositor.pdf_exporter import export_pdf

def _wrap_text_to_width(draw, text, font, max_width):
    """
    주어진 텍스트를 픽셀 단위 가로폭 기준으로 줄바꿈한다.
    """
    lines, line = [], ""
    for word in text.split():
        test_line = f"{line} {word}".strip()
        if draw.textlength(test_line, font=font) <= max_width:
            line = test_line
        else:
            if line:  # 기존 줄 저장
                lines.append(line)
            line = word  # 새 줄 시작
    if line:
        lines.append(line)
    return "\n".join(lines)

def compose_scene(
    diagram_path: Path,
    narration: str,
    out_path: Path,
    *,
    canvas_size=(1280, 720),
    font_path: Path = Path("assets/NanumGothic.ttf"),
    margin: int = 40,
) -> Path:
    """
    Graphviz 다이어그램 PNG와 나레이션을 합성하여 최종 Scene 이미지를 만든다.
    - 흰색 배경 위 중앙에 다이어그램
    - 하단 텍스트는 가로폭 맞춰 가운데 정렬
    - 이미지:텍스트 높이 비율 = 5:1
    """
    W, H = canvas_size
    canvas = Image.new("RGB", (W, H), (255, 255, 255))

    # 세로 비율 분리
    img_area_h = int(H * 5 / 6)   # 5:1 비율
    text_area_h = H - img_area_h

    # viz 이미지 로드
    diagram = Image.open(diagram_path).convert("RGBA")
    dw, dh = diagram.size

    # 다이어그램 비율 유지 리사이즈
    scale = min((W - 2 * margin) / dw, (img_area_h - 2 * margin) / dh)
    new_w, new_h = int(dw * scale), int(dh * scale)
    diagram = diagram.resize((new_w, new_h), Image.LANCZOS)

    # 중앙 배치
    dx = (W - new_w) // 2
    dy = (img_area_h - new_h) // 2
    canvas.paste(diagram, (dx, dy), diagram)

    # 나레이션 폰트 설정
    draw = ImageDraw.Draw(canvas)
    try:
        if font_path and Path(font_path).exists():
            font_size = max(18, int(text_area_h * 0.2))  # 텍스트 영역 비율 기반
            font = ImageFont.truetype(str(font_path), font_size)
        else:
            font = ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()

    # 픽셀 기준 줄바꿈
    wrapped_text = _wrap_text_to_width(draw, narration, font, W - 2 * margin)

    # 텍스트 크기 계산
    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=6, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 가운데 정렬
    text_x = (W - tw) // 2
    text_y = img_area_h + (text_area_h - th) // 2

    draw.multiline_text(
        (text_x, text_y),
        wrapped_text,
        font=font,
        fill=(0, 0, 0),
        spacing=6,
        align="center",
    )

    # 저장
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return out_path

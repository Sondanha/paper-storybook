# src/services/compositor/scene_composer.py
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def compose_scene(
    diagram_path: Path,
    narration: str,
    out_path: Path,
    *,
    character_path: Path = Path("assets/characters/mascot.png"),
    font_path: Path = Path("assets/NanumGothic.ttf"),
    font_size: int = 18,
) -> Path:
    """
    Graphviz 다이어그램 PNG와 나레이션을 합성하여 최종 Scene 이미지를 만든다.
    말풍선 PNG 대신, 코드에서 직접 둥근 직사각형+꼬리로 말풍선을 그림.
    """
    # 배경 다이어그램 로드
    diagram = Image.open(diagram_path).convert("RGBA")
    W, H = diagram.size

    # 캐릭터 로드
    character = Image.open(character_path).convert("RGBA")
    char_w, char_h = 200, 300
    character = character.resize((char_w, char_h), Image.LANCZOS)

    # 새 캔버스 (다이어그램 아래에 공간 추가)
    canvas = Image.new("RGBA", (W, H + 120), (255, 255, 255, 255))
    canvas.paste(diagram, (0, 0))

    # 캐릭터 좌하단 배치
    char_x = 20
    char_y = H - char_h + 80
    canvas.paste(character, (char_x, char_y), character)

    # 말풍선 위치 계산
    bubble_x = char_x + char_w - 20
    bubble_y = H - 180
    bubble_w, bubble_h = 360, 120

    # 말풍선 그리기
    draw = ImageDraw.Draw(canvas)
    bubble_box = [bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h]
    draw.rounded_rectangle(bubble_box, radius=20, fill=(255, 255, 230), outline=(200, 180, 0), width=2)

    # 꼬리 (삼각형) 추가
    tail = [
        (char_x + char_w - 10, char_y + 50),
        (bubble_x, bubble_y + bubble_h // 2 - 10),
        (bubble_x, bubble_y + bubble_h // 2 + 10),
    ]
    draw.polygon(tail, fill=(255, 255, 230), outline=(200, 180, 0))

    # 나레이션 텍스트 그리기
    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except OSError:
        font = ImageFont.load_default()

    text_x = bubble_x + 15
    text_y = bubble_y + 15
    draw.multiline_text((text_x, text_y), narration, font=font, fill=(0, 0, 0), spacing=4)

    # 저장
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return out_path

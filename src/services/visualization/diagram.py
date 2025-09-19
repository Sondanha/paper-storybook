from pathlib import Path
from graphviz import Source
from io import BytesIO
from PIL import Image, ImageDraw
import re

_ENGINE_MAP = {
    "dot": "dot",
    "neato": "neato",
    "fdp": "fdp",
    "sfdp": "sfdp",
    "twopi": "twopi",
    "circo": "circo",
}

_layout_re = re.compile(r"\blayout\s*=\s*([A-Za-z0-9_]+)", re.I)

def detect_engine(dot_code: str) -> str:
    m = _layout_re.search(dot_code)
    if m:
        return _ENGINE_MAP.get(m.group(1).lower(), "dot")
    return "dot"

def ensure_graph_wrapper(dot_code) -> str:
    if isinstance(dot_code, dict):
        if "diagram" in dot_code and isinstance(dot_code["diagram"], str):
            dot_code = dot_code["diagram"]
        else:
            return "digraph G { dummy [label=\"invalid input\"]; }"
    elif not isinstance(dot_code, str):
        dot_code = str(dot_code)

    if not dot_code:
        return "digraph G { dummy [label=\"empty\"]; }"

    stripped = dot_code.strip()
    if stripped.startswith("digraph") or stripped.startswith("graph"):
        return dot_code

    body = "\n".join(line for line in dot_code.splitlines() if line.strip())
    if not body:
        body = 'dummy [label="auto_fixed"];'
    return f"digraph G {{\n{body}\n}}"

def sanitize_dot(dot_code: str) -> str:
    """닫히지 않은 따옴표 같은 흔한 오류를 보정"""
    # 닫히지 않은 큰따옴표 제거
    if dot_code.count('"') % 2 == 1:
        dot_code = dot_code.rsplit('"', 1)[0] + '"'
    return dot_code

def _make_fallback_png(message: str) -> BytesIO:
    """Graphviz 실패 시 대체 PNG 생성"""
    img = Image.new("RGB", (800, 600), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), f"Graphviz error:\n{message}", fill="black")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def render_diagram(dot_code: str, out_dir: Path | None = None, scene_id: int = 0, *, in_memory: bool = False):
    dot_code = ensure_graph_wrapper(dot_code)
    dot_code = sanitize_dot(dot_code)
    engine = detect_engine(dot_code)

    if in_memory:
        try:
            src = Source(dot_code, engine=engine)
            png_bytes = src.pipe(format="png")
            return BytesIO(png_bytes)   # 정상 PNG
        except Exception as e:
            return _make_fallback_png(str(e))   # 실패 시 fallback PNG
    else:
        if out_dir is None:
            raise ValueError("out_dir must be provided when in_memory=False")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"scene_{scene_id}.png"

        # 디버깅용 .dot 파일 저장
        dot_file = out_dir / f"scene_{scene_id}.dot"
        with open(dot_file, "w", encoding="utf-8") as f:
            f.write(dot_code)

        try:
            src = Source(dot_code, filename=str(out_path.with_suffix("")), format="png", engine=engine)
            src.render(cleanup=True)
            return out_path
        except Exception as e:
            # fallback PNG 파일 생성
            buf = _make_fallback_png(str(e))
            with open(out_path, "wb") as f:
                f.write(buf.getvalue())
            return out_path

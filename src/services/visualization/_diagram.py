# src/services/visualization/diagram.py
from pathlib import Path
from graphviz import Source
import re

# layout 속성 → Graphviz 엔진 매핑
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
    """DOT 코드 안에 layout=... 있으면 그걸 엔진으로 사용"""
    m = _layout_re.search(dot_code)
    if m:
        return _ENGINE_MAP.get(m.group(1).lower(), "dot")
    # 기본값은 dot
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

    # 비정상 입력일 때 보정
    body = "\n".join(line for line in dot_code.splitlines() if line.strip())
    if not body:
        body = 'dummy [label="auto_fixed"];'
    return f"digraph G {{\n{body}\n}}"


def render_diagram(dot_code: str, out_dir: Path, scene_id: int) -> Path:
    """
    DOT 문자열을 받아 PNG로 렌더링.
    layout= 속성을 읽어서 맞는 엔진으로 실행.
    """
    out_path = out_dir / f"scene_{scene_id}.png"
    out_dir.mkdir(parents=True, exist_ok=True)

    dot_code = ensure_graph_wrapper(dot_code)

    try:
        engine = detect_engine(dot_code)

        # 디버깅용으로 .dot 파일 저장
        dot_file = out_dir / f"scene_{scene_id}.dot"
        with open(dot_file, "w", encoding="utf-8") as f:
            f.write(dot_code)
        print(f"🛠 scene {scene_id}: engine={engine}, saved {dot_file}")

        src = Source(dot_code, filename=str(out_path.with_suffix("")), format="png", engine=engine)
        src.render(cleanup=True)
        print(f"✅ scene {scene_id} → {out_path}")
    except Exception as e:
        fallback_path = out_dir / f"scene_{scene_id}_error.png"
        with open(fallback_path, "wb") as f:
            f.write(b"")
        print(f"⚠️ scene {scene_id} DOT render failed ({e}), fallback created: {fallback_path}")
        return fallback_path

    return out_path

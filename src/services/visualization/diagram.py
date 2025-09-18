# src/services/visualization/diagram.py

from pathlib import Path
from graphviz import Source

def ensure_graph_wrapper(dot_code) -> str:
    """
    DOT 코드가 문자열이 아닐 수도 있음(dict 등).
    안전하게 문자열만 받아 처리.
    """
    # dict나 다른 타입일 때 → 문자열로 변환 시도
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

    # 이미 정상적인 DOT 시작
    if stripped.startswith("digraph") or stripped.startswith("graph"):
        return dot_code

    # 비정상적인 경우: 줄 단위 보정
    fixed_lines = []
    for line in dot_code.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("["):  # 잘못된 노드 정의
            fixed_lines.append('dummy [label="auto_fixed"];')
        else:
            fixed_lines.append(s)

    body = "\n".join(fixed_lines) if fixed_lines else 'dummy [label="auto_fixed"];'
    return f"digraph G {{\n{body}\n}}"

def render_diagram(dot_code: str, out_dir: Path, scene_id: int) -> Path:
    """
    DOT 문자열을 받아 PNG로 렌더링.
    오류 가능성이 있는 DOT은 ensure_graph_wrapper로 안전하게 감쌈.
    """
    out_path = out_dir / f"scene_{scene_id}.png"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 🚩 안전 보정 적용
    dot_code = ensure_graph_wrapper(dot_code)

    try:
        src = Source(dot_code, filename=str(out_path.with_suffix("")), format="png")
        src.render(cleanup=True)
        print(f"✅ scene {scene_id} → {out_path}")
    except Exception as e:
        # 렌더 실패 시 fallback PNG 생성
        fallback_path = out_dir / f"scene_{scene_id}_error.png"
        with open(fallback_path, "wb") as f:
            f.write(b"")  # 그냥 빈 파일
        print(f"⚠️ scene {scene_id} → DOT render failed ({e}), fallback created: {fallback_path}")
        return fallback_path

    return out_path

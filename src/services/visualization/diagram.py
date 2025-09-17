from graphviz import Source
from pathlib import Path
from typing import Literal, Optional
from src.services.visualization.dot_cleaner import clean_dot


# 공통 스타일 헤더 (노랑-주황 계열, 따뜻한 느낌)
STYLE_HEADER = """
node [shape=box,
      style="rounded,filled",
      fontname="Helvetica",
      fontsize=11,
      fillcolor="#FFE5B4", // 밝은 오렌지
      color="#FFB347"];    // 테두리 주황
edge [color="#FF8C00", penwidth=1.2, arrowsize=0.7];
graph [bgcolor="#FFF8E7"]; // 크림색 배경
"""


def render_graphviz(
    dot_source: str,
    format: Literal["png", "svg"] = "png",
    out_path: Optional[Path] = None,
    engine: Literal["dot", "neato", "circo"] = "dot",
) -> bytes:
    """
    Render a Graphviz DOT string into an image with warm style.

    Args:
        dot_source (str): Graphviz DOT language string
        format (str): Output format ("png" or "svg")
        out_path (Optional[Path]): If provided, save file here
        engine (str): Layout engine ("dot", "neato", "circo")

    Returns:
        bytes: Rendered image content
    """
    # DOT 문자열 전처리
    body = clean_dot(dot_source)

    # 스타일 헤더 주입
    styled_dot = body
    if "digraph" in body:
        # 본문에서 digraph G { ... } 잡아서 STYLE_HEADER 삽입
        styled_dot = body.replace("{", "{" + STYLE_HEADER, 1)

    src = Source(styled_dot, engine=engine)
    img_bytes = src.pipe(format=format)

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(img_bytes)

    return img_bytes


def render_scene_visualization(
    viz_prompt: str,
    scene_id: int,
    label: str,
    out_dir: Optional[Path] = None,
    engine: Literal["dot", "neato", "circo"] = "dot",
) -> bytes:
    """
    Render one visualization item from scene JSON with warm theme.

    Args:
        viz_prompt (str): Graphviz DOT string
        scene_id (int): Scene number
        label (str): Visualization label
        out_dir (Optional[Path]): If provided, save under this directory
        engine (str): Layout engine ("dot", "neato", "circo")

    Returns:
        bytes: Rendered image content
    """
    safe_label = label.replace(" ", "_").replace("/", "_")
    out_path = None
    if out_dir is not None:
        out_path = out_dir / f"scene{scene_id}_{safe_label}.png"

    return render_graphviz(
        dot_source=viz_prompt,
        format="png",
        out_path=out_path,
        engine=engine,
    )

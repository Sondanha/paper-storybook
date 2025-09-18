# src/services/visualization/dot_cleaner.py

import re

def _unescape_dot_string(dot_str: str) -> str:
    """DOT 코드 문자열의 JSON 이스케이프만 복구"""
    return (
        dot_str
        .replace("\\n", "\n")
        .replace('\\"', '"')
        .replace("\\t", "\t")
        .replace("\\r", "")
    )

def escape_square_brackets(dot_code: str) -> str:
    """label="..." 패턴 안에서 [ ] 를 \[ \] 로 치환"""
    def repl(m):
        text = m.group(1)
        # 두 번 백슬래시 넣어야 파이썬에서 경고 안 나고 Graphviz에서 \[로 전달됨
        text = text.replace("[", "\\\\[").replace("]", "\\\\]")
        return f'label="{text}"'
    return re.sub(r'label="([^"]*)"', repl, dot_code)

def inject_font(dot_code: str, font: str = "Malgun Gothic") -> str:
    """DOT 코드 맨 위에 폰트 지정 구문 삽입"""
    lines = dot_code.splitlines()
    if not any("fontname" in l for l in lines):
        # digraph/graph 선언 바로 뒤에 넣음
        for i, line in enumerate(lines):
            if line.strip().startswith(("digraph", "graph")):
                lines.insert(i + 1, f'  node [fontname="{font}"];')
                lines.insert(i + 2, f'  edge [fontname="{font}"];')
                break
    return "\n".join(lines)


def force_html_labels(dot_code: str) -> str:
    """
    모든 label="..." → label=<...> 로 변환.
    [] 같은 특수문자가 있어도 그대로 출력된다.
    """
    def repl(m):
        text = m.group(1)
        # HTML-safe 변환
        text = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        return f'label=<{text}>'
    return re.sub(r'label="([^"]*)"', repl, dot_code)


def clean_viz_entry(entry: dict[str, object]) -> dict[str, object]:
    dot_code = None

    # 1. 최상위 diagram 키
    if "diagram" in entry and isinstance(entry["diagram"], str):
        dot_code = entry["diagram"]

    # 2. visualizations 안에서 찾기
    elif "visualizations" in entry and isinstance(entry["visualizations"], list):
        for viz in entry["visualizations"]:
            if isinstance(viz, dict) and "diagram" in viz:
                dot_code = viz["diagram"]
                break

    # 3. 실패하면 fallback
    if not dot_code:
        dot_code = "digraph G { dummy [label=\"auto_fallback\"]; }"

    # 문자열 정리
    dot_code = _unescape_dot_string(dot_code)
    dot_code = force_html_labels(dot_code)
    dot_code = inject_font(dot_code, "Malgun Gothic")

    entry["diagram"] = dot_code
    return entry


# src/services/visualization/dot_cleaner.py
import re
import textwrap

# -------------------------------
# 유틸 함수
# -------------------------------
def _unescape_dot_string(dot_str: str) -> str:
    return (
        dot_str
        .replace("\\n", "\n")
        .replace('\\"', '"')
        .replace("\\t", "\t")
        .replace("\\r", "")
    )

def _insert_after_open_brace(dot_code: str, lines_to_insert: list[str]) -> str:
    """DOT 본문 블록 내부에 안전 삽입"""
    i = dot_code.find("{")
    j = dot_code.rfind("}")
    if i == -1 or j == -1 or j <= i:
        return dot_code
    before = dot_code[:i+1]
    body = dot_code[i+1:j]
    after = dot_code[j:]

    # 들여쓰기 맞추기
    indent = ""
    for line in body.splitlines():
        if line.strip():
            indent = line[: len(line) - len(line.lstrip())]
            break
    insertion = "\n".join(f"{indent}{line}" for line in lines_to_insert)
    return f"{before}\n{insertion}\n{body}\n{after}"

# -------------------------------
# 보정 로직
# -------------------------------
def inject_font(dot_code: str, font: str = "Malgun Gothic") -> str:
    if "fontname" in dot_code:
        return dot_code
    return _insert_after_open_brace(dot_code, [
        f'node [fontname="{font}"];',
        f'edge [fontname="{font}"];',
    ])

def inject_graph_defaults(dot_code: str) -> str:
    """겹침 방지용 기본 graph 속성 삽입"""
    defaults = {
        "bgcolor": '"white"',
        "ranksep": "0.6",
        "nodesep": "0.4",
        "splines": "true",
        "overlap": "false",
        "sep": "0.3",
        "clusterrank": "local",
        "outputorder": "edgesfirst",
    }

    m = re.search(r"graph\s*\[([^\]]*)\]", dot_code)
    if m:
        before, inside, after = dot_code[:m.start(1)], m.group(1), dot_code[m.end(1):]
        props = {k.strip(): v.strip() for k,v in 
                 (pair.split("=") for pair in inside.split(",") if "=" in pair)}
        for k, v in defaults.items():
            if k not in props:
                props[k] = v
        new_inside = ", ".join(f"{k}={v}" for k,v in props.items())
        return f"{before}{new_inside}{after}"
    else:
        return _insert_after_open_brace(dot_code, [
            'graph [bgcolor="white", ranksep=0.6, nodesep=0.4, '
            'splines=true, overlap=false, sep=0.3, '
            'clusterrank=local, outputorder=edgesfirst];'
        ])

def force_html_labels(dot_code: str) -> str:
    def repl(m):
        text = m.group(1)
        text = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        return f'label=<{text}>'
    return re.sub(r'label="([^"]*)"', repl, dot_code)

_ellipsis_chain = re.compile(r"->\s*\.\.\.\s*->")

def sanitize_ellipsis(dot_code: str) -> str:
    """a -> ... -> b 같은 체인을 안전하게 치환"""
    if "..." not in dot_code:
        return dot_code
    code = _ellipsis_chain.sub("-> ellipsis ->", dot_code)
    if "ellipsis" in code and "ellipsis [" not in code:
        code = _insert_after_open_brace(
            code, ['ellipsis [shape=point, width=0.02, label=""];']
        )
    return code

# -------------------------------
# 긴 label 보정
# -------------------------------
def sanitize_labels(dot_code: str, max_len: int = 200) -> str:
    """
    Graphviz DOT label 보정
    - 따옴표 → HTML-safe 변환
    - 긴 문자열 자동 줄바꿈
    """

    def repl(m):
        text = m.group(1)

        # 긴 텍스트 → 줄바꿈 추가
        if len(text) > max_len:
            text = "\n".join(textwrap.wrap(text, width=max_len))

        # 특수문자 escape
        text = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("+", "&#43;")
                .replace("|", "&#124;")
                .replace("[", "&#91;")  
                .replace("]", "&#93;")
                .replace('"', "'")
        )
        return f'label=<{text}>'

    return re.sub(r'label="([^"]*?)"', repl, dot_code)

# -------------------------------
# 엔진 감지 + 힌트 삽입
# -------------------------------
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
    if "rankdir=" in dot_code or "cluster_encoder" in dot_code or "cluster_decoder" in dot_code:
        return "dot"
    m = _layout_re.search(dot_code)
    if m:
        return _ENGINE_MAP.get(m.group(1).lower(), "dot")
    return "dot"

def inject_engine_hints(dot_code: str, engine: str) -> str:
    if engine == "twopi" and "root=" not in dot_code:
        m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\[", dot_code)
        if m:
            root_node = m.group(1)
            if root_node.lower() not in {"graph", "digraph"}:
                return _insert_after_open_brace(dot_code, [f'graph [root={root_node}];'])
    if engine == "neato":
        if "mode=" not in dot_code:
            dot_code = _insert_after_open_brace(dot_code, ['graph [mode=KK];'])
        if "sep=" not in dot_code:
            dot_code = _insert_after_open_brace(dot_code, ['graph [sep="+1"];'])
    return dot_code

# -------------------------------
# 스타일 주입
# -------------------------------
def inject_style(dot_code: str) -> str:
    additions = []
    if "bgcolor=" not in dot_code:
        additions.append('graph [bgcolor="#fffdf7", style=filled];')
    if "fillcolor=" not in dot_code:
        additions.append(
            'node [style="filled,rounded", '
            'fillcolor="#fff2b2:#ffd966", gradientangle=90, '
            'color="#e6a700", fontcolor="#000000", shape=box];'
        )
    if "edge [color=" not in dot_code:
        additions.append(
            'edge [color="#d4a017", penwidth=1.5];'
        )

    if additions:
        dot_code = _insert_after_open_brace(dot_code, additions)
    return dot_code

# -------------------------------
# 메인 엔트리
# -------------------------------
def clean_viz_entry(entry: dict[str, object]) -> dict[str, object]:
    dot_code = None

    if "diagram" in entry and isinstance(entry["diagram"], str):
        dot_code = entry["diagram"]
    elif "visualizations" in entry and isinstance(entry["visualizations"], list):
        for viz in entry["visualizations"]:
            if isinstance(viz, dict) and "diagram" in viz:
                dot_code = viz["diagram"]
                break

    if not dot_code:
        dot_code = "digraph G { dummy [label=\"auto_fallback\"]; }"

    dot_code = _unescape_dot_string(dot_code)
    dot_code = sanitize_ellipsis(dot_code)
    dot_code = force_html_labels(dot_code)
    dot_code = sanitize_labels(dot_code)   # ✅ 추가
    dot_code = inject_font(dot_code, "Malgun Gothic")
    dot_code = inject_graph_defaults(dot_code)

    # 엔진 감지 후 힌트 삽입
    engine = detect_engine(dot_code)
    dot_code = inject_engine_hints(dot_code, engine)

    # 스타일 주입
    dot_code = inject_style(dot_code)

    entry["diagram"] = dot_code
    return entry

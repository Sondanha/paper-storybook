# src/services/llm/viz_classifier.py

import json
import re
from typing import Any
from src.services.llm.client import call_claude
from src.core.config import settings

_MAX_TEXT_CHARS = 3000

# =====================
# 🚩 추가 유틸
# =====================

def _truncate(s: str, max_len: int = _MAX_TEXT_CHARS) -> str:
    if not s:
        return ""
    return s if len(s) <= max_len else s[:max_len]


def _strip_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_first_balanced_json(s: str) -> str | None:
    i0 = s.find("{")
    if i0 < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(i0, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[i0 : i + 1]
    return None


def _repair_common_broken_pairs(s: str) -> str:
    keys = r"(diagram|graphviz|graphviz_code|graph|dot|scene_graph|content|layout)"
    s = re.sub(rf",\s*\"{keys}\"\s*:\s*,\s*\"{keys}\"\s*:", r", \"\2\":", s, flags=re.DOTALL)
    s = re.sub(rf"\"{keys}\"\s*:\s*,\s*\"{keys}\"\s*:", r"\"\2\":", s, flags=re.DOTALL)
    s = re.sub(rf",\s*\"{keys}\"\s*:\s*,\s*", r", ", s, flags=re.DOTALL)
    s = re.sub(rf"\"{keys}\"\s*:\s*,\s*", r"", s, flags=re.DOTALL)
    return s


def _sanitize_label(text: str) -> str:
    """
    노드/에지 label 텍스트 정리:
    - 금지문자([]{} backtick) 제거
    - 최대 20자 제한, 넘으면 edge로 넘길 수 있도록 별도 표시
    """
    text = re.sub(r"[\[\]{}`]", "()", text).strip()
    if len(text) > 20:
        return text[:17] + "..."
    return text


def _enforce_label_rules(diagram: str) -> str:
    """
    DOT 코드 내 라벨을 HTML <FONT> 형식으로 강제 변환.
    """
    def repl(m):
        return f'label=<<FONT FACE="NanumGothic">{_sanitize_label(m.group(1))}</FONT>>'

    diagram = re.sub(r'label\s*=\s*"([^"]+)"', repl, diagram)

    if 'fontname="NanumGothic"' not in diagram:
        diagram = (
            'graph [fontname="NanumGothic", fontsize=12];\n'
            'node [fontname="NanumGothic", fontsize=12];\n'
            'edge [fontname="NanumGothic", fontsize=12];\n'
            + diagram
        )
    return diagram


def _assign_unique_layout(viz: dict[str, Any], used_layouts: list[str]) -> None:
    """
    레이아웃 중복 방지: 아직 안 쓴 레이아웃이 있으면 강제로 할당.
    """
    all_layouts = ["dot", "neato", "circo", "twopi"]
    layout = viz.get("layout", "dot")
    if layout in used_layouts and len(used_layouts) < len(all_layouts):
        unused = [l for l in all_layouts if l not in used_layouts]
        if unused:
            viz["layout"] = unused[0]


# 추가: 이스케이프된 따옴표를 건너뛰며 "tool": "..." 전체를 잡아 DOT면 diagram으로 이동
def _fix_tool_field_digraphs(s: str) -> str:
    # "tool": " ... " 에서 내부는 (\\.|[^"\\])* 로 캡처 → 이스케이프된 따옴표도 통과
    pat = re.compile(r'"tool"\s*:\s*"((?:\\.|[^"\\])*)"')

    def repl(m: re.Match[str]) -> str:
        inner_escaped = m.group(1)
        try:
            # JSON 문자열 디코딩으로 실제 값 복원
            value = json.loads(f'"{inner_escaped}"')
        except Exception:
            value = inner_escaped

        if isinstance(value, str) and value.lstrip().startswith(("digraph", "graph")):
            # tool → graphviz, diagram에 DOT 삽입
            return f'"tool": "graphviz", "diagram": {json.dumps(value, ensure_ascii=False)}'
        return m.group(0)

    return pat.sub(repl, s)


def _repair_raw_json(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)

    s = s.replace('"excalidraw"', '"graphviz"')
    s = s.replace('"stable-diffusion"', '"stability"')

    # 중복 diagram 키 보정 그대로 두고...
    s = re.sub(r'("diagram"\s*:\s*)",\s*"diagram"\s*:\s*', r'\1', s)

    # ✅ 이 줄 추가: tool에 박힌 DOT를 이스케이프-안전하게 끌어내기
    s = _fix_tool_field_digraphs(s)

    # 이하 기존 alias 블록 추출 루프 그대로...
    aliases = ['"diagram"', '"graphviz"', '"graph"', '"graphviz_code"', '"dot"', '"scene_graph"']

    def _encode_graph_block(text: str, key_pos: int) -> tuple[str, int] | None:
        colon = text.find(":", key_pos)
        if colon == -1:
            return None
        i = colon + 1
        while i < len(text) and text[i].isspace():
            i += 1
        had_quote = False
        if i < len(text) and text[i] == '"':
            had_quote = True
            i += 1

        m = re.search(r'(digraph\s+[^{]+\{|\bgraph\s*\{)', text[i:], re.IGNORECASE)
        if not m:
            return None
        start = i + m.start()

        depth = 0
        j = start
        in_str = False
        while j < len(text):
            ch = text[j]
            prev = text[j-1] if j > 0 else ""
            if ch == '"' and prev != '\\':
                in_str = not in_str
            if not in_str:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
            j += 1
        else:
            return None

        block = text[start:end]
        encoded = json.dumps(block, ensure_ascii=False)

        k = end
        if had_quote and k < len(text) and text[k] == '"':
            k += 1

        new_text = text[:colon+1] + " " + encoded + text[k:]
        return new_text, colon + 1 + 1 + len(encoded)

    idx = 0
    while True:
        next_pos = None
        which = None
        for a in aliases:
            p = s.find(a, idx)
            if p != -1 and (next_pos is None or p < next_pos):
                next_pos = p
                which = a
        if next_pos is None:
            break

        res = _encode_graph_block(s, next_pos + len(which))
        if res is None:
            idx = next_pos + len(which)
            continue
        s, idx = res

    return s


def _safe_json_loads(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # 잘못된 escape 치환
        s = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)

    try:
        return json.loads(s)
    except Exception:
        pass

    s_fixed = _repair_raw_json(s)
    try:
        return json.loads(s_fixed)
    except Exception:
        only_json = _extract_first_balanced_json(s_fixed)
        if only_json:
            return json.loads(only_json)
        raise


def _normalize_viz_keys(obj: dict[str, Any]) -> dict[str, Any]:
    for key in ["graph", "graphviz", "graphviz_code", "dot", "scene_graph"]:
        if key in obj and "diagram" not in obj:
            obj["diagram"] = obj[key]
            del obj[key]
    return obj


def _hoist_top_level_diagram(obj: dict[str, Any]) -> None:
    code = obj.get("diagram")
    layout = obj.get("layout") or "dot"
    if code and isinstance(code, str):
        vizzes = obj.get("visualizations")
        if not isinstance(vizzes, list):
            vizzes = []
        vizzes.insert(
            0,
            {
                "viz_type": "diagram",
                "tool": "graphviz",
                "layout": layout,
                "viz_label": "auto_primary",
                "diagram": code,
            },
        )
        obj["visualizations"] = vizzes


def _ensure_viz_labels(vizzes: list[dict[str, Any]], scene_id: Any) -> None:
    for idx, v in enumerate(vizzes):
        if not v.get("viz_label"):
            v["viz_label"] = f"scene_{scene_id}_v{idx+1}"


def classify_single_scene(
    scene: dict[str, Any],
    used_layouts: list[str] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    scene_id = scene.get("scene_id")
    title = str(scene.get("title", "")).strip()
    narration = _truncate(str(scene.get("narration", "")).strip())
    raw_text = _truncate(str(scene.get("raw_text", "")).strip())

    layouts_info = (
        f"Previously used layouts: {', '.join(used_layouts)}"
        if used_layouts
        else "No layouts used yet"
    )

    prompt = f"""
    You are the 'Visualization Designer' for an AI paper storybook.
    Your task: propose **1–2 clear schematic diagrams** (Graphviz DOT).
    Illustrations are strongly discouraged — only use them if a diagram cannot express the idea.

    ⚠️ Output rules (STRICT):
    - Return ONE valid JSON object ONLY. No prose, no extra code after the JSON.
    - Always include "scene_id", "title", "narration".
    - Allowed viz_type: "diagram" (preferred), "illustration" (rare).
    - For diagrams: use "tool": "graphviz" and include "layout" ("dot","neato","circo","twopi").
    - Graphviz code must be JSON-safe (escape newlines as \\n). Put code under "diagram".
    - Do NOT append raw DOT after the JSON.

    ⚠️ Layout Diversity Rule:
    - Do NOT always use rankdir=LR with dot.
    - Each paper MUST include at least 3 distinct layouts across its scenes.
    - {layouts_info}
    - Prefer introducing a new layout if repetition is detected.

    💡 Language & Label Rules:
    - "title"과 "narration"은 한국어 문장으로 작성하되, 중요한 기술 용어는 반드시 영어 병기 (예: YOLO (You Only Look Once)).
    - Graphviz DOT 코드 내 시각적 텍스트는 반드시 label=<...> 안에서 HTML 블록으로 작성.
    - 모든 label은 <FONT FACE="NanumGothic">텍스트</FONT> 형식으로 작성.
    - 모든 노드와 에지에는 반드시 fontname="NanumGothic", fontsize=12 이상을 지정.

    ⚠️ Node ID Rules (STRICT):
    - 모든 노드 ID는 단순한 영문/숫자/언더스코어만 사용 (예: node1, node2, yolo_model).
    - 노드 ID 안에 한글, 공백, HTML 태그를 절대 넣지 말 것.
    - 시각적으로 표시할 텍스트는 반드시 label 속성에 넣을 것.

    ⛔ Forbidden Rules:
    - 노드/에지 label에는 긴 문장, 수식, 토큰 시퀀스([CLS], 중괄호({{...}}), `) 절대 금지.
    - 한 노드 label은 최대 20자 내외로 제한.
    - 긴 설명은 반드시 edge label 또는 narration에 넣을 것.
    - label 안에서는 [], 중괄호({{...}}), 백틱(`) 절대 사용 금지. 필요한 경우 () 등으로 대체.
    - 도형 안 여러 줄 금지. <BR/>는 최대 1회까지만 허용.

    ⚠️ Label Rules (STRICT):
    - 모든 노드/에지 label은 HTML label 형식 (label=<...>)으로 작성.
    - 반드시 <FONT FACE="NanumGothic"> ... </FONT> 블록 안에 작성.
    - 긴 설명은 edge label 또는 narration에 배치. 노드 label은 짧게 (최대 20자).
    - <BR/>은 허용하되 최대 1회만 사용.

    ---
    🎯 Layout & Style Hints:
    | Purpose                     | Recommended Layout |
    |-----------------------------|--------------------|
    | Pipeline / Sequential Flow  | dot + rankdir=LR   |
    | Hierarchy / Architecture    | dot + rankdir=TB + clusters |
    | Comparison / Contrast       | dot + clusters     |
    | Relational Network          | neato              |
    | Circular / Spread           | circo              |
    | Trade-off / Balance         | neato or twopi     |
    | Record / Table Structure    | dot + shape=record |

    Now generate visualization for this scene (JSON only):
    {json.dumps(scene, ensure_ascii=False, indent=2)}
    """.strip()

    resp = call_claude(
        prompt,
        model=model or settings.CLAUDE_DEFAULT_MODEL,
        max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
    )
    return resp

def _fix_tool_and_diagram(obj: dict) -> dict:
    """tool/diagram 값이 잘못된 경우 전역적으로 교정"""
    bad_vals = {"graphviz", "dot", "neato", "circo", "twopi"}

    # tool 값이 DOT 코드인 경우 → diagram으로 이동
    tval = obj.get("tool")
    if isinstance(tval, str) and tval.strip().startswith(("digraph", "graph")):
        obj["diagram"] = tval
        obj["tool"] = "graphviz"

    # diagram이 placeholder라면 제거
    dval = obj.get("diagram")
    if isinstance(dval, str) and dval.strip().lower() in bad_vals:
        del obj["diagram"]

    return obj


def classify_scenes_iteratively(
    scenes: list[dict[str, Any]], model: str | None = None, max_tokens: int | None = None
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    used_layouts: list[str] = []

    for scene in scenes:
        raw = classify_single_scene(
            scene, used_layouts=used_layouts, model=model, max_tokens=max_tokens
        )
        raw = _repair_raw_json(raw)

        try:
            obj = _safe_json_loads(raw)
            if isinstance(obj, list) and obj:
                obj = obj[0]
            if not isinstance(obj, dict):
                raise ValueError("Unexpected JSON structure")

            obj.setdefault("scene_id", scene.get("scene_id", 0))
            obj.setdefault("title", scene.get("title", ""))
            obj.setdefault("narration", scene.get("narration", ""))

            # 전역 tool/diagram 교정
            obj = _fix_tool_and_diagram(obj)

            # visualizations 내부도 교정
            vizzes = obj.get("visualizations", [])
            if isinstance(vizzes, list):
                for viz in vizzes:
                    _fix_tool_and_diagram(viz)

            obj = _normalize_viz_keys(obj)
            _hoist_top_level_diagram(obj)

            vizzes = obj.get("visualizations", [])
            if not isinstance(vizzes, list):
                vizzes = []

            for viz in vizzes:
                if viz.get("viz_type") == "diagram":
                    viz["tool"] = "graphviz"
                    layout = viz.get("layout") or obj.get("layout") or "dot"
                    viz["layout"] = layout

                    _assign_unique_layout(viz, used_layouts)
                    if viz["layout"] not in used_layouts:
                        used_layouts.append(viz["layout"])

                    if "diagram" in viz and isinstance(viz["diagram"], str):
                        viz["diagram"] = _enforce_label_rules(viz["diagram"])

                elif viz.get("viz_type") == "illustration":
                    viz["tool"] = "stability"

            # fallback 보장
            if not any(v.get("viz_type") == "diagram" for v in vizzes):
                title = obj.get("title", "제목 없음")
                safe_title = _sanitize_label(title)
                fallback_dot = f'''
                    digraph G {{
                    node [shape=box, fontname="NanumGothic", fontsize=12];
                    "{safe_title}" -> "다음 단계";
                    }}
                    '''.strip()

                vizzes.append(
                    {
                        "viz_type": "diagram",
                        "tool": "graphviz",
                        "viz_label": "auto_fallback",
                        "diagram": fallback_dot,
                        "layout": "dot",
                    }
                )
                if "dot" not in used_layouts:
                    used_layouts.append("dot")

            _ensure_viz_labels(vizzes, obj.get("scene_id"))

            # 중복 라벨 제거
            unique_vizzes, seen = [], set()
            for viz in vizzes:
                label = viz.get("viz_label")
                if label in seen:
                    continue
                seen.add(label)
                unique_vizzes.append(viz)

            obj["visualizations"] = unique_vizzes[:2]
            results.append(obj)

        except Exception:
            results.append(
                {
                    "scene_id": scene.get("scene_id", 0),
                    "title": scene.get("title", ""),
                    "narration": scene.get("narration", ""),
                    "error": "JSON parse failed",
                    "raw": str(raw)[:800],
                }
            )

    return results

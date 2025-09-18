# src/services/llm/viz_classifier.py

import json
import re
from typing import Any
from src.services.llm.client import call_claude
from src.core.config import settings

_MAX_TEXT_CHARS = 3000


def _truncate(s: str, max_len: int = _MAX_TEXT_CHARS) -> str:
    if not s:
        return ""
    return s if len(s) <= max_len else s[:max_len]


def _strip_fences(s: str) -> str:
    s = s.strip()
    # ```json ... ``` 또는 ``` ... ``` 제거
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_first_balanced_json(s: str) -> str | None:
    """
    앞에서부터 첫 번째 '완전한' JSON object 블록({ ... })을 균형 잡힌 중괄호 카운팅으로 추출.
    DOT 코드가 뒤에 이어 붙어도 안전하게 JSON만 떼낸다.
    """
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
    """
    LLM 출력에서 종종 생기는 '\"key\": , \"key\": \"...\"' 패턴 정리.
    첫 번째(값 없는) 키를 제거하고 키 사이 구분용 쉼표 하나만 남긴다.
    """
    # diagram 및 동의어 키들
    keys = r"(diagram|graphviz|graphviz_code|graph|dot|scene_graph|content|layout)"
    # 1) , "key": , "key":
    s = re.sub(rf",\s*\"{keys}\"\s*:\s*,\s*\"{keys}\"\s*:", r", \"\2\":", s, flags=re.DOTALL)
    # 2) "key": , "key":
    s = re.sub(rf"\"{keys}\"\s*:\s*,\s*\"{keys}\"\s*:", r"\"\2\":", s, flags=re.DOTALL)
    # 3) 잔여 ',"key": ,' 단독 패턴 → 구분쉼표 유지
    s = re.sub(rf",\s*\"{keys}\"\s*:\s*,\s*", r", ", s, flags=re.DOTALL)
    # 4) 선행 쉼표 없는 '"key": ,' 패턴 제거
    s = re.sub(rf"\"{keys}\"\s*:\s*,\s*", r"", s, flags=re.DOTALL)
    return s

def _repair_raw_json(s: str) -> str:
    """
    - 코드펜스 제거
    - 툴명 정규화
    - 잘못 붙은 `"diagram": ", "diagram":` 패턴 정리
    - diagram/graphviz/graph/dot/scene_graph 값에서 Graphviz 블록(digraph/graph { ... })을
      괄호매칭으로 정확히 추출하고 JSON 문자열로 안전하게 인코딩해서 삽입
    """
    if not s:
        return ""
    s = s.strip()
    # 코드펜스 제거
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)

    # 툴명 정규화(모델이 가끔 다른 이름으로 내보내는 경우)
    s = s.replace('"excalidraw"', '"graphviz"')
    s = s.replace('"stable-diffusion"', '"stability"')

    # 중복 diagram 키가 붙은 케이스 방지
    s = re.sub(r'("diagram"\s*:\s*)",\s*"diagram"\s*:\s*', r'\1', s)

    aliases = ['"diagram"', '"graphviz"', '"graph"', '"graphviz_code"', '"dot"', '"scene_graph"']

    def _encode_graph_block(text: str, key_pos: int) -> tuple[str, int] | None:
        """key_pos: `"diagram"` 등 키 문자열 끝 직후 위치"""
        # 콜론 찾기
        colon = text.find(":", key_pos)
        if colon == -1:
            return None
        i = colon + 1
        # 공백 스킵
        while i < len(text) and text[i].isspace():
            i += 1
        # 값이 따옴표로 시작했는지
        had_quote = False
        if i < len(text) and text[i] == '"':
            had_quote = True
            i += 1

        # 그래프 코드 시작 검색
        m = re.search(r'(digraph\s+[^{]+\{|\bgraph\s*\{)', text[i:], re.IGNORECASE)
        if not m:
            return None
        start = i + m.start()

        # 중괄호 괄호매칭으로 블록 끝 찾기(문자열 내부 제외)
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
                        end = j + 1  # '}' 포함
                        break
            j += 1
        else:
            # 닫는 괄호를 못 찾으면 포기
            return None

        block = text[start:end]
        encoded = json.dumps(block, ensure_ascii=False)  # 안전한 JSON 문자열 생성

        # 원래 값 구간 제거 범위 계산(닫는 따옴표까지 제거)
        k = end
        if had_quote and k < len(text) and text[k] == '"':
            k += 1

        # 치환 적용
        new_text = text[:colon+1] + " " + encoded + text[k:]
        return new_text, colon + 1 + 1 + len(encoded)  # 새 인덱스(대략) 반환

    # 모든 alias 키에 대해 순차 처리
    idx = 0
    while True:
        # 가장 앞에 등장하는 alias를 찾음
        next_pos = None
        which = None
        for a in aliases:
            p = s.find(a, idx)
            if p != -1 and (next_pos is None or p < next_pos):
                next_pos = p
                which = a
        if next_pos is None:
            break  # 더 없음

        res = _encode_graph_block(s, next_pos + len(which))
        if res is None:
            # 이 alias는 건드릴 수 없으니 다음으로
            idx = next_pos + len(which)
            continue
        s, idx = res

    return s

def _safe_json_loads(s: str):
    """
    - 바로 json.loads 시도
    - 실패 시, 첫 번째 균형잡힌 JSON 오브젝트만 추출하여 재시도
    """
    s_try = s
    try:
        obj = json.loads(s_try)
        if isinstance(obj, str):
            return json.loads(obj)
        return obj
    except Exception:
        pass

    # 코드펜스/이중키 보정이 안 되어 들어왔다면 한 번 더 보정
    s_fixed = _repair_raw_json(s_try)
    try:
        return json.loads(s_fixed)
    except Exception:
        # 최후의 수단: {} 블록만 긁어 재시도
        only_json = _extract_first_balanced_json(s_fixed)
        if only_json:
            return json.loads(only_json)
        # 그래도 실패 시 상위에서 처리
        raise

def _normalize_viz_keys(obj: dict[str, Any]) -> dict[str, Any]:
    """
    graph / graphviz / graphviz_code / dot / scene_graph → diagram 으로 통일
    """
    for key in ["graph", "graphviz", "graphviz_code", "dot", "scene_graph"]:
        if key in obj and "diagram" not in obj:
            obj["diagram"] = obj[key]
            del obj[key]
    return obj

def _hoist_top_level_diagram(obj: dict[str, Any]) -> None:
    """
    top-level에 'diagram'과 'layout'만 있는 경우에도 visualizations 항목으로 승격.
    """
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
    """
    viz_label이 없으면 자동 생성. (중복 제거 로직이 라벨에 의존하기 때문)
    """
    for idx, v in enumerate(vizzes):
        if not v.get("viz_label"):
            v["viz_label"] = f"scene_{scene_id}_v{idx+1}"


def classify_single_scene(
    scene: dict[str, Any],
    used_layouts: list[str] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    scene 하나에 대해 LLM을 호출하여 시각화 지시(JSON 객체)를 생성.
    used_layouts: 이전 씬에서 사용된 레이아웃 리스트
    """

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

---

🎯 Layout & Style Hints:
| Purpose                     | Recommended Layout |
|----------------------------|--------------------|
| Pipeline / Sequential Flow | dot + rankdir=LR   |
| Hierarchy / Architecture   | dot + rankdir=TB + clusters |
| Comparison / Contrast      | dot + clusters     |
| Relational Network         | neato              |
| Circular / Spread          | circo              |
| Trade-off / Balance        | neato or twopi     |
| Record / Table Structure   | dot + shape=record |

Now generate visualization for this scene (JSON only):
{json.dumps(scene, ensure_ascii=False, indent=2)}
    """.strip()

    resp = call_claude(
        prompt,
        model=model or settings.CLAUDE_DEFAULT_MODEL,
        max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
    )
    return resp


def classify_scenes_iteratively(
    scenes: list[dict[str, Any]], model: str | None = None, max_tokens: int | None = None
) -> list[dict[str, Any]]:
    """
    씬 리스트를 순회하며 LLM에 넘기고 결과를 모음.
    레이아웃 다양성을 보장하기 위해 이전 씬들의 layout 목록을 누적 전달.
    """
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

            # 기본 필드 보강
            obj.setdefault("scene_id", scene.get("scene_id", 0))
            obj.setdefault("title", scene.get("title", ""))
            obj.setdefault("narration", scene.get("narration", ""))

            # top-level 키 표준화 및 승격
            obj = _normalize_viz_keys(obj)
            _hoist_top_level_diagram(obj)

            vizzes = obj.get("visualizations", [])
            if not isinstance(vizzes, list):
                vizzes = []

            # viz 표준화 + 레이아웃 기록
            for viz in vizzes:
                if viz.get("viz_type") == "diagram":
                    viz["tool"] = "graphviz"
                    # layout 기본값
                    layout = viz.get("layout") or obj.get("layout") or "dot"
                    viz["layout"] = layout
                    if layout and layout not in used_layouts:
                        used_layouts.append(layout)
                    # code 키 표준화 (nested)
                    for k in ["graph", "graphviz", "graphviz_code", "dot", "scene_graph", "content"]:
                        if k in viz and "diagram" not in viz:
                            viz["diagram"] = viz[k]
                            try:
                                del viz[k]
                            except Exception:
                                pass

                    # 🚩 tool 필드에 DOT 코드가 잘못 들어간 케이스 보정
                    tool_val = viz.get("tool", "")
                    if isinstance(tool_val, str) and tool_val.strip().startswith(("digraph", "graph")):
                        if "diagram" not in viz:
                            viz["diagram"] = tool_val
                        viz["tool"] = "graphviz"

                elif viz.get("viz_type") == "illustration":
                    viz["tool"] = "stability"


            # 최소 하나의 diagram 보장 (없으면 auto_fallback)
            if not any(v.get("viz_type") == "diagram" for v in vizzes):
                vizzes.append(
                    {
                        "viz_type": "diagram",
                        "tool": "graphviz",
                        "viz_label": "auto_fallback",
                        "viz_prompt": "digraph G { A -> B; }",
                        "layout": "dot",
                    }
                )
                if "dot" not in used_layouts:
                    used_layouts.append("dot")

            # 라벨 자동 생성(중복 제거가 라벨 기준이라 필수)
            _ensure_viz_labels(vizzes, obj.get("scene_id"))

            # 중복 제거 + 최대 2개 제한
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

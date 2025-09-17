# src/services/llm/viz_classifier.py

import json
import re
from typing import Any
from src.services.llm.client import call_claude
from src.core.config import settings

# 입력 텍스트 과도 길이 방지
_MAX_TEXT_CHARS = 3000


def _truncate(s: str, max_len: int = _MAX_TEXT_CHARS) -> str:
    if not s:
        return ""
    return s if len(s) <= max_len else s[:max_len]

def _repair_raw_json(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(json)?", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"```$", "", s).strip()
    s = s.replace('"excalidraw"', '"graphviz"')
    s = s.replace('"stable-diffusion"', '"stability"')

    # viz_prompt 안전화: 줄바꿈/따옴표 escape
    s = re.sub(r'("viz_prompt"\s*:\s*")([\s\S]*?)(")', 
               lambda m: m.group(1) + m.group(2).replace("\\n", "\\\\n").replace("\n", "\\\\n").replace('"', '\\"') + m.group(3), 
               s)

    return s



def _safe_json_loads(s: str):
    """
    JSON 문자열 파싱을 안전하게 처리.
    - 필요시 2중 디코딩 (문자열 안의 JSON)
    - 실패하면 { ... } 패턴만 추출
    """
    try:
        obj = json.loads(s)
        if isinstance(obj, str):
            # LLM이 문자열로 감싼 JSON 반환했을 경우
            return json.loads(obj)
        return obj
    except Exception:
        # 객체 부분만 추출
        match = re.search(r"\{[\s\S]*\}", s)
        if match:
            return json.loads(match.group(0))
        raise


def classify_single_scene(
    scene: dict[str, Any],
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    scene 하나에 대해 LLM을 호출하여 시각화 지시(JSON 객체)를 생성.
    JSON 객체 문자열을 반환.
    """

    scene_id = scene.get("scene_id")
    title = str(scene.get("title", "")).strip()
    narration = _truncate(str(scene.get("narration", "")).strip())
    raw_text = _truncate(str(scene.get("raw_text", "")).strip())

    # --- 프롬프트: 논문 그림 스타일 시각화 ---
    prompt = f"""
You are the 'Visualization Designer' for an AI paper storybook.
Your job is to create visualizations that explain AI papers clearly
with **simple, schematic visuals** (like those seen in research papers or slides).

⚠️ Very Important:
- Output must be a single JSON object (not an array).
- Always include "scene_id", "title", and "narration" (same as input).
- Each scene must include **1 to 2 diagrams only**. Use the minimum number needed to avoid redundancy.
- Avoid repeating the same structure with slightly different labels. If one diagram covers the idea, do not generate another similar one.
- Diagrams may cover different aspects as long as they are **non-redundant** and concise.
- Allowed viz_type: "diagram" or "illustration" only.
- Allowed tool values:
  - "graphviz" for diagrams
  - "stability" for illustrations
- Do NOT invent other tool names.
- Do NOT include humans, characters, or metaphorical drawings.
- Use only simple geometric / schematic visuals (grids, bounding boxes, heatmaps, feature maps, arrows).
- For Graphviz DOT code: keep it concise and JSON-safe (escape newlines as \\n if needed), ideally a single line.
- **Illustration is optional** and should be **omitted by default**.
- Only add **at most one** illustration **if strictly necessary** to convey schematic visuals that a diagram cannot express well
  (e.g., spatial grids, heatmaps, attention maps, feature maps). If diagrams suffice, **do NOT** include an illustration.
- Output plain JSON only (no code fences, no markdown, no extra escaping).

Example:
{{
  "scene_id": 1,
  "title": "연구 동기와 문제 정의",
  "narration": "기존 탐지 모델은 복잡한 파이프라인이 필요했다...",
  "visualizations": [
    {{
      "viz_type": "diagram",
      "tool": "graphviz",
      "viz_label": "old vs new pipeline",
      "viz_prompt": "digraph G {{ rankdir=LR; OldMethod -> ComplexPipeline; Proposed -> SimplePipeline; }}"
    }},
    {{
      "viz_type": "diagram",
      "tool": "graphviz",
      "viz_label": "end-to-end flow",
      "viz_prompt": "digraph G {{ rankdir=LR; Input -> Model -> Boxes_And_Probs; }}"
    }}
  ]
}}

Now generate visualizations for this scene:

{{
  "scene_id": {scene_id},
  "title": "{title}",
  "narration": "{narration}",
  "raw_text": "{raw_text}"
}}
""".strip()

    resp = call_claude(
        prompt,
        model=model or settings.CLAUDE_DEFAULT_MODEL,
        max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
    )
    return resp


def classify_scenes_iteratively(
    scenes: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int | None = None,
) -> list[dict[str, Any]]:
    """
    씬 리스트를 순회하며 하나씩 LLM에 넘기고 결과를 모은다.
    - 항상 list[dict] 반환
    - 최소 diagram 하나 보장
    - illustration은 선택적
    """
    results: list[dict[str, Any]] = []

    for scene in scenes:
        raw = classify_single_scene(scene, model=model, max_tokens=max_tokens)
        raw = _repair_raw_json(raw)  # 사전 보정

        try:
            obj = _safe_json_loads(raw)

            # dict 또는 list 첫 원소만 허용
            if isinstance(obj, list) and obj:
                obj = obj[0]
            if not isinstance(obj, dict):
                raise ValueError("Unexpected JSON structure")

            # 필드 보강
            obj.setdefault("scene_id", scene.get("scene_id", 0))
            obj.setdefault("title", scene.get("title", ""))
            obj.setdefault("narration", scene.get("narration", ""))

            # viz 리스트 보정
            vizzes = obj.get("visualizations", [])
            if not isinstance(vizzes, list):
                vizzes = []

            # tool 정규화
            for viz in vizzes:
                if viz.get("viz_type") == "diagram":
                    viz["tool"] = "graphviz"
                elif viz.get("viz_type") == "illustration":
                    viz["tool"] = "stability"

            # 최소 하나의 diagram 보장
            if not any(v.get("viz_type") == "diagram" for v in vizzes):
                vizzes.append({
                    "viz_type": "diagram",
                    "tool": "graphviz",
                    "viz_label": "auto_fallback",
                    "viz_prompt": "digraph G { A -> B; }"
                })
            # 중복 제거 + 최대 개수 제한
            unique_vizzes = []
            seen_labels = set()
            for viz in vizzes:
                label = viz.get("viz_label")
                if not label or label in seen_labels:
                    continue
                seen_labels.add(label)
                unique_vizzes.append(viz)

            # 최대 2개만 유지
            vizzes = unique_vizzes[:2]

            obj["visualizations"] = vizzes
            results.append(obj)

        except Exception:
            results.append({
                "scene_id": scene.get("scene_id", 0),
                "title": scene.get("title", ""),
                "narration": scene.get("narration", ""),
                "error": "JSON parse failed",
                "raw": str(raw)[:500],
            })

    return results

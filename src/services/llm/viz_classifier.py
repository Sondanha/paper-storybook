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
    s = re.sub(
        r'("viz_prompt"\s*:\s*")([\s\S]*?)(")',
        lambda m: m.group(1)
        + m.group(2)
        .replace("\\n", "\\\\n")
        .replace("\n", "\\\\n")
        .replace('"', '\\"')
        + m.group(3),
        s,
    )
    return s


def _safe_json_loads(s: str):
    """
    JSON 문자열 파싱을 안전하게 처리.
    """
    try:
        obj = json.loads(s)
        if isinstance(obj, str):
            return json.loads(obj)
        return obj
    except Exception:
        match = re.search(r"\{[\s\S]*\}", s)
        if match:
            return json.loads(match.group(0))
        raise


def classify_single_scene(
    scene: dict[str, Any], model: str | None = None, max_tokens: int | None = None
) -> str:
    """
    scene 하나에 대해 LLM을 호출하여 시각화 지시(JSON 객체)를 생성.
    """

    scene_id = scene.get("scene_id")
    title = str(scene.get("title", "")).strip()
    narration = _truncate(str(scene.get("narration", "")).strip())
    raw_text = _truncate(str(scene.get("raw_text", "")).strip())

    # --- 프롬프트 ---
    prompt = f"""
You are the 'Visualization Designer' for an AI paper storybook.
Your task: propose **1–2 clear schematic diagrams** (Graphviz DOT).
Illustrations are strongly discouraged — only use them if a diagram
cannot possibly express the idea.

⚠️ Very Important:
- Output ONE JSON object (not array).
- Always include "scene_id", "title", "narration".
- Allowed viz_type: "diagram" (preferred), "illustration" (rare).
- For diagrams: use "tool": "graphviz" and include "layout" ("dot","neato","circo").
- Graphviz code must be JSON-safe (escape newlines as \\n).
- Use context-appropriate styles:
  * Flowchart (rankdir=LR/TB)
  * Hierarchy (clusters)
  * Pipeline (step-by-step)
  * Record/table-like (record shapes)
  * Comparison (side-by-side clusters)
  * Timeline (rankdir=LR)
  * Circular (layout="circo") or relational (layout="neato")

Examples:

Flowchart:
digraph G {{
  rankdir=LR;
  Input -> Process -> Output;
}}

Comparison:
digraph G {{
  subgraph cluster_old {{ label="Old"; A -> B; }}
  subgraph cluster_new {{ label="YOLO"; X -> Y; }}
}}

Timeline:
digraph G {{
  rankdir=LR; 2015 -> 2016 -> 2017 -> 2018;
}}

Now generate visualization for this scene:

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
    """
    results: list[dict[str, Any]] = []

    for scene in scenes:
        raw = classify_single_scene(scene, model=model, max_tokens=max_tokens)
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
                vizzes.append(
                    {
                        "viz_type": "diagram",
                        "tool": "graphviz",
                        "viz_label": "auto_fallback",
                        "viz_prompt": "digraph G { A -> B; }",
                        "layout": "dot",
                    }
                )

            # 중복 제거 + 최대 2개 제한
            unique_vizzes, seen = [], set()
            for viz in vizzes:
                label = viz.get("viz_label")
                if not label or label in seen:
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
                    "raw": str(raw)[:500],
                }
            )

    return results

# src/services/llm/viz_classifier.py
"""
Scene → (viz_type, tool, prompt) 생성기

목표
- 내레이션과 일치하는 시각화 지시어를 LLM 한 번 호출로 생성
- diagram/figure/illustration 을 통일된 JSON 스키마로 반환
- 툴별 프롬프트 차이(Graphviz/Mermaid, Diffusion 프롬프트 스타일)까지 포함
- viz_rules.yaml이 있으면 반영, 없으면 안전한 기본값으로 동작

주의
- 출력은 반드시 JSON (코드펜스 금지)
- prompt에는 백틱(`)이나 ``` 같은 마크다운 코드펜스를 넣지 말 것
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from src.services.llm.client import call_claude
from src.core.config import settings

# 지원 범주(최종 타입)
VIZ_TYPES = {"diagram", "figure", "illustration"}

# 다이어그램 툴 우선순위: 프로젝트 합의가 없다면 Graphviz 우선
DEFAULT_DIAGRAM_TOOL = "graphviz"   # or "mermaid"
# 일러스트레이션 프롬프트 타깃: 외부 API에 맞춰 텍스트만 생성
DEFAULT_ILLUST_TOOL = "stability"   # arbitrary label: "stability" | "flux" | "openai_images" 등
# figure는 원본 figure + annotation 계획만 돌려준다
DEFAULT_FIGURE_TOOL = "annotation"

# 입력 텍스트 과도 길이 방지
_MAX_TEXT_CHARS = 6000  # 장황한 본문 방어용

# viz_rules.yaml 경로 (있으면 사용)
_VIZ_RULES_PATH = Path("configs/viz_rules.yaml")


def _truncate(s: str, max_len: int = _MAX_TEXT_CHARS) -> str:
    if s is None:
        return ""
    return s if len(s) <= max_len else s[:max_len]


def _load_viz_rules() -> Optional[Dict[str, Any]]:
    """
    viz_rules.yaml 형식을 읽어온다.
    없거나 파싱 실패하면 None.
    """
    if not _VIZ_RULES_PATH.exists():
        return None
    try:
        import yaml  # 선택 의존성
        with _VIZ_RULES_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _build_prompt(scene: Dict[str, Any], rules: Optional[Dict[str, Any]], prefer_tool: Optional[str]) -> str:
    """
    LLM에게 줄 프롬프트를 생성.
    - viz_type 분류 + tool 선택 + prompt 생성까지 한 번에.
    - 출력은 JSON only (코드펜스 금지).
    """
    title = scene.get("title", "")
    narration = scene.get("narration", "")
    raw_text = scene.get("raw_text", "")

    narration = _truncate(narration, 3000)
    raw_text = _truncate(raw_text, 3000)

    # 규칙을 문자열로 삽입(선택)
    rules_str = ""
    if rules:
        try:
            rules_str = json.dumps(rules, ensure_ascii=False, indent=2)
        except Exception:
            rules_str = ""

    # 선호 도구 힌트
    tool_hint = (
        f"- 선호 도구 힌트: '{prefer_tool}'를 우선 고려하되, 장면 성격과 부합하지 않으면 무시 가능.\n"
        if prefer_tool else ""
    )

    # 도구별 프롬프트 제약 안내
    tool_guidance = f"""
도구별 출력 규칙:
- diagram + graphviz: prompt에는 순수 DOT 문법만 포함. 예) "digraph G {{ A -> B; B -> C; }}"
- diagram + mermaid: prompt에는 순수 Mermaid 문법만 포함. 예) "graph LR; A[기존 방법]-->B[한계]; B-->C[Transformer];"
- figure + annotation: prompt에는 강조/주석 계획을 한국어로 기술. 예) "Figure 3의 손실함수 도식에서 'Self-Attention' 부분에 붉은 테두리 박스, 캡션: ..."
- illustration + stability/flux/openai_images: 순수 텍스트 프롬프트. 장면 핵심, 구도, 요소, 스타일을 한국어로 간결히. 금지: 카메라/렌즈 과잉, 저작권 캐릭터 직접 지시.

반드시 다음 JSON 스키마로만 출력(코드펜스 금지):
{{
  "scene_id": {scene.get("scene_id", 0)},
  "viz_type": "diagram | figure | illustration",
  "viz_label": "flowchart | block_diagram | original_figure | conceptual_illustration | ...",
  "tool": "graphviz | mermaid | annotation | stability | flux | openai_images",
  "viz_prompt": "툴에 바로 넘길 문자열. 코드펜스/백틱 금지",
  "meta": {{
    "language": "ko",
    "aspect": "16:9 | 1:1 | 4:3 (선택)",
    "notes": "선택적 설명"
  }}
}}
"""

    prompt = f"""
당신은 AI 논문 스토리북 제작 파이프라인의 '시각화 설계자'입니다.
아래 Scene의 내레이션을 바탕으로 알맞은 시각화 유형과 툴별 지시문을 생성하세요.
출력은 반드시 한국어 JSON 한 덩어리만, 코드펜스 없이.

장면 정보:
- 제목: {title}
- 내레이션(요약 기반 설명): {narration}

참고 원문 일부(선택 사용): {raw_text}

분류 대상(최종 타입): {sorted(VIZ_TYPES)}
{tool_hint}

규칙 매핑(viz_rules.yaml; 없으면 무시해도 됨):
{rules_str if rules_str else "(규칙 파일 없음)"}

의도:
- 내레이션과 그림이 반드시 의미적으로 일치할 것.
- diagram은 구조/흐름을 간결하게, figure는 원문 도식 강조 계획을, illustration은 개념 비유/메타포를.
- 출력은 JSON만. 백틱(`)이나 ``` 같은 코드펜스 금지. 불필요한 텍스트 금지.

{tool_guidance}
    """.strip()

    return prompt


def _sanitize_and_complete(obj: Dict[str, Any], prefer_tool: Optional[str]) -> Dict[str, Any]:
    """
    LLM JSON 응답을 최종 사용 형태로 정제.
    - 누락 필드 채움
    - 잘못된 필드 값 교정
    """
    out: Dict[str, Any] = {}
    out["scene_id"] = obj.get("scene_id", 0)

    # viz_type 정규화
    vt = (obj.get("viz_type") or "").strip().lower()
    if vt not in VIZ_TYPES:
        # 일단 다이어그램으로 폴백
        vt = "diagram"
    out["viz_type"] = vt

    # tool 정규화
    tool = (obj.get("tool") or "").strip().lower()
    if vt == "diagram":
        if prefer_tool in {"graphviz", "mermaid"}:
            tool = prefer_tool
        if tool not in {"graphviz", "mermaid"}:
            tool = DEFAULT_DIAGRAM_TOOL
    elif vt == "figure":
        tool = "annotation"
    else:  # illustration
        # 외부 서비스 이름은 자유롭게 쓰되 내부 라벨을 유지
        if tool not in {"stability", "flux", "openai_images"}:
            tool = DEFAULT_ILLUST_TOOL
    out["tool"] = tool

    out["viz_label"] = obj.get("viz_label") or ""
    # prompt: 코드펜스/백틱 제거
    vp = (obj.get("viz_prompt") or "").strip()
    vp = vp.replace("```", "").replace("`", "")
    out["viz_prompt"] = vp

    meta = obj.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("language", "ko")
    out["meta"] = meta

    return out


def classify_viz(
    scene: Dict[str, Any],
    prefer_tool: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Scene(dict: scene_id, title, narration, raw_text) → {scene_id, viz_type, tool, viz_prompt, meta}

    prefer_tool:
      - diagram일 때 "graphviz" 또는 "mermaid" 힌트
      - illustration일 때 "stability" | "flux" | "openai_images" 힌트
    """
    rules = _load_viz_rules()
    prompt = _build_prompt(scene, rules, prefer_tool)

    # 기본은 가성비 Haiku, 필요 시 인자로 오버라이드
    model_name = model or getattr(settings, "CLAUDE_DEFAULT_MODEL", "claude-3-5-haiku-20241022")
    max_out = max_tokens or getattr(settings, "CLAUDE_MAX_TOKENS", 1024)

    resp = call_claude(prompt, model=model_name, max_tokens=max_out)

    try:
        data = json.loads(resp)
    except Exception:
        # 파싱 실패 시 매우 안전한 폴백: 간단 플로우 다이어그램
        simple = f'digraph G {{ start[label="{scene.get("title", "Scene")}"]; narr[label="요점: {scene.get("narration","")[:50]}"]; start -> narr; }}'
        return {
            "scene_id": scene.get("scene_id", 0),
            "viz_type": "diagram",
            "viz_label": "flowchart",
            "tool": DEFAULT_DIAGRAM_TOOL,
            "viz_prompt": simple,
            "meta": {"language": "ko", "notes": "fallback: JSON parse failed"},
        }

    return _sanitize_and_complete(data, prefer_tool=prefer_tool)


def classify_viz_batch(
    scenes: List[Dict[str, Any]],
    prefer_tool: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    여러 Scene을 순차 처리. 병렬화는 RQ/Worker에서.
    """
    results: List[Dict[str, Any]] = []
    for s in scenes:
        try:
            results.append(classify_viz(s, prefer_tool=prefer_tool, model=model, max_tokens=max_tokens))
        except Exception as e:
            # 한 장면 실패해도 전체는 계속
            results.append({
                "scene_id": s.get("scene_id", 0),
                "viz_type": "diagram",
                "viz_label": "flowchart",
                "tool": DEFAULT_DIAGRAM_TOOL,
                "viz_prompt": f'digraph G {{ err[label="viz error: {str(e)[:60]}"]; }}',
                "meta": {"language": "ko", "notes": "error fallback"},
            })
    return results

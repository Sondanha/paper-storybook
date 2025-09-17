# src/services/llm/scene_splitter.py

import re
import json
from pathlib import Path

from src.services.llm.client import call_claude
from src.core.config import settings

# --- 추가: 입력 길이 제한 ---
_MAX_TEXT_CHARS = 3000
def _truncate(s: str, max_len: int = _MAX_TEXT_CHARS) -> str:
    if not s:
        return ""
    return s if len(s) <= max_len else s[:max_len]


SCENE_SPLIT_PROMPT = """
당신은 AI 연구 논문의 내용을 스토리북(Scene) 단위로 재구성하는 내레이터입니다.
주어진 본문 텍스트를 장면(Scene) 단위로 나누고, 각 장면마다 독자가 이해하기 쉬운
한국어 내레이션을 작성하세요.

⚠️ 출력 규칙 (아주 중요):
- 반드시 JSON 배열만 출력해야 함. 불필요한 텍스트, 설명, 코드펜스(```) 모두 금지.
- JSON 배열 내부의 각 객체는 아래 스키마를 따라야 함.

출력 예시 (반드시 동일한 형식 유지):
[
  {
    "scene_id": 1,
    "title": "연구 동기와 문제 정의",
    "narration": "이 연구는 기존 모델의 한계를 설명하며 시작합니다...",
    "raw_text": "Recurrent neural networks ... have limitations in ..."
  },
  {
    "scene_id": 2,
    "title": "제안된 방법론",
    "narration": "새로운 접근법을 소개하며 장점과 차별점을 강조합니다.",
    "raw_text": "We propose a novel architecture ..."
  }
]

조건:
1. 장면 수는 반드시 10~12개로 분할할 것.
2. 1개 또는 2개 장면만 출력하는 것은 절대 허용되지 않음.
3. 내레이션은 한국어로 작성하되, 주요 용어는 영어 원어를 병기할 수 있음.
4. raw_text에는 해당 장면에 대응되는 원문 일부를 그대로 포함시킬 것.
5. 반드시 JSON 배열만 출력하고, 다른 문장/코멘트/코드펜스는 절대 포함하지 말 것.
"""

def _sanitize_scene(scene: dict) -> dict[str, str | int]:
    return {
        "scene_id": int(scene.get("scene_id", 0)) if str(scene.get("scene_id", "")).isdigit() else 0,
        "title": str(scene.get("title", "") or "").strip(),
        "narration": str(scene.get("narration", "") or "").strip(),
        # 역슬래시 안전 처리
        "raw_text": str(scene.get("raw_text", "") or "").replace("\\", "\\\\").strip(),
    }

def _extract_json_array(text: str) -> str | None:
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        return match.group(0)
    return None

def _safe_json_loads(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        # 1차 실패 → 백슬래시 이스케이프 처리
        fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)
        return json.loads(fixed)


def split_into_scenes_with_narration(full_text: str) -> list[dict[str, str | int]]:
    safe_text = _truncate(full_text)

    def _call_splitter(text: str, extra_prompt: str = "") -> str:
        prompt = f"{SCENE_SPLIT_PROMPT}{extra_prompt}\n\n논문 본문:\n{text}"
        return call_claude(
            prompt,
            model=settings.CLAUDE_DEFAULT_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
        )

    response = _call_splitter(safe_text)

    def _parse_response(resp: str):
        try:
            return _safe_json_loads(resp)
        except Exception:
            json_str = _extract_json_array(resp)
            if json_str:
                return _safe_json_loads(json_str)
            return None

    scenes = _parse_response(response)

    # --- Retry 로직: scene이 2개 이하일 경우 ---
    if not isinstance(scenes, list) or len(scenes) <= 2:
        retry_resp = _call_splitter(
            safe_text,
            extra_prompt="\n⚠️ 장면이 10개 미만이면 규칙 위반입니다. 반드시 10~12개 장면을 생성하세요."
        )
        scenes = _parse_response(retry_resp) or scenes

    if not isinstance(scenes, list):
        return [{
            "scene_id": 0,
            "title": "RAW_OUTPUT",
            "narration": str(response)[:500],
            "raw_text": "",
        }]

    return [_sanitize_scene(s) for s in scenes]

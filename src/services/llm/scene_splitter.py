# src/services/llm/scene_splitter.py

from typing import List, Dict
import json
import re

from src.services.llm.client import call_claude
from src.core.config import settings  # 모델 기본값 관리


SCENE_SPLIT_PROMPT = """
당신은 AI 연구 논문의 내용을 스토리북(Scene) 단위로 재구성하는 내레이터입니다.
주어진 본문 텍스트를 장면(Scene) 단위로 나누고, 각 장면마다 독자가 이해하기 쉬운
한국어 내레이션을 작성하세요.

⚠️ 출력 규칙 (매우 중요):
- 반드시 JSON 배열만 출력할 것. 설명/해설/코드펜스/불필요한 텍스트 금지.
- JSON 배열 내부의 각 객체는 아래 스키마를 따라야 함.

출력 형식:
[
  {
    "scene_id": 1,
    "title": "장면 제목",
    "narration": "내레이션 텍스트",
    "raw_text": "해당 장면의 원문 일부"
  },
  ...
]

조건:
1. 장면 수는 보통 5~15개로, 논문의 흐름을 유지할 것.
2. 내레이션은 한국어로 작성하되, 주요 용어는 영어 원어를 병기할 수 있음.
3. raw_text에는 해당 장면에 대응되는 원문 일부를 그대로 포함시킬 것.
4. 반드시 JSON 배열만 출력하고, 코드펜스(```)나 백틱(`)은 넣지 말 것.
"""


def safe_json_loads(text: str):
    """
    LLM 응답에서 JSON 배열만 안전하게 추출.
    """
    try:
        return json.loads(text)
    except Exception:
        # 응답 중에서 JSON 배열 부분만 추출
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def split_into_scenes_with_narration(full_text: str) -> List[Dict]:
    """
    논문 전체 텍스트를 받아 Claude API를 통해
    Scene 분리 + 내레이션을 동시에 생성합니다.

    Args:
        full_text: 논문 전체 본문 (string)

    Returns:
        scenes: [{"scene_id": int, "title": str, "narration": str, "raw_text": str}, ...]
    """
    prompt = f"{SCENE_SPLIT_PROMPT}\n\n논문 본문:\n{full_text}"

    response = call_claude(
        prompt,
        model=settings.CLAUDE_DEFAULT_MODEL,
        max_tokens=settings.CLAUDE_MAX_TOKENS
    )

    scenes = safe_json_loads(response)

    if not scenes:
        print("[SceneSplitter] JSON 파싱 실패, RAW 응답 반환")
        scenes = [{
            "scene_id": 0,
            "title": "RAW_OUTPUT",
            "narration": response,
            "raw_text": ""
        }]

    return scenes

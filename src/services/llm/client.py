# src/services/llm/client.py

from anthropic import Anthropic
from src.core.config import settings

# Claude API 클라이언트 초기화
anthropic = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

def call_claude(prompt: str, model: str = None, max_tokens: int = None) -> str:
    """
    Claude API 호출 함수
    - prompt: LLM에 전달할 프롬프트 문자열
    - model: 사용할 Claude 모델 (None이면 기본값)
    - max_tokens: 최대 출력 토큰 수 (None이면 기본값)
    """
    try:
        response = anthropic.messages.create(
            model=model or settings.CLAUDE_DEFAULT_MODEL,
            max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"[ClaudeClient] API 호출 실패: {e}")
        raise

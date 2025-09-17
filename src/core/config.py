import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings:
    # Claude API 키
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # 기본 LLM 모델 (없으면 fallback)
    CLAUDE_DEFAULT_MODEL: str = os.getenv(
        "CLAUDE_DEFAULT_MODEL", "claude-3-5-haiku-20241022"
    )

    # 최대 토큰 수 (없으면 기본 2048)
    CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "2048"))

settings = Settings()

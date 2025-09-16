# src/core/config.py
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings:
    # Claude API 키
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # 기본 LLM 모델
    CLAUDE_DEFAULT_MODEL: str = "claude-3-5-haiku-20241022"  # 저렴하고 빠른 모델

    # 최대 토큰 수 (필요시 조정)
    CLAUDE_MAX_TOKENS: int = 2048

settings = Settings()

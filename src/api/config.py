# src/api/config.py
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis 설정
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    queue_name: str = "storybook"

    # 데이터 디렉토리
    data_dir: Path = Path("data")
    processed_dir: Path = data_dir / "processed"
    viz_dir: Path = data_dir / "viz_jpg"
    scene_dir: Path = data_dir / "scenes"
    output_dir: Path = data_dir / "output"

    # Anthropic / Claude 관련 (env에서 들어오는 값)
    anthropic_api_key: str | None = None
    claude_default_model: str | None = None
    claude_max_tokens: int | None = None

    # Pydantic v2 설정
    model_config = {
        "env_file": ".env",
        "extra": "forbid",  # 정의 안 된 키가 있으면 에러, 필요 없으면 "ignore"
    }


settings = Settings()
# python -m uvicorn src.api.main:app --reload

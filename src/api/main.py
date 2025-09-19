from fastapi import FastAPI
from src.api import storybooks

def create_app() -> FastAPI:
    app = FastAPI(
        title="Paper Storybook API",
        description="논문 PDF → 스토리북 변환 서비스",
        version="0.1.0",
    )

    # Storybook 변환 API
    app.include_router(storybooks.router, tags=["storybooks"])

    # Health check 엔드포인트
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app

app = create_app()

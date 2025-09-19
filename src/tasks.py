# src/tasks.py
from rq import Queue
from redis import Redis
from src.texprep.pipeline import run_pipeline
from src.api.config import settings

# Redis 연결
redis_conn = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
)
q = Queue(settings.queue_name, connection=redis_conn)


def preprocess_task(cfg: dict, main_tex: str | None = None) -> dict:
    """
    Worker에서 실행할 전처리 태스크
    """
    result = run_pipeline(cfg, main_tex=main_tex)
    return result


def enqueue_preprocess(cfg: dict, main_tex: str | None = None):
    """
    API에서 호출할 함수. 실제 Job을 큐에 넣는다.
    """
    job = q.enqueue(preprocess_task, cfg, main_tex)
    return {"job_id": job.get_id(), "status": job.get_status()}

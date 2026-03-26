import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request

from app.api.routes import admin, auth, chat, documents, health, jobs
from app.core.config import get_settings
from app.core.logging import request_id_ctx, setup_logging
from app.db.base import Base
from app.db.session import engine

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request_id_ctx.set(request_id)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info("%s %s %s %.2fms", request.method, request.url.path, response.status_code, elapsed)
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(jobs.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.exception_handlers import (
    app_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.db.init_db import init_development_environment
from app.workers import JobWorker

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_development_environment()
    worker = JobWorker()
    worker.start()
    logger.info("Application started")
    try:
        yield
    finally:
        worker.stop()
        logger.info("Application stopped")


app = FastAPI(
    title="AI Scene Detector",
    version=get_settings().app_version,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    started_at = time.perf_counter()
    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.headers["x-request-id"] = request_id
    response.headers["x-process-time-ms"] = f"{elapsed_ms:.2f}"
    if get_settings().request_log_enabled:
        logger.info(
            "HTTP %s %s %s %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={"request_id": request_id},
        )
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(api_router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

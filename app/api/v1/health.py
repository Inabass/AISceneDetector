from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.health import HealthData, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    db.execute(text("SELECT 1"))
    return HealthResponse(
        data=HealthData(
            status="ok",
            app_name=settings.app_name,
            version=settings.app_version,
            database="ok",
            storage_root=str(settings.storage_root),
        ),
        request_id=getattr(request.state, "request_id", None),
    )

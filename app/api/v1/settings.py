from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.settings import SettingData, SettingsListResponse, SettingsUpdateRequest
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsListResponse)
def list_settings(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SettingsListResponse:
    data = SettingsService(db, settings).list_editable()
    return SettingsListResponse(
        data=[SettingData(**item) for item in data],
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("", response_model=SettingsListResponse)
def update_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SettingsListResponse:
    data = SettingsService(db, settings).set_editable(payload.values)
    return SettingsListResponse(
        data=[SettingData(**item) for item in data],
        request_id=getattr(request.state, "request_id", None),
    )

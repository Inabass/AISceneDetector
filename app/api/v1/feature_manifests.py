from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.feature import FeatureManifestData, FeatureManifestResponse
from app.services.feature_manifest_service import FeatureManifestService

router = APIRouter(prefix="/features", tags=["features"])


@router.get("/{feature_id}/manifest", response_model=FeatureManifestResponse)
def get_feature_manifest(
    feature_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FeatureManifestResponse:
    manifest = FeatureManifestService(db, settings).load_manifest(feature_id)
    return FeatureManifestResponse(
        data=FeatureManifestData.model_validate(manifest.model_dump()),
        request_id=getattr(request.state, "request_id", None),
    )

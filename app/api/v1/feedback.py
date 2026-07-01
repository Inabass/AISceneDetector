import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.feedback import DetectionFeedback
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackData,
    FeedbackListResponse,
    FeedbackResponse,
)
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201)
def create_feedback(
    payload: FeedbackCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FeedbackResponse:
    feedback = FeedbackService(db, settings).create_feedback(
        detection_id=payload.detection_id,
        segment_id=payload.segment_id,
        label=payload.label,
        memo=payload.memo,
        source=payload.source,
    )
    return FeedbackResponse(
        data=to_feedback_data(feedback),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("", response_model=FeedbackListResponse)
def list_feedback(
    request: Request,
    limit: int = 100,
    detection_id: int | None = None,
    segment_id: int | None = None,
    label: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FeedbackListResponse:
    feedback_items = FeedbackService(db, settings).list_feedback(
        limit=limit,
        detection_id=detection_id,
        segment_id=segment_id,
        label=label,
    )
    return FeedbackListResponse(
        data=[to_feedback_data(feedback) for feedback in feedback_items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{feedback_id}", response_model=FeedbackResponse)
def get_feedback(
    feedback_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FeedbackResponse:
    feedback = FeedbackService(db, settings).get_feedback(feedback_id)
    return FeedbackResponse(
        data=to_feedback_data(feedback),
        request_id=getattr(request.state, "request_id", None),
    )


def to_feedback_data(feedback: DetectionFeedback) -> FeedbackData:
    return FeedbackData(
        id=feedback.id,
        detection_result_id=feedback.detection_result_id,
        segment_id=feedback.segment_id,
        model_version_id=feedback.model_version_id,
        label=feedback.label,
        source=feedback.source,
        memo=feedback.memo,
        start_sec=feedback.start_sec,
        end_sec=feedback.end_sec,
        score=feedback.score,
        metadata=json.loads(feedback.metadata_json),
    )

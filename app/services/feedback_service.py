import json

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.unit_of_work import UnitOfWork
from app.models.feedback import DetectionFeedback
from app.repositories.detection_repository import DetectionRepository
from app.repositories.feedback_repository import FeedbackRepository

VALID_FEEDBACK_LABELS = {"positive", "negative", "ignore"}


class FeedbackService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.feedback_repository = FeedbackRepository(db)
        self.detection_repository = DetectionRepository(db)

    def create_feedback(
        self,
        detection_id: int,
        label: str,
        segment_id: int | None = None,
        memo: str | None = None,
        source: str = "manual",
    ) -> DetectionFeedback:
        normalized_label = label.strip().lower()
        if normalized_label not in VALID_FEEDBACK_LABELS:
            raise ValidationAppError(
                message="Feedback label must be positive, negative, or ignore.",
                detail={"label": label},
            )
        detection = self.detection_repository.get(detection_id)
        if detection is None:
            raise NotFoundError(
                message="Detection result was not found.",
                detail={"detection_id": detection_id},
            )
        if detection.status != "succeeded":
            raise ValidationAppError(
                message="Feedback can only be added to succeeded detections.",
                detail={"detection_id": detection_id, "status": detection.status},
                suggested_action="Wait for the detection job to finish.",
            )

        segment = None
        if segment_id is not None:
            segment = self.detection_repository.get_segment(segment_id)
            if segment is None or segment.detection_result_id != detection.id:
                raise ValidationAppError(
                    message="Feedback segment does not belong to the detection result.",
                    detail={"detection_id": detection_id, "segment_id": segment_id},
                )

        metadata = {
            "purpose": "model_improvement_feedback",
            "source_video_path": detection.source_video_path,
            "source_filename": detection.source_filename,
            "source_sha256": detection.source_sha256,
            "detection_status": detection.status,
        }
        if segment is not None:
            metadata["segment_index"] = segment.segment_index
            metadata["representative_timestamp_sec"] = (
                segment.representative_timestamp_sec
            )

        feedback = DetectionFeedback(
            detection_result_id=detection.id,
            segment_id=segment.id if segment else None,
            model_version_id=detection.model_version_id,
            label=normalized_label,
            source=source.strip()[:64] or "manual",
            memo=memo.strip() if memo and memo.strip() else None,
            start_sec=segment.padded_start_sec if segment else None,
            end_sec=segment.padded_end_sec if segment else None,
            score=segment.score if segment else None,
            metadata_json=json.dumps(metadata, ensure_ascii=True),
        )
        with UnitOfWork(self.db):
            self.feedback_repository.add(feedback)
        self.db.refresh(feedback)
        return feedback

    def get_feedback(self, feedback_id: int) -> DetectionFeedback:
        feedback = self.feedback_repository.get(feedback_id)
        if feedback is None:
            raise NotFoundError(
                message="Feedback was not found.",
                detail={"feedback_id": feedback_id},
            )
        return feedback

    def list_feedback(
        self,
        limit: int = 100,
        detection_id: int | None = None,
        segment_id: int | None = None,
        label: str | None = None,
    ) -> list[DetectionFeedback]:
        normalized_label = label.strip().lower() if label else None
        if normalized_label is not None and normalized_label not in VALID_FEEDBACK_LABELS:
            raise ValidationAppError(
                message="Feedback label must be positive, negative, or ignore.",
                detail={"label": label},
            )
        return self.feedback_repository.list_recent(
            limit=limit,
            detection_id=detection_id,
            segment_id=segment_id,
            label=normalized_label,
        )

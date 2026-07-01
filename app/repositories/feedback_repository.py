from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import DetectionFeedback
from app.repositories.base import Repository


class FeedbackRepository(Repository[DetectionFeedback]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def add(self, feedback: DetectionFeedback) -> DetectionFeedback:
        self.db.add(feedback)
        return feedback

    def get(self, feedback_id: int) -> DetectionFeedback | None:
        return self.db.get(DetectionFeedback, feedback_id)

    def list_recent(
        self,
        limit: int = 100,
        detection_id: int | None = None,
        segment_id: int | None = None,
        label: str | None = None,
    ) -> list[DetectionFeedback]:
        statement = select(DetectionFeedback)
        if detection_id is not None:
            statement = statement.where(
                DetectionFeedback.detection_result_id == detection_id
            )
        if segment_id is not None:
            statement = statement.where(DetectionFeedback.segment_id == segment_id)
        if label is not None:
            statement = statement.where(DetectionFeedback.label == label)
        statement = statement.order_by(DetectionFeedback.created_at.desc()).limit(limit)
        return list(self.db.execute(statement).scalars())

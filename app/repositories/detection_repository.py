from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detection import DetectionResult
from app.repositories.base import Repository


class DetectionRepository(Repository[DetectionResult]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def add(self, detection: DetectionResult) -> DetectionResult:
        self.db.add(detection)
        return detection

    def get(self, detection_id: int) -> DetectionResult | None:
        return self.db.get(DetectionResult, detection_id)

    def list_recent(self, limit: int = 50) -> list[DetectionResult]:
        return list(
            self.db.execute(
                select(DetectionResult)
                .order_by(DetectionResult.created_at.desc())
                .limit(limit)
            ).scalars()
        )

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detection import DetectionResult, DetectionSegment
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

    def add_segment(self, segment: DetectionSegment) -> DetectionSegment:
        self.db.add(segment)
        return segment

    def list_segments(self, detection_id: int) -> list[DetectionSegment]:
        return list(
            self.db.execute(
                select(DetectionSegment)
                .where(DetectionSegment.detection_result_id == detection_id)
                .order_by(DetectionSegment.segment_index.asc())
            ).scalars()
        )

    def delete_segments(self, detection_id: int) -> None:
        for segment in self.list_segments(detection_id):
            self.db.delete(segment)

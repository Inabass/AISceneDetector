from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.training_video import TrainingVideo
from app.repositories.base import Repository


class TrainingVideoRepository(Repository[TrainingVideo]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def add(self, video: TrainingVideo) -> TrainingVideo:
        self.db.add(video)
        return video

    def get(self, video_id: int) -> TrainingVideo | None:
        return self.db.get(TrainingVideo, video_id)

    def list_recent(self, limit: int = 50) -> list[TrainingVideo]:
        return list(
            self.db.execute(
                select(TrainingVideo)
                .order_by(TrainingVideo.created_at.desc())
                .limit(limit)
            ).scalars()
        )

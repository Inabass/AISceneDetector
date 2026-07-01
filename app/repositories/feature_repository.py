from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feature import Feature
from app.models.training_video import TrainingVideo
from app.repositories.base import Repository


class FeatureRepository(Repository[Feature]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def add(self, feature: Feature) -> Feature:
        self.db.add(feature)
        return feature

    def get(self, feature_id: int) -> Feature | None:
        return self.db.get(Feature, feature_id)

    def get_succeeded_by_cache_key(self, cache_key: str) -> Feature | None:
        return self.db.execute(
            select(Feature)
            .where(Feature.cache_key == cache_key, Feature.status == "succeeded")
            .order_by(Feature.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def list_succeeded_training_features(self) -> list[tuple[Feature, TrainingVideo]]:
        return list(
            self.db.execute(
                select(Feature, TrainingVideo)
                .join(TrainingVideo, TrainingVideo.id == Feature.source_video_id)
                .where(
                    Feature.kind == "training_frame_features",
                    Feature.status == "succeeded",
                    TrainingVideo.validation_status == "valid",
                    TrainingVideo.processing_status == "READY",
                )
                .order_by(TrainingVideo.label_type.asc(), Feature.created_at.desc())
            ).all()
        )

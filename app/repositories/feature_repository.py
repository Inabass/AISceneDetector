from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feature import Feature
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

    def list_by_cache_key(self, cache_key: str) -> list[Feature]:
        return list(
            self.db.execute(
                select(Feature)
                .where(Feature.cache_key == cache_key)
                .order_by(Feature.created_at.asc())
            ).scalars()
        )

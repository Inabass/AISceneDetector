from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.model import AiModel, ModelVersion
from app.repositories.base import Repository


class ModelRepository(Repository[AiModel]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def add_model(self, model: AiModel) -> AiModel:
        self.db.add(model)
        return model

    def add_version(self, version: ModelVersion) -> ModelVersion:
        self.db.add(version)
        return version

    def get_model(self, model_id: int) -> AiModel | None:
        return self.db.execute(
            select(AiModel).where(AiModel.id == model_id, AiModel.deleted_at.is_(None))
        ).scalar_one_or_none()

    def list_models(self) -> list[AiModel]:
        return list(
            self.db.execute(
                select(AiModel)
                .where(AiModel.deleted_at.is_(None))
                .order_by(AiModel.created_at.desc())
            ).scalars()
        )

    def get_version(self, version_id: int) -> ModelVersion | None:
        return self.db.get(ModelVersion, version_id)

    def get_active_version(self, model: AiModel) -> ModelVersion | None:
        if model.active_version_id is None:
            return None
        return self.get_version(model.active_version_id)

    def list_versions(self, model_id: int) -> list[ModelVersion]:
        return list(
            self.db.execute(
                select(ModelVersion)
                .where(ModelVersion.model_id == model_id)
                .order_by(ModelVersion.id.desc())
            ).scalars()
        )

    def next_version_number(self, model_id: int) -> int:
        count = self.db.execute(
            select(func.count(ModelVersion.id)).where(ModelVersion.model_id == model_id)
        ).scalar_one()
        return int(count) + 1

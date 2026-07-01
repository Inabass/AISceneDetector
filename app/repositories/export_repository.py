from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.export import Export
from app.repositories.base import Repository


class ExportRepository(Repository[Export]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def add(self, export: Export) -> Export:
        self.db.add(export)
        return export

    def get(self, export_id: int) -> Export | None:
        return self.db.get(Export, export_id)

    def list_by_job(self, job_id: int) -> list[Export]:
        return list(
            self.db.execute(
                select(Export).where(Export.job_id == job_id).order_by(Export.id.asc())
            ).scalars()
        )

    def list_recent(self, limit: int = 50) -> list[Export]:
        return list(
            self.db.execute(
                select(Export).order_by(Export.created_at.desc()).limit(limit)
            ).scalars()
        )

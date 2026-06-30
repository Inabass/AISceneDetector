from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import AppSetting
from app.repositories.base import Repository


class SettingsRepository(Repository[AppSetting]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_key(self, key: str) -> AppSetting | None:
        return self.db.execute(
            select(AppSetting).where(AppSetting.key == key)
        ).scalar_one_or_none()

    def upsert(
        self,
        key: str,
        value_json: str,
        editable: bool = True,
        description: str | None = None,
    ) -> AppSetting:
        setting = self.get_by_key(key)
        if setting is None:
            setting = AppSetting(
                key=key,
                value_json=value_json,
                editable=editable,
                description=description,
            )
            self.db.add(setting)
        else:
            setting.value_json = value_json
            setting.editable = editable
            setting.description = description
        return setting

import json
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.settings_repository import SettingsRepository


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.repository = SettingsRepository(db)

    def get(self, key: str) -> Any | None:
        setting = self.repository.get_by_key(key)
        if setting is None:
            return None
        return json.loads(setting.value_json)

    def set(
        self,
        key: str,
        value: Any,
        editable: bool = True,
        description: str | None = None,
    ) -> None:
        self.repository.upsert(
            key=key,
            value_json=json.dumps(value, ensure_ascii=True),
            editable=editable,
            description=description,
        )

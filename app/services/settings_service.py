import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.db.unit_of_work import UnitOfWork
from app.repositories.settings_repository import SettingsRepository


EDITABLE_SETTINGS: dict[str, dict[str, Any]] = {
    "default_frame_interval_sec": {
        "type": "float",
        "min": 0.1,
        "max": 60.0,
        "description": "学習・検出で使う既定のフレーム間隔秒。",
    },
    "default_training_batch_size": {
        "type": "int",
        "min": 1,
        "max": 512,
        "description": "学習特徴量抽出の既定batch size。",
    },
    "default_detection_batch_size": {
        "type": "int",
        "min": 1,
        "max": 512,
        "description": "検出推論の既定batch size。",
    },
    "default_smoothing_window_sec": {
        "type": "float",
        "min": 0.0,
        "max": 60.0,
        "description": "シーン区間生成の平滑化window秒。",
    },
    "default_merge_gap_sec": {
        "type": "float",
        "min": 0.0,
        "max": 60.0,
        "description": "近接シーンを結合する最大gap秒。",
    },
    "default_padding_sec": {
        "type": "float",
        "min": 0.0,
        "max": 60.0,
        "description": "シーン区間の前後padding秒。",
    },
    "default_min_segment_duration_sec": {
        "type": "float",
        "min": 0.0,
        "max": 600.0,
        "description": "採用する最小シーン長秒。",
    },
    "default_max_segment_duration_sec": {
        "type": "float",
        "min": 1.0,
        "max": 3600.0,
        "description": "分割する最大シーン長秒。",
    },
    "feedback_max_frames_per_segment": {
        "type": "int",
        "min": 1,
        "max": 64,
        "description": "feedback再学習で1区間から抽出する最大フレーム数。",
    },
    "feedback_min_frame_interval_sec": {
        "type": "float",
        "min": 0.01,
        "max": 60.0,
        "description": "feedback再学習の最小サンプリング間隔秒。",
    },
}


class SettingsService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings
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
        with UnitOfWork(self.db):
            self.repository.upsert(
                key=key,
                value_json=json.dumps(value, ensure_ascii=True),
                editable=editable,
                description=description,
            )

    def get_effective(self, key: str, default: Any) -> Any:
        value = self.get(key)
        return default if value is None else value

    def list_editable(self) -> list[dict[str, Any]]:
        if self.settings is None:
            raise RuntimeError("Settings object is required.")
        output = []
        for key, metadata in EDITABLE_SETTINGS.items():
            stored = self.get(key)
            default = getattr(self.settings, key)
            output.append(
                {
                    "key": key,
                    "value": default if stored is None else stored,
                    "default_value": default,
                    "type": metadata["type"],
                    "editable": True,
                    "description": metadata["description"],
                    "min": metadata["min"],
                    "max": metadata["max"],
                    "source": "default" if stored is None else "database",
                }
            )
        return output

    def set_editable(self, values: dict[str, Any]) -> list[dict[str, Any]]:
        if self.settings is None:
            raise RuntimeError("Settings object is required.")
        for key, value in values.items():
            metadata = EDITABLE_SETTINGS.get(key)
            if metadata is None:
                raise ValidationAppError(
                    message="Setting is not editable.",
                    detail={"key": key},
                    suggested_action="Use one of the editable settings keys.",
                )
            normalized = self._normalize_value(key, value, metadata)
            self.set(
                key=key,
                value=normalized,
                editable=True,
                description=metadata["description"],
            )
        return self.list_editable()

    def _normalize_value(
        self,
        key: str,
        value: Any,
        metadata: dict[str, Any],
    ) -> int | float:
        try:
            if metadata["type"] == "int":
                normalized: int | float = int(value)
            else:
                normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise ValidationAppError(
                message="Setting value has invalid type.",
                detail={"key": key, "value": value, "type": metadata["type"]},
            ) from exc
        if normalized < metadata["min"] or normalized > metadata["max"]:
            raise ValidationAppError(
                message="Setting value is out of allowed range.",
                detail={
                    "key": key,
                    "value": normalized,
                    "min": metadata["min"],
                    "max": metadata["max"],
                },
            )
        return normalized

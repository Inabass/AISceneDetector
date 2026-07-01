from pydantic import BaseModel

from app.schemas.common import ApiResponse


class SettingData(BaseModel):
    key: str
    value: int | float
    default_value: int | float
    type: str
    editable: bool
    description: str
    min: int | float
    max: int | float
    source: str


class SettingsUpdateRequest(BaseModel):
    values: dict[str, int | float]


class SettingsListResponse(ApiResponse[list[SettingData]]):
    pass

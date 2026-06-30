from pydantic import BaseModel

from app.schemas.common import ApiResponse


class HealthData(BaseModel):
    status: str
    app_name: str
    version: str
    database: str
    storage_root: str


class HealthResponse(ApiResponse[HealthData]):
    pass

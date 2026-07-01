from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.schemas.job import JobData


class ModelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ModelTrainRequest(BaseModel):
    parent_version_id: int | None = None
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    feature_ids: list[int] | None = None
    include_feedback: bool = False
    feedback_ids: list[int] | None = None


class ModelRollbackRequest(BaseModel):
    version_id: int


class ModelVersionData(BaseModel):
    id: int
    model_id: int
    version: str
    parent_version_id: int | None
    status: str
    artifact_path: str
    feature_set_path: str
    thresholds: dict[str, object]
    metrics: dict[str, object]
    extractor: dict[str, object]
    matcher: dict[str, object]
    cluster: dict[str, object]
    classifier: dict[str, object]
    created_by_job_id: int | None


class ModelData(BaseModel):
    id: int
    name: str
    description: str | None
    active_version_id: int | None
    active_version: ModelVersionData | None = None
    versions: list[ModelVersionData] = []


class ModelResponse(ApiResponse[ModelData]):
    pass


class ModelListResponse(ApiResponse[list[ModelData]]):
    pass


class ModelJobResponse(ApiResponse[JobData]):
    pass

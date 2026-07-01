from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse


class FeedbackCreateRequest(BaseModel):
    detection_id: int
    segment_id: int | None = None
    label: str = Field(pattern="^(positive|negative|ignore)$")
    memo: str | None = None
    source: str = "manual"


class FeedbackData(BaseModel):
    id: int
    detection_result_id: int
    segment_id: int | None
    model_version_id: int
    label: str
    source: str
    memo: str | None
    start_sec: float | None
    end_sec: float | None
    score: float | None
    metadata: dict[str, object]


class FeedbackResponse(ApiResponse[FeedbackData]):
    pass


class FeedbackListResponse(ApiResponse[list[FeedbackData]]):
    pass

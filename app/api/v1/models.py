import json

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.job import Job
from app.models.model import AiModel, ModelVersion
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobData
from app.schemas.model import (
    ModelCreateRequest,
    ModelData,
    ModelJobResponse,
    ModelListResponse,
    ModelResponse,
    ModelRollbackRequest,
    ModelTrainRequest,
    ModelVersionData,
)
from app.services.model_service import ModelService, run_model_training_job

router = APIRouter(prefix="/models", tags=["models"])


@router.post("", response_model=ModelResponse, status_code=201)
def create_model(
    payload: ModelCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ModelResponse:
    service = ModelService(db, settings)
    model = service.create_model(payload.name, payload.description)
    return ModelResponse(
        data=to_model_data(model, [], None),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("", response_model=ModelListResponse)
def list_models(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ModelListResponse:
    service = ModelService(db, settings)
    models = service.list_models()
    return ModelListResponse(
        data=[
            to_model_data(
                model,
                service.list_versions(model.id),
                service.get_active_version(model),
            )
            for model in models
        ],
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(
    model_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ModelResponse:
    service = ModelService(db, settings)
    model = service.get_model(model_id)
    return ModelResponse(
        data=to_model_data(
            model,
            service.list_versions(model.id),
            service.get_active_version(model),
        ),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{model_id}/train", response_model=ModelJobResponse, status_code=202)
def train_model(
    model_id: int,
    payload: ModelTrainRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ModelJobResponse:
    service = ModelService(db, settings)
    job_id = service.create_training_job(
        model_id=model_id,
        parent_version_id=payload.parent_version_id,
        threshold=payload.threshold,
        feature_ids=payload.feature_ids,
        include_feedback=payload.include_feedback,
        feedback_ids=payload.feedback_ids,
    )
    job = JobRepository(db).get(job_id)
    if job and job.status == "queued":
        background_tasks.add_task(run_model_training_job, job_id)
    return ModelJobResponse(
        data=to_job_data(job),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{model_id}/rollback", response_model=ModelResponse)
def rollback_model(
    model_id: int,
    payload: ModelRollbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ModelResponse:
    service = ModelService(db, settings)
    model = service.rollback(model_id, payload.version_id)
    return ModelResponse(
        data=to_model_data(
            model,
            service.list_versions(model.id),
            service.get_active_version(model),
        ),
        request_id=getattr(request.state, "request_id", None),
    )


def to_model_data(
    model: AiModel,
    versions: list[ModelVersion],
    active_version: ModelVersion | None,
) -> ModelData:
    return ModelData(
        id=model.id,
        name=model.name,
        description=model.description,
        active_version_id=model.active_version_id,
        active_version=to_model_version_data(active_version) if active_version else None,
        versions=[to_model_version_data(version) for version in versions],
    )


def to_model_version_data(version: ModelVersion) -> ModelVersionData:
    return ModelVersionData(
        id=version.id,
        model_id=version.model_id,
        version=version.version,
        parent_version_id=version.parent_version_id,
        status=version.status,
        artifact_path=version.artifact_path,
        feature_set_path=version.feature_set_path,
        thresholds=json.loads(version.thresholds_json),
        metrics=json.loads(version.metrics_json),
        extractor=json.loads(version.extractor_json),
        matcher=json.loads(version.matcher_json),
        cluster=json.loads(version.cluster_json),
        classifier=json.loads(version.classifier_json),
        created_by_job_id=version.created_by_job_id,
    )


def to_job_data(job: Job | None) -> JobData:
    if job is None:
        raise RuntimeError("Job was not created")
    return JobData(
        id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_code=job.error_code,
        error_message=job.error_message,
    )

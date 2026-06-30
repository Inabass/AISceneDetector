from fastapi import APIRouter

from app.api.v1.features import router as features_router
from app.api.v1.gpu import router as gpu_router
from app.api.v1.health import router as health_router
from app.api.v1.system import router as system_router
from app.api.v1.training import router as training_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(features_router)
api_router.include_router(gpu_router)
api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(training_router)

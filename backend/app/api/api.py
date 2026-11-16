from fastapi import APIRouter

from app.api.endpoints import analytics, auth, history, predict

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(predict.router, prefix="/predict", tags=["predict"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

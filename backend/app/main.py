import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.api.api import api_router
from app.core.config import settings
from app.db.database import init_db
from app.models.analytics import AnalyticsCache  # noqa: F401  (register tables)
from app.models.scan import Scan  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services import prediction_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("freshlytics")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Connecting to database…")
    await init_db()
    logger.info("Loading freshness model…")
    await run_in_threadpool(prediction_service.warm_up)
    logger.info("Freshlytics API ready.")
    yield


app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app|https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"message": "Welcome to the Freshlytics API. Visit /docs for documentation."}


@app.get("/health")
def health():
    return {"status": "ok"}

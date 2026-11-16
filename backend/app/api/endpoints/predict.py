import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.models.scan import Scan
from app.models.user import User
from app.schemas.scan import PredictionResponse
from app.services import prediction_service
from ml.inference import NotFruitError

router = APIRouter()

Image.MAX_IMAGE_PIXELS = 60_000_000


def _opt_float(v: Optional[str], lo: float, hi: float, label: str) -> Optional[float]:
    if v is None or str(v).strip() == "":
        return None
    try:
        f = float(v)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{label} must be a number.")
    if not lo <= f <= hi:
        raise HTTPException(status_code=422, detail=f"{label} must be between {lo:g} and {hi:g}.")
    return f


@router.get("/info")
async def model_info():
    return {
        "model": "ResNet50V2 fresh/rotten classifier",
        "auto_detected_fruits": prediction_service.auto_detected_fruits(),
        "supported_fruits": prediction_service.auto_detected_fruits(),
        "stages": prediction_service.stage_info(),
        "guide": prediction_service.fruit_guide(),
    }


@router.post("", response_model=PredictionResponse)
@router.post("/", response_model=PredictionResponse, include_in_schema=False)
async def predict_fruit(
    file: UploadFile = File(...),
    temperature: Optional[str] = Form(None),
    humidity: Optional[str] = Form(None),
    storage_type: str = Form("room"),
    fruit_hint: Optional[str] = Form(None),
    force: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(contents) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image too large. Max size is {settings.MAX_UPLOAD_MB} MB.")

    temp = _opt_float(temperature, -10, 50, "Temperature")
    hum = _opt_float(humidity, 0, 100, "Humidity")
    storage = storage_type if storage_type in ("room", "fridge") else "room"
    hint = (fruit_hint or "").lower().strip() or None
    if hint and hint != "auto" and hint not in prediction_service.auto_detected_fruits():
        raise HTTPException(status_code=422, detail=f"Unsupported fruit '{fruit_hint}'.")

    try:
        result = await run_in_threadpool(
            prediction_service.predict, io.BytesIO(contents),
            temperature=temp, humidity=hum, storage_type=storage, fruit_hint=hint,
            skip_fruit_check=force,
        )
    except NotFruitError as e:
        raise HTTPException(status_code=422, detail={"code": "no_fruit", "message": str(e)})
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="That file isn't a readable image. Try a JPG, PNG or WebP.")
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")

    scan = Scan(
        user_id=current_user.id,
        fruit_type=result["fruit"],
        freshness_stage=result["freshness_stage"],
        freshness_score=result["freshness_score"],
        shelf_life_hours=result["shelf_life_hours"],
        temperature=temp,
        humidity=hum,
        confidence=result["ai_confidence"],
        rot_probability=result["rot_probability"],
        storage_type=storage,
        fruit_source=result["fruit_source"],
        thumbnail=result["thumbnail"],
        heatmap=result["heatmap"],
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    return PredictionResponse(
        scan_id=scan.id,
        created_at=scan.created_at,
        storage_recommendation=" ".join(result["recommendations"]),
        **result,
    )

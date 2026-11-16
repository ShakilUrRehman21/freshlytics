import io
import os
import sys
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freshness_net import CLASSES
from inference import FRUIT_PROFILES, STAGES, NotFruitError, get_predictor

app = FastAPI(title="Freshlytics ML Service")


@app.on_event("startup")
async def startup():
    await run_in_threadpool(get_predictor)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info():
    predictor = get_predictor()
    return {
        "fruits": list(predictor.fruits),
        "profiles": FRUIT_PROFILES,
        "stages": [{"min_score": s, "label": label, "description": d} for s, label, d in STAGES],
    }


@app.post("/predict")
async def predict(
    image: UploadFile = File(...),
    fruit: Optional[str] = Form(None),
    storage: Optional[str] = Form("room"),
    temperature: Optional[float] = Form(None),
    humidity: Optional[float] = Form(None),
    skip_fruit_check: bool = Form(False),
):
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image uploaded.")

    predictor = get_predictor()
    try:
        result = await run_in_threadpool(
            predictor.predict,
            io.BytesIO(contents),
            fruit=fruit or None,
            storage=storage or "room",
            temperature=temperature,
            humidity=humidity,
            skip_fruit_check=skip_fruit_check,
        )
        return result
    except NotFruitError as e:
        raise HTTPException(status_code=422, detail={"code": "no_fruit", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")

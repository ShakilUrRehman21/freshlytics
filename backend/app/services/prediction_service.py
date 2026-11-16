"""Thin wrapper that makes the ML package importable from the backend and
loads the model once per process."""
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from ml.inference import FRUIT_PROFILES, STAGES, get_predictor  # noqa: E402

SUPPORTED_FRUITS = [f for f in FRUIT_PROFILES if f != "other"]


def warm_up() -> None:
    get_predictor()


def predict(image_file, **kwargs) -> dict:
    return get_predictor().predict(image_file, **kwargs)


def auto_detected_fruits() -> list[str]:
    """Fruits the active checkpoint can recognise on its own."""
    return list(get_predictor().fruits)


def fruit_guide() -> list[dict]:
    return [
        {
            "fruit": name,
            "room_days": p["room"],
            "fridge_days": p["fridge"],
            "ideal_temp": p["ideal_temp"],
            "ideal_humidity": p["ideal_humidity"],
            "tip": p["tip"],
            "auto_detected": name in auto_detected_fruits(),
        }
        for name, p in FRUIT_PROFILES.items()
        if name != "other"
    ]


def stage_info() -> list[dict]:
    return [{"min_score": s, "label": label, "description": d} for s, label, d in STAGES]

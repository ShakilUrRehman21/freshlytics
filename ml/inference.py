"""
Freshlytics inference engine.

Pipeline
--------
1. FreshnessNet (ResNet50V2, converted from the Keras/TF.js model) scores the image
   over 6 classes: {fresh, rotten} x {apple, banana, orange}.
   - rot probability   = sum of the three "rotten" class probabilities
   - fruit type        = argmax over the fruit marginals (apple / banana / orange)
   The rot signal generalises to other fruits (mango, grapes...) because it keys on
   mould, bruising and discolouration, so users can override the fruit type.
2. A Grad-CAM heatmap over the last conv block shows *where* the model sees decay.
3. Shelf life is estimated from a per-fruit storage profile, scaled by the measured
   freshness and by storage temperature (Q10 ≈ 2 rule: every +10 °C roughly halves
   the remaining life) and humidity.
"""
from __future__ import annotations

import base64
import io
import math
import os
import threading
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps

try:
    from ml.freshness_net import CLASSES, INPUT_SIZE, FreshnessNet
except ImportError:  # executed from inside ml/
    from freshness_net import CLASSES, INPUT_SIZE, FreshnessNet

ML_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CHECKPOINT = os.path.join(ML_DIR, "checkpoints", "freshness_resnet50v2.pth")
TFJS_SOURCE = os.path.join(ML_DIR, "extracted", "final_bangkit-master", "public", "model", "model3", "transfer_learning")

DETECTABLE_FRUITS = ["apple", "banana", "orange"]

# Typical shelf life (days) for a *fresh* fruit. Sources: USDA FoodKeeper / common
# extension-service guidance; values are deliberately conservative.
FRUIT_PROFILES = {
    "apple":  {"room": 7,  "fridge": 35, "ideal_temp": "0–4 °C",  "ideal_humidity": "90–95%",
               "tip": "Keep apples away from other produce — they release ethylene and speed up ripening around them."},
    "banana": {"room": 5,  "fridge": 7,  "ideal_temp": "13–15 °C", "ideal_humidity": "85–95%",
               "tip": "Ripen at room temperature, then refrigerate: the peel darkens but the flesh stays good for days."},
    "orange": {"room": 10, "fridge": 28, "ideal_temp": "3–8 °C",  "ideal_humidity": "90–95%",
               "tip": "Store loose (not in sealed plastic) so moisture can't build up and trigger mould."},
    "mango":  {"room": 4,  "fridge": 6,  "ideal_temp": "10–13 °C", "ideal_humidity": "85–90%",
               "tip": "Ripen unripe mangoes on the counter; only chill once they give slightly to gentle pressure."},
    "grapes": {"room": 2,  "fridge": 10, "ideal_temp": "0–2 °C",  "ideal_humidity": "90–95%",
               "tip": "Don't wash grapes until you eat them — surface moisture is the fastest route to mould."},
    "guava": {"room": 3,  "fridge": 10, "ideal_temp": "8–10 °C", "ideal_humidity": "85–90%",
               "tip": "Ripen on the counter, then refrigerate; cut guava should be eaten within a day."},
    "pomegranate": {"room": 10, "fridge": 45, "ideal_temp": "5–7 °C", "ideal_humidity": "90–95%",
               "tip": "Whole fruit keeps for weeks in the fridge; refrigerate loose arils in a sealed box and use within 5 days."},
    "strawberry": {"room": 1, "fridge": 5, "ideal_temp": "0–2 °C", "ideal_humidity": "90–95%",
               "tip": "Keep unwashed on a paper towel in a single layer, and remove any mouldy berry straight away."},
    "lime":   {"room": 7,  "fridge": 28, "ideal_temp": "9–10 °C", "ideal_humidity": "85–90%",
               "tip": "Store in a bag in the fridge so the peel doesn't dry out and harden."},
    "jujube": {"room": 4,  "fridge": 14, "ideal_temp": "2–5 °C", "ideal_humidity": "85–90%",
               "tip": "Ber wrinkles as it dries — still edible, but refrigerate in a bag to keep it crisp."},
    "other":  {"room": 4,  "fridge": 10, "ideal_temp": "4–8 °C",  "ideal_humidity": "85–95%",
               "tip": "Check daily and separate any piece showing soft spots so decay doesn't spread."},
}
REFERENCE_TEMP = {"room": 21.0, "fridge": 4.0}

STAGES = [  # (min score, label, description)
    (80, "Fresh", "Looks fresh with no visible signs of decay."),
    (55, "Good", "Mostly fine — minor signs of ageing."),
    (30, "Use Soon", "Visible ageing. Eat, cook or freeze within a day or two."),
    (0, "Spoiled", "Clear signs of rot or mould. Discard affected pieces."),
]

# Logit temperature: the original network is very over-confident (softmax saturates
# at 0/1); softening gives a more useful graded freshness score.
LOGIT_TEMPERATURE = 2.5
FRUIT_THRESHOLD = 0.08  # min ImageNet produce probability to accept a photo


def _stage_for(score: int):
    for min_score, label, desc in STAGES:
        if score >= min_score:
            return label, desc
    return STAGES[-1][1], STAGES[-1][2]


def estimate_shelf_life_hours(fruit: str, freshness: float, storage: str,
                              temperature: Optional[float], humidity: Optional[float]) -> float:
    """freshness in [0, 1]. Returns remaining hours (>= 0)."""
    profile = FRUIT_PROFILES.get(fruit, FRUIT_PROFILES["other"])
    storage = storage if storage in ("room", "fridge") else "room"
    base_hours = profile[storage] * 24.0

    # Remaining life falls faster than linearly with visible decay.
    remaining_fraction = max(0.0, freshness) ** 1.6

    t = temperature if temperature is not None else REFERENCE_TEMP[storage]
    t = float(min(max(t, -5.0), 45.0))
    temp_factor = 2.0 ** ((REFERENCE_TEMP[storage] - t) / 10.0)
    temp_factor = min(max(temp_factor, 0.25), 3.0)

    hum_factor = 1.0
    if humidity is not None:
        if humidity < 40:
            hum_factor = 0.85   # dehydration / shrivelling
        elif humidity > 95:
            hum_factor = 0.8    # condensation → mould

    return round(base_hours * remaining_fraction * temp_factor * hum_factor, 1)


def storage_recommendation(fruit: str, stage: str, storage: str, temperature: Optional[float],
                           shelf_life_hours: float) -> list[str]:
    profile = FRUIT_PROFILES.get(fruit, FRUIT_PROFILES["other"])
    recs: list[str] = []
    if stage == "Spoiled":
        recs.append("Discard visibly mouldy pieces and check neighbouring fruit — spores spread quickly.")
    elif stage == "Use Soon" or shelf_life_hours < 24:
        recs.append("Use within 24 hours: eat now, blend into a smoothie, bake, or freeze slices.")
    if storage == "room" and profile["fridge"] > profile["room"] * 1.5 and stage in ("Fresh", "Good"):
        gain = profile["fridge"] / profile["room"]
        recs.append(f"Refrigerating could extend shelf life roughly {gain:.0f}× (ideal {profile['ideal_temp']}).")
    if temperature is not None and storage == "room" and temperature >= 28:
        recs.append(f"It's warm ({temperature:.0f} °C) — heat roughly halves shelf life for every 10 °C. Move to a cooler spot.")
    if stage != "Spoiled":
        recs.append(profile["tip"])
    else:
        recs.append("Wash hands and wipe the storage spot; next time, " + profile["tip"][0].lower() + profile["tip"][1:])
    return recs


class NotFruitError(ValueError):
    pass


# ImageNet classes 936-957 are fruit & vegetables (banana, orange, Granny Smith, lemon, fig...)
_PRODUCE = list(range(936, 958))
# ImageNet produce classes that correspond to items we support; anything else -> "other"
_SUPPORTED_IMAGENET = {948, 949, 950, 951, 954, 957}  # Granny Smith, strawberry, orange, lemon, banana, pomegranate


class FruitGate:
    """General ImageNet classifier used only to reject photos with no fruit in them.
    Weights download once (~22 MB). If unavailable, the gate is skipped."""

    def __init__(self):
        self.model = None
        try:
            from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large
            w = MobileNet_V3_Large_Weights.IMAGENET1K_V2
            self.model = mobilenet_v3_large(weights=w).eval()
            self.tf = w.transforms()
        except Exception as e:  # offline etc.
            print(f"[freshlytics] fruit check disabled: {e}")

    @torch.no_grad()
    def check(self, img: Image.Image):
        """Returns (produce probability, top produce class index, its share of produce prob)."""
        if self.model is None:
            return None, None, 0.0
        p = F.softmax(self.model(self.tf(img).unsqueeze(0)), dim=1)[0]
        prod = p[_PRODUCE]
        total = float(prod.sum())
        i = int(prod.argmax())
        self.last_shares = {c: float(p[c]) / max(total, 1e-6) for c in _PRODUCE}
        return total, _PRODUCE[i], float(prod[i]) / max(total, 1e-6)


class FreshlyticsPredictor:
    def __init__(self, model_path: str = DEFAULT_CHECKPOINT, device: Optional[str] = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        if not os.path.exists(model_path):
            if os.path.isdir(TFJS_SOURCE):
                print("[freshlytics] PyTorch checkpoint missing — converting TF.js model (one-off)...")
                try:
                    from ml.convert_tfjs import build, load_tfjs
                except ImportError:
                    from convert_tfjs import build, load_tfjs
                topology, state = build(*load_tfjs(TFJS_SOURCE))
                os.makedirs(os.path.dirname(model_path), exist_ok=True)
                tmp = FreshnessNet(topology)
                tmp.load_state_dict(state)
                torch.save({"topology": topology, "state_dict": tmp.state_dict(),
                            "input_size": INPUT_SIZE, "preprocess": "rgb/255"}, model_path)
            else:
                raise FileNotFoundError(
                    f"Model checkpoint not found at {model_path} and no TF.js source at {TFJS_SOURCE}. "
                    "Run `python ml/convert_tfjs.py`."
                )
        self.model = FreshnessNet.from_checkpoint(model_path, map_location=self.device).to(self.device)
        for p in self.model.parameters():
            p.requires_grad_(False)
        self.fruits = list(getattr(self.model, "fruits", DETECTABLE_FRUITS))
        self._cam_layer = "conv4_block3_out"
        self._lock = threading.Lock()
        self.gate = FruitGate()

    # ---------- image helpers ----------
    @staticmethod
    def _load(image) -> Image.Image:
        img = image if isinstance(image, Image.Image) else Image.open(image)
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")

    @staticmethod
    def _square(img: Image.Image) -> Image.Image:
        w, h = img.size
        s = min(w, h)
        return img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))

    def _to_tensor(self, img: Image.Image) -> torch.Tensor:
        arr = np.asarray(img.resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
        return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(self.device)

    @staticmethod
    def _b64_jpeg(img: Image.Image, size: int, quality: int = 82) -> str:
        im = img.copy()
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    def _forward_with_cam(self, x: torch.Tensor):
        """Forward pass that also returns a Grad-CAM map for the 'rotten' direction."""
        acts = {}
        model = self.model
        cache = {}
        out = x
        with torch.enable_grad():
            x = x.clone().requires_grad_(True)
            for node in model.topology:
                t, cfg, name = node["type"], node["cfg"], node["name"]
                ins = [cache[i] for i in node["inputs"]] if node["inputs"] else [x]
                h = ins[0]
                if t == "InputLayer":
                    out = x
                elif t == "ZeroPadding2D":
                    (pt, pb), (pl, pr) = cfg["padding"]
                    out = F.pad(h, (pl, pr, pt, pb))
                elif t in ("Conv2D", "BatchNormalization"):
                    out = model.layers[name](h)
                elif t == "Activation":
                    out = F.relu(h)
                elif t == "MaxPooling2D":
                    out = F.max_pool2d(h, tuple(cfg["pool"]), tuple(cfg["stride"]))
                elif t == "AveragePooling2D":
                    out = F.avg_pool2d(h, tuple(cfg["pool"]), tuple(cfg["stride"]))
                elif t == "Add":
                    out = sum(ins[1:], ins[0])
                elif t == "Flatten":
                    out = h.permute(0, 2, 3, 1).reshape(h.shape[0], -1)
                elif t == "Dense":
                    out = model.layers[name](h)
                    if cfg["activation"] == "relu":
                        out = F.relu(out)
                elif t == "Dropout":
                    out = h
                cache[name] = out
                if name == self._cam_layer:
                    out.retain_grad()
                    acts["a"] = out
            logits = out
            probs = F.softmax(logits / LOGIT_TEMPERATURE, dim=1)
            rot = probs[0, len(self.fruits):].sum()
            # Explain the rot evidence (log-odds of rotten vs fresh)
            target = torch.log(rot + 1e-6) - torch.log(1 - rot + 1e-6)
            target.backward()
        a = acts["a"]
        weights = a.grad.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((weights * a).sum(dim=1))[0].detach()
        return logits.detach(), cam

    def _heatmap_overlay(self, img: Image.Image, cam: torch.Tensor, strength: float) -> str:
        cam = cam.cpu().numpy()
        if cam.max() > 0:
            cam = cam / cam.max()
        size = 320
        base = img.resize((size, size), Image.BILINEAR)
        cam_img = Image.fromarray(np.uint8(cam * 255)).resize((size, size), Image.BICUBIC)
        c = np.asarray(cam_img, dtype=np.float32) / 255.0
        # warm colour ramp: transparent → amber → deep red
        rgb = np.stack([np.clip(0.95 + 0 * c, 0, 1), np.clip(0.75 - 0.6 * c, 0, 1), np.clip(0.2 - 0.2 * c, 0, 1)], -1)
        alpha = (np.clip((c - 0.25) / 0.75, 0, 1) ** 1.2) * 0.75 * strength
        b = np.asarray(base, dtype=np.float32) / 255.0
        out = b * (1 - alpha[..., None]) + rgb * alpha[..., None]
        return self._b64_jpeg(Image.fromarray(np.uint8(out * 255)), size, quality=85)

    # ---------- public API ----------
    def predict(self, image, temperature: Optional[float] = None, humidity: Optional[float] = None,
                storage_type: str = "room", fruit_hint: Optional[str] = None,
                skip_fruit_check: bool = False) -> dict:
        img = self._square(self._load(image))
        if not skip_fruit_check:
            fp, top_cls, top_share = self.gate.check(img)
            if fp is not None and fp < FRUIT_THRESHOLD:
                raise NotFruitError("No fruit found in this photo. Fill the frame with one fruit and try again.")
        else:
            fp, top_cls, top_share = None, None, 0.0
        # Clearly a different kind of produce (e.g. strawberry, lemon, broccoli) -> "other"
        is_other = (fp is not None and fp >= 0.3 and top_cls not in _SUPPORTED_IMAGENET and top_share >= 0.6)
        x = self._to_tensor(img)
        with self._lock:
            logits, cam = self._forward_with_cam(x)

        probs_raw = F.softmax(logits, dim=1)[0]
        probs = F.softmax(logits / LOGIT_TEMPERATURE, dim=1)[0]

        n = len(self.fruits)
        rot_probability = float(probs[n:].sum())
        fruit_marginal = (probs_raw[:n] + probs_raw[n:]).tolist()
        detected_idx = int(np.argmax(fruit_marginal))
        detected_fruit = self.fruits[detected_idx]
        fruit_confidence = float(fruit_marginal[detected_idx])

        hint = (fruit_hint or "").strip().lower() or None
        if hint == "auto":
            hint = None
        # Cross-check: banana / orange are ImageNet classes too, so for a fresh-looking item the
        # general model must agree (stops okra -> "banana", carrot -> "orange" and similar).
        shares = getattr(self.gate, "last_shares", None) if fp is not None else None
        check_idx = {"banana": 954, "orange": 950}.get(detected_fruit)
        if (hint is None and shares and check_idx and rot_probability < 0.5
                and shares.get(check_idx, 0) < 0.15):
            is_other = True
        if hint is None and is_other:
            detected_fruit, fruit_confidence = "other", top_share
        fruit = hint if hint in FRUIT_PROFILES else detected_fruit
        fruit_source = "user" if hint in FRUIT_PROFILES else "model"

        freshness = 1.0 - rot_probability
        score = int(round(100 * freshness))
        stage, stage_desc = _stage_for(score)
        storage = storage_type if storage_type in ("room", "fridge") else "room"
        shelf = estimate_shelf_life_hours(fruit, freshness, storage, temperature, humidity)
        if stage == "Spoiled":
            shelf = min(shelf, 6.0)

        # How sure the model is of the fresh/rotten call (distance from the 50/50 line)
        decision_conf = abs(float(probs_raw[n:].sum()) - 0.5) * 2
        ai_confidence = round(0.5 + 0.5 * decision_conf, 3)
        low_confidence_fruit = fruit_source == "model" and (fruit_confidence < 0.7 or fruit == "other")

        heatmap = self._heatmap_overlay(img, cam, strength=min(1.0, rot_probability * 1.6 + 0.15))

        return {
            "fruit": fruit,
            "fruit_source": fruit_source,
            "detected_fruit": detected_fruit,
            "fruit_confidence": round(fruit_confidence, 3),
            "fruit_uncertain": low_confidence_fruit,
            "freshness_stage": stage,
            "stage_description": stage_desc,
            "freshness_score": score,
            "rot_probability": round(rot_probability, 3),
            "shelf_life_hours": shelf,
            "ai_confidence": ai_confidence,
            "storage_type": storage,
            "temperature": temperature,
            "humidity": humidity,
            "recommendations": storage_recommendation(fruit, stage, storage, temperature, shelf),
            "ideal_conditions": {
                "temperature": FRUIT_PROFILES.get(fruit, FRUIT_PROFILES["other"])["ideal_temp"],
                "humidity": FRUIT_PROFILES.get(fruit, FRUIT_PROFILES["other"])["ideal_humidity"],
            },
            "thumbnail": self._b64_jpeg(img, 192, quality=78),
            "heatmap": heatmap,
        }


_predictor: Optional[FreshlyticsPredictor] = None
_predictor_lock = threading.Lock()


def get_predictor() -> FreshlyticsPredictor:
    global _predictor
    if _predictor is None:
        with _predictor_lock:
            if _predictor is None:
                _predictor = FreshlyticsPredictor()
    return _predictor


if __name__ == "__main__":
    import json
    import sys

    p = get_predictor()
    for path in sys.argv[1:]:
        r = p.predict(path)
        r.pop("thumbnail"), r.pop("heatmap")
        print(path, json.dumps(r, indent=2))

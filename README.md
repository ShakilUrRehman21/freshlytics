# Freshlytics

> **Supported fruits:** only those the active model is trained on (shown in the app). Default model:
> apple, banana, orange. Retrained on `ml/data_v2` (see RUNNING.md): apple, banana, orange, mango,
> guava, lime, pomegranate. Other fruits/vegetables are not supported.

Predicting freshness. Preventing waste.

Photograph a piece of fruit and Freshlytics tells you how fresh it is (a 0–100 score and a stage:
**Fresh, Good, Use Soon, Spoiled**), how long it has left given where and how you store it, where
it sees decay (a "decay map"), and what to do about it. Every scan is saved to your history and
rolled up into an overview that puts the fruit you should eat first at the top.

## How it works

| Part | What it does |
| --- | --- |
| `ml/freshness_net.py` | Pure-PyTorch runtime for a **ResNet50V2** fresh/rotten classifier trained on ~10.9k photos (Kaggle *fruits fresh and rotten*, ~98% validation accuracy). |
| `ml/convert_tfjs.py` | Converts the original TensorFlow.js model in `ml/extracted/final_bangkit-master` into `ml/checkpoints/freshness_resnet50v2.pth`. The backend does this automatically on first start if the checkpoint is missing. |
| `ml/inference.py` | Scores decay, recognises apple / banana / orange, draws a Grad-CAM decay map, and estimates shelf life from per-fruit storage profiles adjusted for decay, temperature (≈ halves per +10 °C) and humidity. Mango, grapes and other fruit are supported by choosing the fruit when scanning — decay detection still works on them. |
| `ml/train.py` | Re-trains the classification head on your own photos (frozen backbone, CPU friendly) — the way to add automatic recognition for more fruits. |
| `backend/` | FastAPI + SQLAlchemy (async). Auth (JWT), prediction, history, analytics. Postgres (incl. Neon) or SQLite. |
| `frontend/` | React + Vite + Tailwind. Overview, Scan (upload, drag-and-drop, paste, camera), History, Storage guide, Settings, light/dark. |

## Running it

See **[RUNNING.md](RUNNING.md)** for the full guide. Short version on Windows:

```bat
setup.bat   :: once
start.bat   :: API on http://localhost:8000, website on http://localhost:3000
```

## Dataset and model

`ml/data_v2/` is a cleaned, de-duplicated dataset of fresh and rotten **apples, bananas, oranges
and mangoes** built by `ml/build_dataset.py` from two published datasets (pinned in
`ml/dataset_sources/`). Retrain with `ml/train.py` and measure with `ml/evaluate.py`.
RUNNING.md §7–8 explains the sources, the cleaning steps and how to add fruits.

The original `ml/data` (≈170 web images, many duplicated or mislabelled) taught the first model to
equate "white background" with "fresh"; its pipeline is kept in `ml/legacy/` for reference.

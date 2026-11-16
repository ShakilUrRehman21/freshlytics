# Running Freshlytics

> **Supported fruits = only the fruits the active model was trained on.** The app reads this list
> from the model and shows nothing else. Out of the box that's **apple, banana and orange**; after
> building the dataset and retraining (§7–8) it's **apple, banana, orange, mango, guava, lime and
> pomegranate**. Anything else is not supported and gives unreliable results.

This guide takes you from a fresh clone to a working app at **http://localhost:3000**, then covers
the dataset, retraining, Docker, and common problems. Commands are for **Windows** (PowerShell or
Command Prompt); macOS/Linux differences are noted where they matter.

---

## 1. What you need

| Tool | Version | Check with |
| --- | --- | --- |
| Python | 3.10 – 3.12 | `python --version` |
| Node.js | 18 or newer | `node --version` |
| A database | Neon / any Postgres, **or** nothing (SQLite) | — |
| Disk space | ~3 GB (PyTorch is the big one) | — |

No GPU needed. Everything runs on a normal laptop CPU.

---

## 2. Quick start (Windows)

From the project folder (`D:\Projects\freshlytics`):

```bat
setup.bat      :: one-time: creates the Python venv, installs PyTorch + backend + frontend packages
start.bat      :: every time: opens two windows — the API on :8000 and the website on :3000
```

Then open **http://localhost:3000**, click **Create an account**, and scan a fruit.
If you'd rather do it by hand, or you're on macOS/Linux, follow sections 3–5.

---

## 3. Configure the database (`.env`)

All settings live in **`.env` in the project root** (copy `.env.example` if it doesn't exist).
Pick **one** option:

**A. Neon or another cloud Postgres** (what this project uses now)
```env
POSTGRES_USER=neondb_owner
POSTGRES_PASSWORD=your-password
POSTGRES_DB=neondb
POSTGRES_SERVER=ep-xxxx-pooler.c-4.us-east-1.aws.neon.tech
```
or a single line: `DATABASE_URL=postgresql://user:pass@host/neondb?sslmode=require`.
SSL and pooler-safe settings are switched on automatically for non-local hosts.

**B. Local Postgres**: set `POSTGRES_SERVER=localhost` plus your user, password and database.

**C. No database server at all (simplest for trying it out)**
```env
DATABASE_URL=sqlite+aiosqlite:///./freshlytics.db
```
This creates `backend/freshlytics.db`.

Also set a random `SECRET_KEY` (it signs login tokens), for example
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Tables are created automatically on first start, and columns added in newer versions are added to
existing tables for you.

---

## 4. Backend (API on port 8000)

```bat
cd backend
python -m venv venv
venv\Scripts\activate                 :: macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m uvicorn app.main:app --reload
```

You should see `Freshlytics API ready.` Check http://localhost:8000/health returns `{"status":"ok"}`,
and browse the API at http://localhost:8000/docs.

The model loads from `ml/checkpoints/freshness_resnet50v2.pth`. If that file is missing, the
backend rebuilds it from `ml/extracted/...` on first start (takes a few seconds).

Next time you only need:
```bat
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

---

## 5. Frontend (website on port 3000)

In a **second** terminal:
```bat
cd frontend
npm install          :: first time, or after package.json changes
npm run dev
```
Your browser opens http://localhost:3000. The site talks to the API at
`http://localhost:8000/api/v1`; change `VITE_API_URL` in `.env` if your API runs elsewhere.

For a production build: `npm run build` creates `frontend/dist/`, which any static host can serve.

---

## 6. Using the app

1. **Create an account** (name, email, password of 6+ characters).
2. **Scan**: drop, paste (Ctrl+V), choose or photograph a fruit. One fruit per photo, filling most
   of the frame, in good light, gives the best results.
3. Say **where it's kept** (counter or fridge) and adjust temperature and humidity; these change the
   time-left estimate.
4. **Auto-detect** recognises the fruits the model was trained on (shown under "Which fruit?").
   For anything else, choose the fruit: decay detection still works, and the shelf-life estimate
   uses the right storage profile.
5. **Overview** shows what to eat first; **History** keeps every scan with notes; **Storage guide**
   explains the scores.

---

## 7. The dataset

`ml/data_v2/` is the cleaned training set, built by `ml/build_dataset.py` from two published,
labelled datasets pinned to exact commits in `ml/dataset_sources/`:

| Source | What we use |
| --- | --- |
| *Fruits fresh and rotten for classification* (Kaggle; GitHub mirror) | fresh and rotten apples, bananas and oranges |
| *Healthy-Defective-Fruits* (Pacheco et al., VISAPP 2023) | **real** photos of fresh and rotten/black-spot mangoes and apples (synthetic renders, bruises and scab skipped) |

Cleaning steps:
- **Broken and unusable images:** unreadable files, tiny images, odd shapes and blank frames are removed.
- **Duplicates:** exact and near-duplicate photos are removed, including rotated, mirrored and re-cropped copies. Each pair is confirmed pixel-by-pixel, so different fruits on the same backdrop are kept.
- **Train/test leakage:** a photo that appears in both the training and test sets is kept only in test.
- **Conflicting labels:** if the same photo is labelled both fresh and rotten, every copy is dropped.
- **Studio shots:** photos on a plain light backdrop are cropped to the fruit, so the background can't become a shortcut for the label.

Everything removed is kept in `ml/data_v2/_rejected/<reason>/` so you can check it. For example,
`duplicate/xxx__same_as_yyy.jpg` names the photo it duplicates. `report.json` has the counts, and
**`review.html`** shows a sample of every class. Open it in a browser and delete anything odd before
training.

### Adding more fruits (10 common Indian fruits)

GitHub only hosts data for apple, banana, orange and mango. For the other fruits, download these
two free datasets yourself (each needs a free account), unzip them **anywhere inside `ml\raw\`**,
then rebuild:

| Dataset | Adds | Where |
| --- | --- | --- |
| *Fruit and Vegetable Diseases Dataset (Healthy vs Rotten)* (muhammad0subhan, Kaggle) | grapes, guava, pomegranate, strawberry, jujube (ber), plus more apple/banana/orange/mango | kaggle.com/datasets/muhammad0subhan/fruit-and-vegetable-disease-healthy-vs-rotten |
| *FruitNet: Indian fruits dataset with quality* (Meshram & Patil, Mendeley Data, CC BY 4.0) | lime, plus more guava/pomegranate/apple/banana/orange | data.mendeley.com/datasets/b6fftwbr2v |

Example layout: `ml\raw\kaggle_disease\Guava__Rotten\...`, `ml\raw\fruitnet\Bad Quality_Fruits\Lime_Bad\...`.
The builder labels folders by name (`Healthy/Good/Fresh` = fresh, `Rotten/Bad/Stale` = rotten),
skips vegetables and the "Mixed" folders, and applies the same cleaning as above.

The app only offers fruits the trained model has seen. With FruitNet added that's apple, banana,
orange, mango, guava, lime and pomegranate.

Build / rebuild (GitHub sources download automatically; `ml\raw\` is read if present):
```bat
python ml\build_dataset.py download     :: resumable; re-run until it says "Download complete"
python ml\build_dataset.py finalize
```
Optional: `python ml\build_dataset.py audit` writes `ml/data_v2/audit.html` listing photos the current
model strongly disagrees with (likely mislabels). Add `--quarantine` to move them to `_rejected/`.

The old `ml/data` folder (≈170 images: duplicated web photos, mislabelled "rotten" apples, an apple
stuck with needles) is no longer used. Its scripts are in `ml/legacy/` for reference.

---

## 8. Retraining and evaluating the model

The backbone stays frozen and only the classifier head is trained, so this works on a CPU
(about 30–45 minutes for the full dataset, mostly spent reading images).

```bat
backend\venv\Scripts\activate
python ml\train.py --data ml\data_v2 --epochs 25
python ml\evaluate.py
```
`train.py` backs up the previous checkpoint to `freshness_resnet50v2.backup.pth`. Restart the backend
to load the new model.

**Adding a fruit** (e.g. grapes): add `ml/data_v2/train/freshgrapes/`, `rottengrapes/` and the
same two folders under `test/`. Use a few hundred varied photos each, with different backgrounds,
lighting and angles, and **both** fresh and rotten. Then retrain. The app picks up the new fruit
automatically.

---

## 9. Docker (alternative)

```bat
docker compose up --build
```
Starts Postgres, the API (:8000) and the website (:3000). This uses the bundled local Postgres, not
Neon. Set `DATABASE_URL` in `docker-compose.yml` to use Neon instead.

---

## 10. Troubleshooting

| Problem | Fix |
| --- | --- |
| Website says *Can't reach the Freshlytics server* | The backend isn't running or crashed. Check its terminal and http://localhost:8000/health. |
| `ModuleNotFoundError: No module named 'torch'` | Run the `pip install torch torchvision …` line inside the activated venv. |
| `ModuleNotFoundError: No module named 'app'` | Start uvicorn from inside the `backend` folder. |
| Database errors at startup (`password authentication failed`, `connection refused`, SSL errors) | Check the `.env` values. For a quick test, switch to the SQLite line in section 3. |
| `prepared statement … already exists` | You're using an old copy of `backend/app/db/database.py`; the current one disables the cache for poolers. |
| Login works but you're sent back to the sign-in page | `SECRET_KEY` changed since you signed in. Sign in again. |
| `npm run dev` fails with missing `@fontsource…` | Run `npm install` in `frontend` again. |
| Port 8000 or 3000 already in use | Stop the other process, or run `uvicorn … --port 8001` and set `VITE_API_URL=http://localhost:8001/api/v1`. |
| Camera button does nothing | Browsers only allow the camera on `localhost` or HTTPS, and you must allow access when prompted. |
| Predictions look wrong | Use one fruit per photo, filling the frame, in good light. Pick the fruit manually if it isn't auto-detected. |

"""
Build a clean, de-duplicated fresh/rotten fruit dataset for Freshlytics.

Sources (pinned to exact commits in ml/dataset_sources/*.json, downloaded from GitHub):
  * kaggle_fresh_rotten  — "Fruits fresh and rotten for classification" (Kalluri, Kaggle),
                           apples / bananas / oranges, ~13.6k photos, mirrored by
                           github.com/Bangkit-JKT2-D/fruits-fresh-rotten-classification
  * healthy_defective    — "Healthy-Defective-Fruits" (Pacheco et al., VISAPP 2023),
                           github.com/luischuquim/Healthy-Defective-Fruits — REAL photos only
                           (the synthetic renders are skipped). fresh -> fresh,
                           rot / black-spot defects -> rotten. Bruise and scab are skipped:
                           they're cosmetic, not spoilage.

Cleaning
  * unreadable / truncated files, images smaller than 96 px, extreme aspect ratios,
    near-blank frames -> rejected
  * exact and near duplicates, including rotated / mirrored copies (the Kaggle set contains
    many augmented copies) -> one copy kept; if a duplicate group spans train and test, the
    kept copy goes to test and the train copies are dropped (no train/test leakage)
  * per-class cap so one fruit can't dominate
  * everything rejected is moved to data_v2/_rejected/<reason>/ so you can inspect it

Output
  ml/data_v2/
    train/<fresh|rotten><fruit>/*.jpg     (e.g. freshmango/, rottenapple/)
    test/<fresh|rotten><fruit>/*.jpg
    manifest.csv                          one row per kept image, with its source
    report.json                           counts and reasons
    review.html                           contact sheet of every class to eyeball

Usage
  python ml/build_dataset.py download          # resumable; re-run until it says "complete"
  python ml/build_dataset.py finalize          # dedupe, filter, split, write folders
  python ml/build_dataset.py audit             # optional: flag likely-mislabelled photos
  python ml/build_dataset.py all               # download + finalize

Only needs Pillow + numpy (audit also needs torch).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import hashlib
import html
import io
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

import numpy as np
from PIL import Image, ImageOps

ML_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_DIR = os.path.join(ML_DIR, "dataset_sources")
OUT = os.path.join(ML_DIR, "data_v2")
POOL = os.path.join(OUT, "_pool")
POOL_CSV = os.path.join(OUT, "_pool.csv")
POOL_FIELDS = ["id", "source", "path", "fruit", "state", "split", "status", "w", "h", "dhash", "std"]

MAX_SIDE = 384          # stored resolution (model uses 150 px)
MIN_SIDE = 96
MAX_ASPECT = 2.5
MIN_STD = 10.0          # near-uniform / blank images
DUP_CORR = 0.97         # pixel correlation needed to call two photos duplicates
TEST_FRACTION = 0.2     # for sources without their own split
CAP_PER_CLASS = {"train": 2200, "test": 550}


# ---------------------------------------------------------------- labelling rules
def label_kaggle(path: str):
    # Datasets/train/freshapples/xxx.png
    parts = path.split("/")
    if len(parts) < 4:
        return None
    split, cls = parts[1], parts[2].lower()
    state = "fresh" if cls.startswith("fresh") else "rotten" if cls.startswith("rotten") else None
    fruit = {"apples": "apple", "banana": "banana", "oranges": "orange"}.get(cls.replace("fresh", "").replace("rotten", ""))
    if not state or not fruit or split not in ("train", "test"):
        return None
    return fruit, state, split


HD_CLASSES = {"fresh": "fresh", "rot_defect": "rotten", "rot_deffect": "rotten", "black_spot_defect": "rotten"}


def label_healthy_defective(path: str):
    # mango_images/mango_real_images/rot_defect/xxx.jpg
    parts = path.split("/")
    if len(parts) < 4 or "_real_images" not in parts[1]:
        return None
    fruit = parts[0].split("_")[0]
    state = HD_CLASSES.get(parts[2])
    if fruit not in ("apple", "mango") or not state:
        return None
    split = "test" if int(hashlib.md5(path.encode()).hexdigest(), 16) % 100 < TEST_FRACTION * 100 else "train"
    return fruit, state, split


# ---- local datasets you download yourself (see RUNNING.md §7) -> ml/raw/<anything>/...
RAW_DIR = os.path.join(ML_DIR, "raw")
FRUIT_WORDS = {  # folder-name keyword -> fruit
    "apple": "apple", "banana": "banana", "orange": "orange", "mango": "mango", "grape": "grapes",
    "guava": "guava", "pomegranate": "pomegranate", "strawberry": "strawberry", "lime": "lime",
    "lemon": "lime", "jujube": "jujube", "ber": "jujube",
}
FRESH_WORDS = ("fresh", "healthy", "good")
ROTTEN_WORDS = ("rotten", "stale", "bad", "spoiled", "spoilt")


def label_local(path: str):
    """Works for folder names like 'Guava__Rotten', 'Pomegranate_Bad', 'freshapples'.
    'Mixed' quality folders and anything not in FRUIT_WORDS are skipped."""
    parts = [p.lower() for p in path.replace("\\", "/").split("/")[:-1]]
    joined = " ".join(parts)
    if "mixed" in joined:
        return None
    fruit = state = None
    for p in reversed(parts):
        tokens = re.split(r"[^a-z]+", p)
        squashed = p.replace("_", "").replace(" ", "")
        if fruit is None:
            for w, f in FRUIT_WORDS.items():
                if w in tokens or (len(w) > 3 and w in squashed):
                    fruit = f
                    break
        if state is None:
            if any(w in squashed for w in ROTTEN_WORDS):
                state = "rotten"
            elif any(w in squashed for w in FRESH_WORDS):
                state = "fresh"
    if not fruit or not state:
        return None
    split = "test" if int(hashlib.md5(path.encode()).hexdigest(), 16) % 100 < TEST_FRACTION * 100 else "train"
    return fruit, state, split


LABELERS = {"kaggle_fresh_rotten": label_kaggle, "healthy_defective": label_healthy_defective}


# ---------------------------------------------------------------- image helpers
def dhash_canonical(img: Image.Image) -> int:
    """Rotation/mirror-invariant 64-bit difference hash (min over the 8 dihedral transforms)."""
    g = img.convert("L").resize((32, 32), Image.BILINEAR)
    best = None
    for t in (None, Image.Transpose.ROTATE_90, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_270):
        r = g if t is None else g.transpose(t)
        for m in (r, r.transpose(Image.Transpose.FLIP_LEFT_RIGHT)):
            s = np.asarray(m.resize((9, 8), Image.BILINEAR), dtype=np.int16)
            v = 0
            for bit in (s[:, 1:] > s[:, :-1]).flatten():
                v = (v << 1) | int(bit)
            best = v if best is None or v < best else best
    return best


def process(data: bytes):
    img = Image.open(io.BytesIO(data))
    img.load()
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    img = img.convert("RGB")
    w, h = img.size
    reason = None
    if min(w, h) < MIN_SIDE:
        reason = "too_small"
    elif max(w, h) / min(w, h) > MAX_ASPECT:
        reason = "odd_aspect"
    std = float(np.asarray(img.resize((64, 64)), dtype=np.float32).std())
    if reason is None and std < MIN_STD:
        reason = "blank"
    if reason is None:
        # black-and-white photos carry no colour cues (the main sign of decay)
        sm = np.asarray(img.resize((64, 64)), dtype=np.float32)
        if np.abs(sm - sm.mean(axis=2, keepdims=True)).mean() < 4:
            reason = "grayscale"
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return img, w, h, std, dhash_canonical(img), reason


def autocrop(img: Image.Image):
    """Crop studio shots (plain light backdrop) to the fruit, so the subject fills the frame
    like a real phone photo would and the backdrop can't become a shortcut for the label.
    Returns (image, too_small)."""
    a = np.asarray(img, dtype=np.int16)
    h, w, _ = a.shape
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    if bg.min() < 200 or (np.abs(border - bg).max(axis=1) < 30).mean() < 0.85:
        return img, False                                   # not a plain light backdrop
    mask = np.abs(a - bg).max(axis=2) > 40
    ys, xs = np.where(mask)
    if len(xs) < 50:
        return img, True
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    side = max(x1 - x0, y1 - y0) * 1.15
    if side < 64:
        return img, True
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    box = [int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2)]
    if side >= 0.9 * min(w, h):
        return img, False                                   # already fills the frame
    canvas = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), tuple(int(v) for v in bg))
    canvas.paste(img.crop((max(box[0], 0), max(box[1], 0), min(box[2], w), min(box[3], h))),
                 (max(-box[0], 0), max(-box[1], 0)))
    return canvas, False


# ---------------------------------------------------------------- download
def raw_url(repo: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(path)}"


def fetch(url: str, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "freshlytics-dataset-builder"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("unreachable")


def read_pool() -> dict:
    rows = {}
    if os.path.exists(POOL_CSV):
        with open(POOL_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows[r["id"]] = r
    return rows


def cmd_download(args):
    os.makedirs(POOL, exist_ok=True)
    done = read_pool()
    todo = []
    for name, labeler in LABELERS.items():
        src_file = os.path.join(SOURCES_DIR, f"{name}.json")
        if not os.path.exists(src_file):
            print(f"! missing {src_file}")
            continue
        src = json.load(open(src_file, encoding="utf-8"))
        for p in src["files"]:
            lab = labeler(p)
            if not lab:
                continue
            iid = hashlib.sha1(f"{name}:{p}".encode()).hexdigest()[:16]
            if iid in done:
                continue
            todo.append((iid, name, src["repo"], src["commit"], p, *lab))
    if os.path.isdir(RAW_DIR):
        for root, _, files in os.walk(RAW_DIR):
            for fn in files:
                if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, RAW_DIR).replace(os.sep, "/")
                lab = label_local(rel)
                iid = hashlib.sha1(f"local:{rel}".encode()).hexdigest()[:16]
                if lab and iid not in done:
                    todo.append((iid, "local", None, None, full, *lab))
    total = len(todo) + len(done)
    print(f"{len(done)} already processed, {len(todo)} to download (of {total}).")
    if not todo:
        print("Download complete.")
        return True

    new_file = not os.path.exists(POOL_CSV)
    fh = open(POOL_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=POOL_FIELDS)
    if new_file:
        writer.writeheader()

    def work(item):
        iid, name, repo, commit, p, fruit, state, split = item
        row = {"id": iid, "source": name, "path": p, "fruit": fruit, "state": state, "split": split,
               "status": "ok", "w": "", "h": "", "dhash": "", "std": ""}
        try:
            if repo is None:
                with open(p, "rb") as fh_:
                    data = fh_.read()
            else:
                data = fetch(raw_url(repo, commit, p))
            img, w, h, std, dh, reason = process(data)
            row.update(w=w, h=h, std=f"{std:.1f}", dhash=f"{dh:016x}")
            if reason:
                row["status"] = reason
            else:
                img.save(os.path.join(POOL, iid + ".jpg"), quality=90, optimize=True)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            row["status"] = "download_failed"  # not recorded -> retried next run
        except Exception:
            row["status"] = "unreadable"
        return row

    start = time.time()
    n = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = []
        it = iter(todo)
        for item in it:
            futures.append(ex.submit(work, item))
            if len(futures) >= args.workers * 4:
                break
        while futures:
            f = futures.pop(0)
            row = f.result()
            if row["status"] != "download_failed":
                writer.writerow(row)
            n += 1
            if n % 200 == 0:
                fh.flush()
                rate = n / (time.time() - start)
                print(f"  {len(done) + n}/{total}  ({rate:.0f} img/s)", flush=True)
            if args.max_seconds and time.time() - start > args.max_seconds:
                for rest in futures:
                    r2 = rest.result()
                    if r2["status"] != "download_failed":
                        writer.writerow(r2)
                futures = []
                break
            nxt = next(it, None)
            if nxt is not None:
                futures.append(ex.submit(work, nxt))
    fh.close()
    remaining = len(todo) - n
    if remaining > 0:
        print(f"Stopped after the time budget; {remaining} left. Run `download` again to continue.")
        return False
    print("Download complete.")
    return True


# ---------------------------------------------------------------- finalize
def cmd_finalize(args):
    rows = list(read_pool().values())
    if not rows:
        sys.exit("Nothing downloaded yet — run `download` first.")
    expected = sum(
        1 for name, labeler in LABELERS.items() if os.path.exists(os.path.join(SOURCES_DIR, f"{name}.json"))
        for p in json.load(open(os.path.join(SOURCES_DIR, f"{name}.json"), encoding="utf-8"))["files"] if labeler(p)
    )
    if len([r for r in rows if r["source"] != "local"]) < expected and not args.force:
        sys.exit(f"Only {len(rows)} of {expected} images downloaded. Run `download` until it completes "
                 "(or pass --force to build from what you have). The existing dataset was left untouched.")
    rng = random.Random(42)
    reasons = Counter(r["status"] for r in rows if r["status"] != "ok")
    ok = [r for r in rows if r["status"] == "ok" and os.path.exists(os.path.join(POOL, r["id"] + ".jpg"))]
    gray = []
    for r in ok:
        sm = np.asarray(Image.open(os.path.join(POOL, r["id"] + ".jpg")).convert("RGB").resize((64, 64)), dtype=np.float32)
        if np.abs(sm - sm.mean(axis=2, keepdims=True)).mean() < 4:
            gray.append(r["id"])
    reasons["grayscale"] += len(gray)
    ok = [r for r in ok if r["id"] not in set(gray)]

    # --- near-duplicate removal
    # Candidates share one 16-bit chunk of the dHash. A candidate only counts as a duplicate
    # if its 32x32 colour thumbnail correlates >= DUP_CORR with an already-kept photo under one
    # of the 8 rotations/mirrors. Matching is direct (no transitive chaining), so different
    # fruits shot on the same white backdrop are not merged.
    print("Fingerprinting images…")
    hashes = {r["id"]: int(r["dhash"], 16) for r in ok}
    views = {}
    for r in ok:
        a = np.asarray(Image.open(os.path.join(POOL, r["id"] + ".jpg")).convert("RGB").resize((32, 32), Image.BILINEAR),
                       dtype=np.float32)
        vs = []
        for k in range(4):
            v = np.rot90(a, k)
            for m in (v, v[:, ::-1]):
                m = (m - m.mean()) / (m.std() + 1e-6)
                vs.append(m.flatten())
        views[r["id"]] = np.stack(vs)  # 8 x 3072

    # test photos first so a duplicate of a test photo is removed from train (no leakage)
    order = sorted(ok, key=lambda m: (m["split"] != "test", -int(m["w"] or 0) * int(m["h"] or 0)))
    band_keep = defaultdict(list)
    keeper_of = {}
    kept_rows = {}
    for r in order:
        hv = hashes[r["id"]]
        keys = [(b, (hv >> (16 * b)) & 0xFFFF) for b in range(4)]
        cands = {k for key in keys for k in band_keep[key]}
        match = None
        if cands:
            cl = list(cands)
            M = np.stack([views[c][0] for c in cl])                 # c x 3072
            sims = (views[r["id"]] @ M.T).max(axis=0) / M.shape[1]  # best over 8 views
            j = int(np.argmax(sims))
            if sims[j] >= DUP_CORR:
                match = cl[j]
        if match is None:
            kept_rows[r["id"]] = r
            for key in keys:
                band_keep[key].append(r["id"])
        else:
            keeper_of[r["id"]] = match

    kept, dropped = [], []
    conflict_keepers = set()
    rows_by_id = {r["id"]: r for r in ok}
    for dup, keeper in keeper_of.items():
        d, k = rows_by_id[dup], kept_rows[keeper]
        if (d["fruit"], d["state"]) != (k["fruit"], k["state"]):
            conflict_keepers.add(keeper)
            dropped.append((dict(d, dup_of=keeper), "label_conflict"))
        else:
            dropped.append((dict(d, dup_of=keeper), "duplicate"))
    for iid, r in kept_rows.items():
        if iid in conflict_keepers:   # same photo appears with two labels -> unreliable
            dropped.append((r, "label_conflict"))
        else:
            kept.append(r)
    conflicting = len(conflict_keepers)

    # --- subject too small to judge (e.g. a tiny fruit in a big white frame)
    small = []
    for r in kept:
        _, too_small = autocrop(Image.open(os.path.join(POOL, r["id"] + ".jpg")).convert("RGB"))
        (small if too_small else []).append(r)
    small_ids = {r["id"] for r in small}
    kept = [r for r in kept if r["id"] not in small_ids]
    dropped += [(r, "subject_too_small") for r in small]

    # --- per-class cap
    by_class = defaultdict(list)
    for r in kept:
        by_class[(r["split"], r["state"] + r["fruit"])].append(r)
    final = []
    for (split, cls), items in by_class.items():
        rng.shuffle(items)
        cap = CAP_PER_CLASS[split]
        final += items[:cap]
        dropped += [(m, "class_cap") for m in items[cap:]]

    # --- materialise
    for split in ("train", "test"):
        d = os.path.join(OUT, split)
        if os.path.isdir(d):
            shutil.rmtree(d)
    rej_root = os.path.join(OUT, "_rejected")
    if os.path.isdir(rej_root):
        shutil.rmtree(rej_root)
    cropped = 0
    for r in final:
        dst = os.path.join(OUT, r["split"], r["state"] + r["fruit"])
        os.makedirs(dst, exist_ok=True)
        img = Image.open(os.path.join(POOL, r["id"] + ".jpg")).convert("RGB")
        out, _ = autocrop(img)
        cropped += out is not img
        out.save(os.path.join(dst, r["id"] + ".jpg"), quality=90)
    for m, why in dropped:
        if why == "class_cap":
            continue
        dst = os.path.join(rej_root, why)
        os.makedirs(dst, exist_ok=True)
        shutil.copyfile(os.path.join(POOL, m["id"] + ".jpg"), os.path.join(dst, f"{m['state']}{m['fruit']}_{m['id']}" + (f"__same_as_{m['dup_of']}" if m.get("dup_of") else "") + ".jpg"))

    with open(os.path.join(OUT, "manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "split", "fruit", "state", "source", "source_path"])
        for r in sorted(final, key=lambda r: (r["split"], r["state"], r["fruit"], r["id"])):
            w.writerow([f"{r['split']}/{r['state']}{r['fruit']}/{r['id']}.jpg", r["split"], r["fruit"], r["state"],
                        r["source"], r["path"]])

    counts = Counter((r["split"], r["state"] + r["fruit"]) for r in final)
    drop_counts = Counter(why for _, why in dropped)
    report = {
        "total_source_images": len(rows),
        "kept": len(final),
        "rejected_quality": dict(reasons),
        "rejected_dedupe_and_balance": dict(drop_counts),
        "duplicate_groups_with_conflicting_labels": conflicting,
        "studio_shots_cropped_to_fruit": cropped,
        "classes": {f"{s}/{c}": n for (s, c), n in sorted(counts.items())},
    }
    json.dump(report, open(os.path.join(OUT, "report.json"), "w"), indent=2)
    write_review(final)
    print(json.dumps(report, indent=2))
    print(f"\nDataset written to {OUT}. Open review.html to eyeball each class.")


def write_review(final, per_class: int = 60):
    rng = random.Random(7)
    by = defaultdict(list)
    for r in final:
        by[r["state"] + r["fruit"]].append(r)
    parts = ["<!doctype html><meta charset=utf-8><title>Freshlytics dataset review</title>",
             "<style>body{font:14px system-ui;margin:24px;background:#f2f5ee;color:#17231b}"
             "h2{margin:28px 0 8px}div{display:flex;flex-wrap:wrap;gap:4px}"
             "img{width:96px;height:96px;object-fit:cover;border-radius:6px}</style>",
             "<h1>Dataset review</h1><p>A random sample from each training class. "
             "Anything that doesn't belong can be deleted from <code>ml/data_v2</code> before training.</p>"]
    for cls in sorted(by):
        items = by[cls]
        sample = rng.sample(items, min(per_class, len(items)))
        parts.append(f"<h2>{html.escape(cls)} <small>({len(items)} images)</small></h2><div>")
        parts += [f"<img loading=lazy src='{r['split']}/{cls}/{r['id']}.jpg' title='{html.escape(r['path'])}'>" for r in sample]
        parts.append("</div>")
    open(os.path.join(OUT, "review.html"), "w", encoding="utf-8").write("\n".join(parts))


# ---------------------------------------------------------------- audit
def cmd_audit(args):
    """Use the current model to flag photos whose label it strongly disagrees with."""
    sys.path.insert(0, os.path.dirname(ML_DIR))
    import torch

    from ml.inference import get_predictor
    from ml.train import load_tensor, scan_split

    model = get_predictor().model.cpu().eval()
    fruits = list(getattr(model, "fruits", ["apple", "banana", "orange"]))
    n = len(fruits)
    flagged = []
    for split in ("train", "test"):
        items = scan_split(os.path.join(OUT, split))
        for i in range(0, len(items), 64):
            batch = items[i:i + 64]
            x = torch.stack([load_tensor(p, augment=False) for p, _, _ in batch])
            with torch.no_grad():
                pr = torch.softmax(model(x), 1)
            for (p, state, fruit), row in zip(batch, pr):
                rot = float(row[n:].sum())
                wrong = rot if state == "fresh" else 1 - rot
                if wrong >= args.threshold:
                    flagged.append((wrong, p, state, fruit))
            print(f"  {split}: {min(i + 64, len(items))}/{len(items)}", end="\r")
        print()
    flagged.sort(reverse=True)
    out = os.path.join(OUT, "audit.html")
    parts = ["<!doctype html><meta charset=utf-8><title>Audit</title><style>body{font:14px system-ui;margin:24px}"
             "figure{display:inline-block;margin:4px;width:130px}img{width:130px;height:130px;object-fit:cover}"
             "figcaption{font-size:12px}</style>",
             f"<h1>{len(flagged)} photos the model disagrees with (≥ {args.threshold:.0%})</h1>"]
    for wrong, p, state, fruit in flagged:
        rel = os.path.relpath(p, OUT).replace(os.sep, "/")
        parts.append(f"<figure><img src='{rel}'><figcaption>labelled {state} {fruit}, "
                     f"{wrong:.0%} disagreement</figcaption></figure>")
    open(out, "w", encoding="utf-8").write("\n".join(parts))
    if args.quarantine:
        qdir = os.path.join(OUT, "_rejected", "model_disagreement")
        os.makedirs(qdir, exist_ok=True)
        for _, p, _, _ in flagged:
            shutil.move(p, os.path.join(qdir, os.path.basename(os.path.dirname(p)) + "_" + os.path.basename(p)))
        print(f"Moved {len(flagged)} images to {qdir}")
    print(f"Wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["download", "finalize", "audit", "all"])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-seconds", type=float, default=0, help="stop downloading after this many seconds (resumable)")
    ap.add_argument("--threshold", type=float, default=0.97, help="audit: disagreement level to flag")
    ap.add_argument("--force", action="store_true", help="finalize even if the download is incomplete")
    ap.add_argument("--quarantine", action="store_true", help="audit: move flagged images to _rejected/")
    args = ap.parse_args()
    if args.command in ("download", "all"):
        complete = cmd_download(args)
        if args.command == "all" and complete:
            cmd_finalize(args)
    elif args.command == "finalize":
        cmd_finalize(args)
    else:
        cmd_audit(args)


if __name__ == "__main__":
    main()

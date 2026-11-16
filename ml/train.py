"""
Extend / re-train the Freshlytics freshness model on your own images.

The ResNet50V2 backbone stays frozen (it already knows what decay looks like);
we re-train only the small classification head, so this runs fine on a laptop CPU.

Dataset layout (same as the Kaggle "fruits fresh and rotten" dataset — just add
folders for new fruits):

    ml/data_v2/
      train/
        freshapples/   rottenapples/
        freshbanana/   rottenbanana/
        freshoranges/  rottenoranges/
        freshmango/    rottenmango/      <- new fruit: just add both folders
      test/
        ...same folder names...

Folder names must start with "fresh" or "rotten"; the rest is the fruit name
(plural "s" is stripped). Every fruit needs both a fresh and a rotten folder.
Aim for 200+ varied photos per folder (different backgrounds, lighting, angles) —
the old dataset failed because every "fresh" photo had a white background.

    python ml/train.py --data ml/data_v2 --epochs 15
"""
import argparse
import os
import random
import sys

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageEnhance, ImageOps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.freshness_net import INPUT_SIZE, FreshnessNet  # noqa: E402
from ml.inference import DEFAULT_CHECKPOINT, get_predictor  # noqa: E402

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def parse_dir(name: str):
    n = name.lower().replace("-", "").replace("_", "").replace(" ", "")
    for state in ("fresh", "rotten"):
        if n.startswith(state):
            fruit = n[len(state):]
            if fruit.endswith("es") and fruit[:-2] in ("orang", "mang", "grap"):
                fruit = fruit[:-1]
            if fruit.endswith("s") and fruit not in ("grapes",):
                fruit = fruit[:-1]
            if fruit == "grape":
                fruit = "grapes"
            return state, fruit
    return None


def scan_split(root: str):
    items = []
    if not os.path.isdir(root):
        return items
    for d in sorted(os.listdir(root)):
        parsed = parse_dir(d)
        if not parsed:
            continue
        for f in os.listdir(os.path.join(root, d)):
            if f.lower().endswith(EXTS):
                items.append((os.path.join(root, d, f), parsed[0], parsed[1]))
    return items


def load_tensor(path: str, augment: bool) -> torch.Tensor:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = img.size
    s = min(w, h)
    if augment:
        s = int(s * random.uniform(0.75, 1.0))
        x0, y0 = random.randint(0, w - s), random.randint(0, h - s)
    else:
        x0, y0 = (w - s) // 2, (h - s) // 2
    img = img.crop((x0, y0, x0 + s, y0 + s)).resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
    if augment and random.random() < 0.5:
        img = ImageOps.mirror(img)
    if augment:
        img = img.rotate(random.uniform(-15, 15), resample=Image.BILINEAR)
        # lighting varies a lot between phone photos
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.75, 1.25))
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.8, 1.2))
        img = ImageEnhance.Color(img).enhance(random.uniform(0.85, 1.15))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1)


@torch.no_grad()
def extract(model: FreshnessNet, items, label_of, augment: bool, bs: int = 32):
    feats, labels = [], []
    for i in range(0, len(items), bs):
        batch = []
        for path, state, fruit in items[i:i + bs]:
            try:
                batch.append((load_tensor(path, augment), label_of(state, fruit)))
            except Exception as e:  # unreadable file
                print(f"  skip {path}: {e}")
        if not batch:
            continue
        x = torch.stack([b[0] for b in batch])
        _, f = model(x, return_features=True)
        feats.append(f)
        labels += [b[1] for b in batch]
        print(f"  features {min(i + bs, len(items))}/{len(items)}", end="\r")
    print()
    return torch.cat(feats), torch.tensor(labels)


def main():
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "data_v2"))
    ap.add_argument("--base", default=None, help="checkpoint whose backbone to reuse (default: the active model)")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--aug_passes", type=int, default=2, help="augmented feature passes over the training set")
    ap.add_argument("--out", default=DEFAULT_CHECKPOINT)
    args = ap.parse_args()

    train_items = scan_split(os.path.join(args.data, "train"))
    test_items = scan_split(os.path.join(args.data, "test")) or scan_split(os.path.join(args.data, "val"))
    if not train_items:
        sys.exit(f"No training images found under {args.data}/train (see the docstring for the layout).")

    fruits = sorted({f for _, _, f in train_items})
    for fr in fruits:
        states = {s for _, s, f in train_items if f == fr}
        if states != {"fresh", "rotten"}:
            sys.exit(f"Fruit '{fr}' needs both fresh and rotten folders (found {states}).")
    n = len(fruits)
    label_of = lambda state, fruit: fruits.index(fruit) + (n if state == "rotten" else 0)  # noqa: E731
    print(f"Fruits: {fruits}  |  train images: {len(train_items)}  test images: {len(test_items)}")

    base = (FreshnessNet.from_checkpoint(args.base) if args.base else get_predictor().model).cpu().eval()
    print("Extracting features (frozen backbone)…")
    feats, labels = [], []
    for p in range(args.aug_passes + 1):
        f, l = extract(base, train_items, label_of, augment=p > 0)
        feats.append(f), labels.append(l)
    Xtr, ytr = torch.cat(feats), torch.cat(labels)
    Xte, yte = extract(base, test_items, label_of, augment=False) if test_items else (None, None)

    head = nn.Sequential(nn.Linear(Xtr.shape[1], 64), nn.ReLU(), nn.Dropout(0.5), nn.Linear(64, 2 * n))
    counts = torch.bincount(ytr, minlength=2 * n).float().clamp(min=1)
    loss_fn = nn.CrossEntropyLoss(weight=(counts.sum() / counts) / (2 * n))
    opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    best_acc, best_state = -1.0, None
    for epoch in range(args.epochs):
        head.train()
        perm = torch.randperm(len(Xtr))
        tot = 0.0
        for i in range(0, len(perm), 64):
            idx = perm[i:i + 64]
            opt.zero_grad()
            loss = loss_fn(head(Xtr[idx]), ytr[idx])
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        sched.step()
        head.eval()
        with torch.no_grad():
            if Xte is not None:
                pred = head(Xte).argmax(1)
                acc = (pred == yte).float().mean().item()
                rot_acc = ((pred >= n) == (yte >= n)).float().mean().item()
            else:
                acc = rot_acc = (head(Xtr).argmax(1) == ytr).float().mean().item()
        print(f"epoch {epoch + 1:2d}  loss {tot / len(Xtr):.4f}  acc {acc:.3f}  fresh/rotten acc {rot_acc:.3f}")
        if acc > best_acc:
            best_acc, best_state = acc, {k: v.clone() for k, v in head.state_dict().items()}

    head.load_state_dict(best_state)
    topology = [dict(node, cfg=dict(node["cfg"])) for node in base.topology]
    dense_names = [nd["name"] for nd in topology if nd["type"] == "Dense"]
    for nd in topology:
        if nd["name"] == dense_names[-1]:
            nd["cfg"]["out"] = 2 * n
    model = FreshnessNet(topology)
    sd = base.state_dict()
    sd[f"layers.{dense_names[0]}.weight"] = head[0].weight.data
    sd[f"layers.{dense_names[0]}.bias"] = head[0].bias.data
    sd[f"layers.{dense_names[-1]}.weight"] = head[3].weight.data
    sd[f"layers.{dense_names[-1]}.bias"] = head[3].bias.data
    model.load_state_dict(sd)

    if os.path.exists(args.out):
        backup = args.out.replace(".pth", ".backup.pth")
        os.replace(args.out, backup)
        print(f"Previous checkpoint backed up to {backup}")
    torch.save({"topology": topology, "state_dict": model.state_dict(), "fruits": fruits,
                "input_size": INPUT_SIZE, "preprocess": "rgb/255"}, args.out)
    print(f"Saved {args.out}  (best test accuracy {best_acc:.3f}). Restart the backend to load it.")


if __name__ == "__main__":
    main()

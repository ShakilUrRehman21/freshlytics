"""
Measure a Freshlytics checkpoint on the held-out test set.

    python ml/evaluate.py                                   # active model on ml/data_v2/test
    python ml/evaluate.py --ckpt ml/checkpoints/x.pth --data ml/data_v2 --json report.json

Reports
  * fresh-vs-rotten accuracy (what the freshness score depends on), per fruit
  * fruit recognition accuracy (only for fruits the checkpoint knows)
  * a confusion table
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.freshness_net import FreshnessNet  # noqa: E402
from ml.inference import DEFAULT_CHECKPOINT  # noqa: E402
from ml.train import load_tensor, scan_split  # noqa: E402


@torch.no_grad()
def evaluate(ckpt: str, data: str, split: str = "test") -> dict:
    model = FreshnessNet.from_checkpoint(ckpt).eval()
    fruits = list(model.fruits)
    n = len(fruits)
    items = scan_split(os.path.join(data, split))
    if not items:
        sys.exit(f"No images found in {os.path.join(data, split)}")

    per_fruit = defaultdict(lambda: Counter())
    confusion = Counter()
    for i in range(0, len(items), 64):
        batch = items[i:i + 64]
        x = torch.stack([load_tensor(p, augment=False) for p, _, _ in batch])
        probs = torch.softmax(model(x), 1)
        for (_, state, fruit), pr in zip(batch, probs):
            rot = float(pr[n:].sum())
            pred_state = "rotten" if rot >= 0.5 else "fresh"
            pred_fruit = fruits[int((pr[:n] + pr[n:]).argmax())]
            c = per_fruit[fruit]
            c["n"] += 1
            c["state_ok"] += pred_state == state
            if fruit in fruits:
                c["fruit_known"] += 1
                c["fruit_ok"] += pred_fruit == fruit
            confusion[(f"{state} {fruit}", f"{pred_state} {pred_fruit}")] += 1
        print(f"  {min(i + 64, len(items))}/{len(items)}", end="\r")
    print()

    total = sum(c["n"] for c in per_fruit.values())
    report = {
        "checkpoint": os.path.basename(ckpt),
        "images": total,
        "fresh_vs_rotten_accuracy": round(sum(c["state_ok"] for c in per_fruit.values()) / total, 4),
        "fruit_accuracy_on_known_fruits": round(
            sum(c["fruit_ok"] for c in per_fruit.values()) / max(1, sum(c["fruit_known"] for c in per_fruit.values())), 4),
        "per_fruit": {
            f: {"images": c["n"], "fresh_vs_rotten": round(c["state_ok"] / c["n"], 4),
                "fruit_recognition": round(c["fruit_ok"] / c["fruit_known"], 4) if c["fruit_known"] else None}
            for f, c in sorted(per_fruit.items())
        },
        "confusion": [{"true": t, "predicted": p, "count": k} for (t, p), k in sorted(confusion.items())],
    }
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=DEFAULT_CHECKPOINT)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_v2"))
    ap.add_argument("--json", default=None, help="also write the report to this file")
    args = ap.parse_args()
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    rep = evaluate(args.ckpt, args.data)
    print(f"\n{rep['checkpoint']} on {rep['images']} test images")
    print(f"  fresh vs rotten : {rep['fresh_vs_rotten_accuracy']:.1%}")
    print(f"  fruit type      : {rep['fruit_accuracy_on_known_fruits']:.1%} (fruits the model knows)")
    for f, r in rep["per_fruit"].items():
        fr = f"{r['fruit_recognition']:.1%}" if r["fruit_recognition"] is not None else "not trained"
        print(f"    {f:<8} fresh/rotten {r['fresh_vs_rotten']:.1%}   recognition {fr}   ({r['images']} imgs)")
    if args.json:
        json.dump(rep, open(args.json, "w"), indent=2)


if __name__ == "__main__":
    main()

"""
FreshnessNet — a small PyTorch runtime for the ResNet50V2 fresh/rotten classifier.

The network was originally trained in Keras (ResNet50V2 backbone, 150x150 input,
~10.9k images from the Kaggle "Fruits fresh and rotten for classification" dataset,
~98-99% validation accuracy) and shipped as a TensorFlow.js model in
ml/extracted/final_bangkit-master. `convert_tfjs.py` turns that model into a single
self-contained checkpoint (topology + weights) that this module executes, so the
backend only needs PyTorch.

Output classes (softmax order):
    0 fresh apple, 1 fresh banana, 2 fresh orange,
    3 rotten apple, 4 rotten banana, 5 rotten orange
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

CLASSES = [
    ("apple", "fresh"),
    ("banana", "fresh"),
    ("orange", "fresh"),
    ("apple", "rotten"),
    ("banana", "rotten"),
    ("orange", "rotten"),
]
INPUT_SIZE = 150


class FreshnessNet(nn.Module):
    """Executes a Keras functional-model topology with PyTorch layers.

    `topology` is a list of dicts: {name, type, inputs: [names], cfg: {...}} in
    execution order. Tensors flow in NCHW layout.
    """

    def __init__(self, topology: list[dict]):
        super().__init__()
        self.topology = topology
        self.layers = nn.ModuleDict()
        for node in topology:
            t, cfg, name = node["type"], node["cfg"], node["name"]
            if t == "Conv2D":
                self.layers[name] = nn.Conv2d(
                    cfg["in"], cfg["out"], tuple(cfg["kernel"]), stride=tuple(cfg["stride"]),
                    padding=0, bias=cfg["bias"],
                )
            elif t == "BatchNormalization":
                self.layers[name] = nn.BatchNorm2d(cfg["ch"], eps=cfg["eps"])
            elif t == "Dense":
                self.layers[name] = nn.Linear(cfg["in"], cfg["out"])

    def forward(self, x: torch.Tensor, return_features: bool = False):
        cache: dict[str, torch.Tensor] = {}
        out = x
        features = None
        for node in self.topology:
            t, cfg, name = node["type"], node["cfg"], node["name"]
            ins = [cache[i] for i in node["inputs"]] if node["inputs"] else [x]
            h = ins[0]
            if t == "InputLayer":
                out = x
            elif t == "ZeroPadding2D":
                (pt, pb), (pl, pr) = cfg["padding"]
                out = F.pad(h, (pl, pr, pt, pb))
            elif t in ("Conv2D", "BatchNormalization"):
                out = self.layers[name](h)
            elif t == "Activation":
                out = F.relu(h) if cfg["activation"] == "relu" else h
            elif t == "MaxPooling2D":
                out = F.max_pool2d(h, tuple(cfg["pool"]), tuple(cfg["stride"]))
            elif t == "AveragePooling2D":
                out = F.avg_pool2d(h, tuple(cfg["pool"]), tuple(cfg["stride"]))
            elif t == "Add":
                out = ins[0]
                for other in ins[1:]:
                    out = out + other
            elif t == "Flatten":
                # Keras flattens channels-last
                out = h.permute(0, 2, 3, 1).reshape(h.shape[0], -1)
                features = out
            elif t == "Dense":
                out = self.layers[name](h)
                if cfg["activation"] == "relu":
                    out = F.relu(out)
            elif t == "Dropout":
                out = h
            else:
                raise ValueError(f"Unsupported layer type {t}")
            cache[name] = out
        # final Dense is softmax in Keras; we return logits
        if return_features:
            return out, features
        return out

    @classmethod
    def from_checkpoint(cls, path: str, map_location="cpu") -> "FreshnessNet":
        ckpt = torch.load(path, map_location=map_location, weights_only=False)
        model = cls(ckpt["topology"])
        model.load_state_dict(ckpt["state_dict"])
        model.fruits = ckpt.get("fruits", ["apple", "banana", "orange"])
        model.eval()
        return model

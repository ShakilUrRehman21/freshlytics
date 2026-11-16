"""
Convert the TensorFlow.js ResNet50V2 fresh/rotten model into a PyTorch checkpoint.

    python ml/convert_tfjs.py \
        --src ml/extracted/final_bangkit-master/public/model/model3/transfer_learning \
        --out ml/checkpoints/freshness_resnet50v2.pth

Only needs numpy + torch (no TensorFlow).
"""
import argparse
import json
import os

import numpy as np
import torch

try:
    from ml.freshness_net import FreshnessNet
except ImportError:  # run from inside ml/
    from freshness_net import FreshnessNet


def load_tfjs(src: str):
    with open(os.path.join(src, "model.json")) as f:
        model = json.load(f)
    weights = {}
    for group in model["weightsManifest"]:
        buf = b"".join(open(os.path.join(src, p), "rb").read() for p in group["paths"])
        offset = 0
        for w in group["weights"]:
            assert w["dtype"] == "float32" and "quantization" not in w, w
            n = int(np.prod(w["shape"])) if w["shape"] else 1
            arr = np.frombuffer(buf, dtype="<f4", count=n, offset=offset).reshape(w["shape"])
            offset += n * 4
            weights[w["name"]] = arr.copy()
    return model["modelTopology"]["model_config"]["config"]["layers"], weights


def build(layers, weights):
    topology, state = [], {}
    channels = {}
    for l in layers:
        t, c, name = l["class_name"], l["config"], l["name"]
        inputs = [n[0] for n in l["inbound_nodes"][0]] if l["inbound_nodes"] else []
        cfg = {}
        if t == "InputLayer":
            channels[name] = c["batch_input_shape"][-1]
        elif t == "Conv2D":
            k = weights[f"{name}/kernel"]  # kh, kw, in, out
            cfg = dict(in_=None, kernel=c["kernel_size"], stride=c["strides"], bias=c["use_bias"])
            cfg = {"in": k.shape[2], "out": k.shape[3], "kernel": c["kernel_size"],
                   "stride": c["strides"], "bias": c["use_bias"]}
            state[f"layers.{name}.weight"] = torch.from_numpy(k.transpose(3, 2, 0, 1).copy())
            if c["use_bias"]:
                state[f"layers.{name}.bias"] = torch.from_numpy(weights[f"{name}/bias"])
            channels[name] = k.shape[3]
        elif t == "BatchNormalization":
            ch = channels[inputs[0]]
            cfg = {"ch": ch, "eps": c["epsilon"]}
            state[f"layers.{name}.weight"] = torch.from_numpy(weights[f"{name}/gamma"])
            state[f"layers.{name}.bias"] = torch.from_numpy(weights[f"{name}/beta"])
            state[f"layers.{name}.running_mean"] = torch.from_numpy(weights[f"{name}/moving_mean"])
            state[f"layers.{name}.running_var"] = torch.from_numpy(weights[f"{name}/moving_variance"])
            state[f"layers.{name}.num_batches_tracked"] = torch.tensor(0)
            channels[name] = ch
        elif t == "Dense":
            k = weights[f"{name}/kernel"]  # in, out
            cfg = {"in": k.shape[0], "out": k.shape[1], "activation": c["activation"]}
            state[f"layers.{name}.weight"] = torch.from_numpy(k.T.copy())
            state[f"layers.{name}.bias"] = torch.from_numpy(weights[f"{name}/bias"])
            channels[name] = k.shape[1]
        elif t == "ZeroPadding2D":
            cfg = {"padding": c["padding"]}
        elif t == "Activation":
            cfg = {"activation": c["activation"]}
        elif t in ("MaxPooling2D", "AveragePooling2D"):
            cfg = {"pool": c["pool_size"], "stride": c["strides"] or c["pool_size"]}
        if t not in ("Conv2D", "BatchNormalization", "Dense", "InputLayer"):
            channels[name] = channels.get(inputs[0]) if inputs else None
        topology.append({"name": name, "type": t, "inputs": inputs, "cfg": cfg})
    return topology, state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(os.path.dirname(__file__), "extracted", "final_bangkit-master",
                                                  "public", "model", "model3", "transfer_learning"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "checkpoints", "freshness_resnet50v2.pth"))
    args = ap.parse_args()

    layers, weights = load_tfjs(args.src)
    topology, state = build(layers, weights)
    model = FreshnessNet(topology)
    model.load_state_dict(state, strict=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    torch.save({"topology": topology, "state_dict": model.state_dict(),
                "input_size": 150, "preprocess": "rgb/255"}, args.out)
    print(f"Saved {args.out} ({len(topology)} layers, {sum(p.numel() for p in model.parameters()):,} params)")


if __name__ == "__main__":
    main()

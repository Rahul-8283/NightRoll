"""Convert the Silent-Face MiniFASNetV2 anti-spoof weights to ONNX (Phase 5, task 6.1).

The upstream project publishes PyTorch `.pth` weights only. This script downloads the weights and the
network definition, exports `models/antispoof.onnx`, and checks the ONNX output against PyTorch.

PyTorch is only needed for this one-off conversion, so it is not a worker dependency. Run it with:

    uv run --with torch==2.14.1 --with onnx==1.23.2 python scripts/convert_antispoof.py

The exported model takes a float32 tensor of shape (1, 3, 80, 80) holding a BGR face crop with raw
0 to 255 values (the upstream preprocessing does not scale to 0..1) and returns 3 logits:
class 0 = print attack, class 1 = real face, class 2 = screen replay.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT_DIR / "models"

BASE = "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master"
WEIGHTS_URL = f"{BASE}/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"
NETWORK_URL = f"{BASE}/src/model_lib/MiniFASNet.py"

WEIGHTS_SHA256 = "a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0"
INPUT_SIZE = 80
KERNEL = ((INPUT_SIZE + 15) // 16, (INPUT_SIZE + 15) // 16)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> None:
    if dest.exists():
        return
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    args = parser.parse_args()

    try:
        import numpy as np
        import onnx
        import onnxruntime as ort
        import torch
    except ImportError as exc:
        print(
            f"Missing {exc.name}. Run: uv run --with torch==2.14.1 --with onnx==1.23.2 "
            "python scripts/convert_antispoof.py"
        )
        return 1

    work = args.models_dir / "_antispoof_src"
    work.mkdir(parents=True, exist_ok=True)
    weights = work / "2.7_80x80_MiniFASNetV2.pth"
    network = work / "MiniFASNet.py"
    fetch(WEIGHTS_URL, weights)
    fetch(NETWORK_URL, network)
    if sha256(weights) != WEIGHTS_SHA256:
        print(
            "ERROR: upstream weights changed; their SHA-256 no longer matches the one recorded here.", file=sys.stderr
        )
        return 1

    sys.path.insert(0, str(work))
    from MiniFASNet import MiniFASNetV2  # noqa: E402  (downloaded above)

    model = MiniFASNetV2(conv6_kernel=KERNEL)
    state = torch.load(weights, map_location="cpu")
    # The weights were saved from a DataParallel model, so every key carries a "module." prefix.
    state = {(k[7:] if k.startswith("module.") else k): v for k, v in state.items()}
    model.load_state_dict(state)
    model.eval()

    out_path = args.models_dir / "antispoof.onnx"
    dummy = torch.randint(0, 256, (1, 3, INPUT_SIZE, INPUT_SIZE)).float()
    export_kwargs = dict(
        input_names=["input"],
        output_names=["logits"],
        opset_version=13,
        do_constant_folding=True,
    )
    try:
        torch.onnx.export(model, dummy, str(out_path), dynamo=False, **export_kwargs)
    except TypeError:
        torch.onnx.export(model, dummy, str(out_path), **export_kwargs)

    onnx.checker.check_model(onnx.load(str(out_path)))

    # Parity check: the ONNX graph must reproduce the PyTorch logits.
    session = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    worst = 0.0
    for _ in range(5):
        sample = torch.randint(0, 256, (1, 3, INPUT_SIZE, INPUT_SIZE)).float()
        with torch.no_grad():
            expected = model(sample).numpy()
        got = session.run(None, {"input": sample.numpy()})[0]
        worst = max(worst, float(np.abs(expected - got).max()))
    print(f"Max |PyTorch - ONNX| over 5 random inputs: {worst:.2e}")
    if worst > 1e-3:
        print("ERROR: ONNX output does not match PyTorch", file=sys.stderr)
        return 1

    print(f"Wrote {out_path} ({out_path.stat().st_size // 1024} KB)")
    print(f"  weights sha256: {sha256(weights)}")
    print(f"  onnx sha256:    {sha256(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

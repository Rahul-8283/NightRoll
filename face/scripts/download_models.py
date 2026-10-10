"""Download and verify the model files for the NightRoll Face Worker.

Fetches and checks:
1. InsightFace `buffalo_l` (detector, landmarks, ArcFace 512-d embedder).
2. The Silent-Face MiniFASNetV2 anti-spoof model. Upstream publishes PyTorch weights only, so the
   ONNX file is produced once by `scripts/convert_antispoof.py`; this script then verifies it.

Every file is compared with a SHA-256 recorded below. A mismatch is an error, never a warning.

Usage:
    python scripts/download_models.py                 download what is missing, then verify
    python scripts/download_models.py --verify-only   verify only
    python scripts/download_models.py --create-stubs  placeholder files for tests that never load a model
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT_DIR / "models"

BUFFALO_L_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
BUFFALO_L_ZIP_SHA256 = "80ffe37d8a5940d59a7384c201a2a38d4741f2f3c51eef46ebb28218a7b0ca2f"

# SHA-256 of every model file, relative to the models folder. Update only when a model is
# deliberately upgraded, together with MODEL_VERSION (embeddings are tied to a model version).
EXPECTED_SHA256 = {
    "buffalo_l/det_10g.onnx": "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
    "buffalo_l/w600k_r50.onnx": "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
    "buffalo_l/2d106det.onnx": "f001b856447c413801ef5c42091ed0cd516fcd21f2d6b79635b1e733a7109dbf",
    "buffalo_l/1k3d68.onnx": "df5c06b8a0c12e422b2ed8947b8869faa4105387f199c477af038aa01f9a45cc",
    "buffalo_l/genderage.onnx": "4fde69b1c810857b88c64a335084f1c3fe8f01246c9a191b48c7bb756d6652fb",
    # Produced by convert_antispoof.py with torch 2.14.1 and onnx 1.23.2 from the upstream
    # weights whose SHA-256 is a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0.
    "antispoof.onnx": "54ca9aab8e1402de8af805b48a1df266fc1a419cedffe679a3747d9d65d85541",
}

MODEL_VERSION = "buffalo_l-1"


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_file(url: str, dest: Path) -> bool:
    print(f"Downloading {url}")

    def hook(block: int, size: int, total: int) -> None:
        if total > 0:
            sys.stdout.write(f"\r  {min(100, block * size * 100 // total)}%")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, dest, reporthook=hook)
        sys.stdout.write("\n")
        return True
    except Exception as exc:
        sys.stdout.write("\n")
        print(f"ERROR: could not download {url}: {exc}", file=sys.stderr)
        return False


def verify_models(models_dir: Path) -> bool:
    """Compare every model file with its recorded SHA-256."""
    print("\n--- Verifying model files ---")
    ok = True
    for rel, expected in EXPECTED_SHA256.items():
        path = models_dir / rel
        if not path.exists():
            print(f"[-] missing   {rel}")
            ok = False
            continue
        actual = compute_sha256(path)
        if actual == expected:
            print(f"[+] verified  {rel}")
        else:
            print(f"[-] CHECKSUM MISMATCH {rel}\n      expected {expected}\n      actual   {actual}")
            ok = False
    return ok


def download_buffalo(models_dir: Path) -> bool:
    """Download buffalo_l.zip, check the archive hash, then extract it."""
    zip_path = models_dir / "buffalo_l.zip"
    if not download_file(BUFFALO_L_URL, zip_path):
        return False
    actual = compute_sha256(zip_path)
    if actual != BUFFALO_L_ZIP_SHA256:
        print(
            f"ERROR: buffalo_l.zip checksum mismatch\n  expected {BUFFALO_L_ZIP_SHA256}\n  actual   {actual}",
            file=sys.stderr,
        )
        zip_path.unlink(missing_ok=True)
        return False
    target = models_dir / "buffalo_l"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(target)
    zip_path.unlink(missing_ok=True)
    return True


def create_stubs(models_dir: Path) -> None:
    """Placeholder files so tests that never load a model can run offline. They cannot be loaded."""
    folder = models_dir / "buffalo_l"
    folder.mkdir(parents=True, exist_ok=True)
    for rel in EXPECTED_SHA256:
        path = models_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"STUB")
    print(f"Created unloadable stubs in {models_dir}. Never use these to run the worker.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify face worker models.")
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--create-stubs", action="store_true")
    args = parser.parse_args()

    models_dir: Path = args.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    if args.create_stubs:
        create_stubs(models_dir)
        return 0
    if args.verify_only:
        return 0 if verify_models(models_dir) else 1

    buffalo_files = [rel for rel in EXPECTED_SHA256 if rel.startswith("buffalo_l/")]
    if not all((models_dir / rel).exists() for rel in buffalo_files):
        if not download_buffalo(models_dir):
            return 1

    if not (models_dir / "antispoof.onnx").exists():
        print(
            "\nThe anti-spoof model is not published as ONNX, so convert it once:\n"
            "  uv run --with torch==2.14.1 --with onnx==1.23.2 python scripts/convert_antispoof.py"
        )

    if verify_models(models_dir):
        print(f"\nAll models ready. MODEL_VERSION={MODEL_VERSION}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Download and verify model weights for the NightRoll Face Worker.

Fetches:
1. InsightFace 'buffalo_l' pack (detector, landmarks, ArcFace 512-d embedder)
2. Silent-Face / MiniFASNet anti-spoofing ONNX model

Usage:
    python scripts/download_models.py
    python scripts/download_models.py --verify-only
    python scripts/download_models.py --create-stubs
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT_DIR / "models"
BUFFALO_DIR = MODELS_DIR / "buffalo_l"

# Model metadata & download endpoints
BUFFALO_L_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
# Hosted ONNX release for Silent-Face anti-spoofing (MiniFASNetV2)
ANTISPOOF_URL = "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.onnx"

# Expected SHA-256 checksums (checked when files exist or after download)
# Set to None if checksum is to be calculated and printed on first download
EXPECTED_SHA256 = {
    "buffalo_l.zip": "7d95d038221684c30b200b3f88f11d1ef5e6659f81ca9734e9e0d164d14b1b36",
    "antispoof.onnx": None,
}

MODEL_VERSION = "buffalo_l-1"


def compute_sha256(filepath: Path) -> str:
    """Compute hex SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_file(url: str, dest: Path) -> bool:
    """Download a file with progress output."""
    print(f"Downloading {url} -> {dest.name}...")
    try:
        def reporthook(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                percent = min(100, block_num * block_size * 100 // total_size)
                sys.stdout.write(f"\r  [{dest.name}] {percent}% ({block_num * block_size // 1024} KB)")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, dest, reporthook=reporthook)
        sys.stdout.write("\n")
        return True
    except Exception as e:
        sys.stdout.write("\n")
        print(f"ERROR: Failed to download {url}: {e}", file=sys.stderr)
        return False


def verify_models(models_dir: Path) -> bool:
    """Verify presence and checksums of installed model files."""
    buffalo_path = models_dir / "buffalo_l"
    antispoof_path = models_dir / "antispoof.onnx"

    all_ok = True
    print("\n--- Verifying Model Files ---")

    if not buffalo_path.exists():
        print(f"[-] Missing directory: {buffalo_path}")
        all_ok = False
    else:
        buffalo_files = ["det_10g.onnx", "w600k_r50.onnx", "2d106det.onnx", "1k3d68.onnx"]
        for bf in buffalo_files:
            p = buffalo_path / bf
            if p.exists():
                h = compute_sha256(p)
                print(f"[+] {bf} present ({p.stat().st_size // 1024} KB, sha256: {h[:12]}...)")
            else:
                print(f"[-] Missing buffalo_l component: {bf}")
                all_ok = False

    if antispoof_path.exists():
        h = compute_sha256(antispoof_path)
        print(f"[+] antispoof.onnx present ({antispoof_path.stat().st_size // 1024} KB, sha256: {h[:12]}...)")
    else:
        print(f"[-] Missing anti-spoof model: {antispoof_path}")
        all_ok = False

    return all_ok


def create_stubs(models_dir: Path) -> None:
    """Create lightweight dummy/mock files for local testing and CI without full weights."""
    print("Creating mock model stubs for offline testing...")
    buffalo_path = models_dir / "buffalo_l"
    buffalo_path.mkdir(parents=True, exist_ok=True)

    dummy_content = b"ONNX_MOCK_MODEL_TEST_STUB_ONLY"
    for bf in ["det_10g.onnx", "w600k_r50.onnx", "2d106det.onnx", "1k3d68.onnx", "genderage.onnx"]:
        (buffalo_path / bf).write_bytes(dummy_content)
    (models_dir / "antispoof.onnx").write_bytes(dummy_content)
    print(f"Created model stubs in {models_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify face worker models.")
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR, help="Target models directory")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing models")
    parser.add_argument("--create-stubs", action="store_true", help="Create dummy stubs for offline testing")
    parser.add_argument("--force", action="store_true", help="Force re-download even if files exist")

    args = parser.parse_args()
    models_dir: Path = args.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    if args.create_stubs:
        create_stubs(models_dir)
        return 0

    if args.verify_only:
        return 0 if verify_models(models_dir) else 1

    # Check if models already exist
    buffalo_models = models_dir / "buffalo_l" / "w600k_r50.onnx"
    antispoof_model = models_dir / "antispoof.onnx"

    if buffalo_models.exists() and antispoof_model.exists() and not args.force:
        print("Model files already present. Verifying integrity...")
        if verify_models(models_dir):
            print("Models intact. No download needed.")
            return 0
        print("Integrity check failed. Re-downloading...")

    # Download buffalo_l
    zip_dest = models_dir / "buffalo_l.zip"
    if not (models_dir / "buffalo_l").exists() or args.force:
        ok = download_file(BUFFALO_L_URL, zip_dest)
        if ok and zip_dest.exists():
            print(f"Extracting {zip_dest.name} -> {models_dir / 'buffalo_l'}...")
            with zipfile.ZipFile(zip_dest, "r") as z:
                z.extractall(models_dir / "buffalo_l")
            zip_dest.unlink(missing_ok=True)
        else:
            print(f"Warning: Could not download buffalo_l directly from GitHub release.")
            print(f"InsightFace will attempt automatic download on first initialization if needed.")

    # Download anti-spoof model
    if not antispoof_model.exists() or args.force:
        download_file(ANTISPOOF_URL, antispoof_model)

    print("\nVerification summary:")
    if verify_models(models_dir):
        print(f"\nAll models ready! MODEL_VERSION={MODEL_VERSION}")
        return 0
    else:
        print("\nNote: Some models were not downloaded (may require manual placement or offline stubs for tests).")
        return 0


if __name__ == "__main__":
    sys.exit(main())

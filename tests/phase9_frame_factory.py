"""Makes face crops for the Phase 9 live tests. Runs under the face worker's own Python.

    cd face && .venv/bin/python ../tests/phase9_frame_factory.py <output_dir>

Writes JPEG crops of the two faces in InsightFace's sample photo:
  enroll_*.jpg   five crops of person A, for enrolment
  live_a_*.jpg   four slightly different crops of person A
  live_b_*.jpg   four crops of person B, a different person
and prints a JSON summary. Nothing here is committed; the crops live in the test's temporary folder.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

FACE_DIR = Path(__file__).resolve().parent.parent / "face"
sys.path.insert(0, str(FACE_DIR))

from worker.main import load_face_app  # noqa: E402

SAMPLE = FACE_DIR / ".venv/lib/python3.12/site-packages/insightface/data/images/t1.jpg"


def crop(img, face, margin=1.0, size=480, brightness=1.0, dx=0, dy=0):
    x1, y1, x2, y2 = face.bbox
    w, h = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy
    half = max(w, h) * (0.5 + margin / 2)
    xa, ya = int(max(0, cx - half)), int(max(0, cy - half))
    xb, yb = int(min(img.shape[1], cx + half)), int(min(img.shape[0], cy + half))
    out = cv2.resize(img[ya:yb, xa:xb], (size, size), interpolation=cv2.INTER_CUBIC)
    out = np.clip(out.astype(np.float32) * brightness, 0, 255).astype(np.uint8)
    return cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    app = load_face_app()
    img = cv2.imread(str(SAMPLE))
    faces = sorted(app.get(img), key=lambda f: f.bbox[0])
    person_a, person_b = faces[0], faces[1]

    enroll_variants = [
        dict(),
        dict(brightness=1.08),
        dict(dx=4),
        dict(dy=4, brightness=0.95),
        dict(margin=1.2),
    ]
    live_a_variants = [
        dict(brightness=1.03, dx=2),
        dict(dy=2),
        dict(margin=1.1, brightness=0.97),
        dict(dx=-3),
    ]
    summary = {"enroll": [], "live_a": [], "live_b": []}
    for name, variants, face in (
        ("enroll", enroll_variants, person_a),
        ("live_a", live_a_variants, person_a),
        ("live_b", live_a_variants, person_b),
    ):
        for i, params in enumerate(variants):
            path = out / f"{name}_{i}.jpg"
            path.write_bytes(crop(img, face, **params))
            summary[name].append(str(path))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

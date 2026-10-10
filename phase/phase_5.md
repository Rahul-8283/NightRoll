# Phase 5: Face Worker

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 0, 1 |
| **Unlocks** | Phases 6, 9 |
| **Lead** | Face |
| **Can run alongside** | Phases 2, 3, 4 |

## Goal

A separate internal service that takes face frames and answers two questions: what is this face's embedding, and is it a real face or a photo or screen. It stores frames briefly for disputes and deletes them on schedule. It knows nothing about attendance.

## Outcome

- The face worker runs on its own port and accepts requests only from the backend.
- It returns a 512-number embedding for an enrollment photo.
- It returns a match score and an anti-spoof score for a set of nightly frames.
- Frames are saved to the private `frames` bucket and removed after 24 hours.

## Scope

**In:** model loading, detection, alignment, embedding, matching, anti-spoof, frame storage, cleanup job, internal API.
**Out:** deciding a verdict (Phase 9), the on-device pre-check (Phase 7).

---

## Tasks

### 1. Service skeleton

```text
face/
├── worker/
│   ├── main.py            FastAPI app, lifespan loads models
│   ├── config.py
│   ├── auth.py            Service token check
│   ├── pipeline/
│   │   ├── detect.py      Detection and quality checks
│   │   ├── embed.py       Alignment and ArcFace embedding
│   │   ├── antispoof.py   Real-or-fake score
│   │   └── match.py       Cosine similarity
│   ├── storage.py         Supabase Storage and embedding access
│   ├── cleanup.py         Frame deletion job
│   └── schemas.py
├── models/                Model files (gitignored)
├── scripts/
│   └── download_models.py
├── pyproject.toml
├── .env.example
└── README.md
```

| # | Task |
|---|---|
| 1.1 | Pin `insightface`, `onnxruntime`, `opencv-python-headless`, `numpy`, `fastapi`, `uvicorn`, `supabase` |
| 1.2 | `download_models.py` fetches the models into `face/models/` and checks each file's SHA-256 against a list in the repo |
| 1.3 | Record the model name and version as `MODEL_VERSION`, returned with every embedding |

### 2. Model loading

| # | Task |
|---|---|
| 2.1 | Load InsightFace `buffalo_l` once at startup, on CPU |
| 2.2 | Load the anti-spoof model once at startup |
| 2.3 | Run one warm-up inference at startup so the first real request is not slow |
| 2.4 | `/health` reports ready only after both models are loaded |

### 3. Detection and quality

For each frame:

| Check | Rule | Failure code |
|---|---|---|
| Decodes as an image | JPEG, within size limit | `BAD_IMAGE` |
| Exactly one face | Zero or more than one fails | `NO_FACE`, `MULTIPLE_FACES` |
| Face large enough | Face box at least 112 pixels on its short side | `FACE_TOO_SMALL` |
| Sharp enough | Blur measure above a set floor | `TOO_BLURRY` |
| Lit well enough | Mean brightness inside a set range | `BAD_LIGHTING` |
| Facing the camera | Head turn within a set angle, for the frames used for matching | `BAD_POSE` |

The floors and ranges are settings with starting values. They are tuned in Phase 13.

### 4. Embedding

| # | Task |
|---|---|
| 4.1 | Align the face using the detector's landmarks |
| 4.2 | Compute the ArcFace embedding and normalise it to unit length |
| 4.3 | For enrollment, take 3 to 5 frames, embed each one that passes the quality checks, and average them into one embedding, then normalise again |
| 4.4 | Reject enrollment if fewer than 3 frames pass, or if the frames do not agree with each other closely enough to be one person |

### 5. Matching

| # | Task |
|---|---|
| 5.1 | Read the enrolled embedding for the given student from `face_embeddings` |
| 5.2 | Compute cosine similarity for each nightly frame that passes quality |
| 5.3 | Return the best similarity, the median, and how many frames were usable |

The worker returns numbers. It does not decide pass or fail.

### 6. Anti-spoof

| # | Task |
|---|---|
| 6.1 | Convert the Silent-Face anti-spoofing model to ONNX and add it to the model download list |
| 6.2 | Crop each frame the way the model expects and score it from 0 (fake) to 1 (real) |
| 6.3 | Return the per-frame scores and the median |
| 6.4 | If the model cannot be loaded, the worker reports `antispoof_available: false` in `/health`, and the backend treats liveness as failed rather than passed |

### 7. Frame storage

| # | Task |
|---|---|
| 7.1 | Check each frame's SHA-256 against the hash the backend passes in. A mismatch rejects the request with `FRAME_HASH_MISMATCH`. |
| 7.2 | Save frames to the `frames` bucket at `frames/{window_id}/{mark_id}/{index}.jpg` |
| 7.3 | Enrollment photos are not saved at all. Only the embedding is kept. |
| 7.4 | Return the storage folder path so the backend can record it on the mark |

### 8. Cleanup job

| # | Task |
|---|---|
| 8.1 | Every hour, delete frame folders older than `FRAME_RETENTION_HOURS` |
| 8.2 | Clear `frames_path` on the matching marks |
| 8.3 | Log the number of folders removed. Never log file contents. |
| 8.4 | Expose the last successful run time in `/health` |

### 9. Internal API

All routes require `Authorization: Bearer <FACE_WORKER_TOKEN>`. The worker is not reachable from outside the host.

| Method | Path | Input | Output |
|---|---|---|---|
| GET | `/health` | None | `{ready, model_version, antispoof_available, last_cleanup}` |
| POST | `/enroll` | `student_id`, 3 to 5 frames | `{model_version, frames_used}` and stores the embedding |
| POST | `/verify` | `student_id`, `window_id`, `mark_id`, frames, frame hashes | See below |
| DELETE | `/students/{student_id}/embedding` | None | Removes the embedding on consent withdrawal |

`/verify` response:

```json
{
  "usable_frames": 4,
  "best_similarity": 0.61,
  "median_similarity": 0.58,
  "antispoof_median": 0.97,
  "antispoof_scores": [0.98, 0.97, 0.96, 0.97],
  "frame_issues": [],
  "frames_path": "frames/<window_id>/<mark_id>/",
  "model_version": "buffalo_l-1"
}
```

### 10. Access limits

| # | Task |
|---|---|
| 10.1 | The worker reads and writes `face_embeddings` and the `frames` bucket only |
| 10.2 | It has no query for attendance, window or review tables |
| 10.3 | Embeddings are never returned by any route and never logged |

---

## Exit criteria

- [ ] The worker starts, loads both models, and `/health` reports ready.
- [ ] A request without the service token is refused.
- [ ] `/enroll` with five photos of a teammate stores one embedding in Supabase.
- [ ] `/verify` with fresh photos of the same teammate returns a clearly higher similarity than photos of a different teammate.
- [ ] `/verify` with a photo of a phone screen showing the teammate's face returns a clearly lower anti-spoof score than a live capture.
- [ ] A frame with no face, two faces, or heavy blur returns the matching issue code.
- [ ] Frames appear under the right path in the private bucket.
- [ ] The cleanup job removes a folder whose age is past the limit.
- [ ] One `/verify` call with four frames finishes within the latency noted in the Phase 0 spike.

## Deferred to Phase 13

- Accuracy measurement on a labelled set of same-person and different-person pairs.
- Anti-spoof measurement on printed photos and screen replays.
- Tuning of quality floors and the similarity range.

## Risks

| Risk | What to do |
|---|---|
| Anti-spoof model conversion fails | Use the on-device liveness challenge as the only liveness signal for the demo, and say so |
| Latency too high with every frame scored | Run anti-spoof and embedding on the best two frames only |
| Faces captured lying in bed are tilted or badly lit | The app guides the student to hold the phone upright and turn on a light (Phase 7) |
| Model licence terms | Check the licence of each model file before any use beyond the hackathon |

## Hand-off to Phase 6

Phase 6 needs `/enroll`. Phase 9 needs `/verify`.

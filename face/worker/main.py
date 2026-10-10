"""NightRoll Face Worker FastAPI Service."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status

from worker.auth import verify_service_token
from worker.cleanup import get_last_cleanup_time, run_frame_cleanup
from worker.config import settings
from worker.pipeline.antispoof import AntiSpoofClassifier, calculate_median_antispoof
from worker.pipeline.detect import evaluate_frame
from worker.pipeline.embed import aggregate_enrollment_embeddings, extract_unit_embedding
from worker.pipeline.match import evaluate_similarities
from worker.schemas import (
    EnrollmentResponse,
    FrameIssue,
    HeadPose,
    HealthResponse,
    VerifyResponse,
)
from worker.storage import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("face_worker")

# Global model state
face_app: Any | None = None
antispoof_classifier: AntiSpoofClassifier | None = None
worker_ready: bool = False
cleanup_task: asyncio.Task[None] | None = None


def load_face_app() -> Any:
    """Load InsightFace from the files `scripts/download_models.py` verified, and nothing else.

    InsightFace looks for `<root>/models/<name>`, so the root is the parent of FACE_MODEL_DIR. If the
    folder is missing we fail loudly instead of letting InsightFace download an unverified copy.
    """
    from insightface.app import FaceAnalysis

    model_dir = Path(settings.FACE_MODEL_DIR).resolve()
    if model_dir.name != "models":
        raise RuntimeError(f"FACE_MODEL_DIR must be a folder named 'models', got '{model_dir}'")
    if not (model_dir / settings.FACE_MODEL_NAME).is_dir():
        raise FileNotFoundError(
            f"{model_dir / settings.FACE_MODEL_NAME} is missing. Run: python scripts/download_models.py"
        )

    face_app = FaceAnalysis(
        name=settings.FACE_MODEL_NAME,
        root=str(model_dir.parent),
        providers=["CPUExecutionProvider"],
    )
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    return face_app


async def cleanup_loop() -> None:
    """Hourly background loop for frame retention cleanup."""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hour
            await run_frame_cleanup()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cleanup background loop: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager: load models, run warm-up inference, and manage retention scheduler."""
    global face_app, antispoof_classifier, worker_ready, cleanup_task

    logger.info("Initializing Face Worker models...")

    # 1. Load InsightFace FaceAnalysis on CPU
    try:
        face_app = load_face_app()
        logger.info(f"Loaded InsightFace model '{settings.FACE_MODEL_NAME}'")
    except Exception as e:
        logger.error(f"InsightFace did not load: {e}")
        face_app = None

    # 2. Load Anti-spoofing ONNX model
    antispoof_classifier = AntiSpoofClassifier(settings.ANTISPOOF_MODEL_PATH)

    # 3. Warm-up inference
    try:
        dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
        if face_app is not None:
            _ = face_app.get(dummy_img)
        if antispoof_classifier is not None and antispoof_classifier.is_available:
            _ = antispoof_classifier.score(dummy_img, [100, 100, 200, 200])
        logger.info("Model warm-up inference complete")
    except Exception as e:
        logger.warning(f"Warm-up inference warning: {e}")

    worker_ready = face_app is not None
    if not worker_ready:
        logger.error("Face model failed to load: /health will report ready=false")

    # 4. Start background retention cleanup
    cleanup_task = asyncio.create_task(cleanup_loop())

    yield

    # Shutdown
    if cleanup_task:
        cleanup_task.cancel()
    logger.info("Face Worker shut down cleanly")


app = FastAPI(
    title="NightRoll Face Worker",
    version="0.1.0",
    description="Internal face embedding extraction, anti-spoofing, and frame retention service",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, dependencies=[Depends(verify_service_token)])
async def health_check() -> HealthResponse:
    """Report readiness, model versions, anti-spoof availability, and last cleanup time."""
    antispoof_ok = antispoof_classifier.is_available if antispoof_classifier else False
    return HealthResponse(
        ready=worker_ready,
        model_version=settings.MODEL_VERSION,
        antispoof_available=antispoof_ok,
        last_cleanup=get_last_cleanup_time(),
    )


@app.post("/enroll", response_model=EnrollmentResponse, dependencies=[Depends(verify_service_token)])
async def enroll_student_face(
    student_id: Annotated[UUID, Form()],
    frames: Annotated[list[UploadFile], File()],
) -> EnrollmentResponse:
    """Process 3 to 5 enrollment frames, generate and store an aggregate 512-d ArcFace embedding.

    Enrollment photos are NEVER saved to disk or storage (Task 7.3).
    """
    if len(frames) < settings.ENROLL_MIN_VALID_FRAMES or len(frames) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Enrollment requires between {settings.ENROLL_MIN_VALID_FRAMES} and 5 frames, received {len(frames)}"
            ),
        )

    valid_embeddings: list[np.ndarray] = []
    issues_encountered: list[FrameIssue] = []

    for idx, upload in enumerate(frames):
        content = await upload.read()
        q_res = evaluate_frame(frame_index=idx, image_bytes=content, face_app=face_app, require_neutral_pose=True)

        if not q_res.valid:
            issues_encountered.extend(q_res.issues)
            continue

        try:
            emb = extract_unit_embedding(q_res.face)
            valid_embeddings.append(emb)
        except Exception as e:
            issues_encountered.append(FrameIssue(frame_index=idx, code="BAD_EMBEDDING", detail=str(e)))

    if len(valid_embeddings) < settings.ENROLL_MIN_VALID_FRAMES:
        reasons = [f"Frame {iss.frame_index}: {iss.code} ({iss.detail})" for iss in issues_encountered]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Fewer than {settings.ENROLL_MIN_VALID_FRAMES} frames passed quality checks. "
                f"Issues: {'; '.join(reasons)}"
            ),
        )

    # Validate cross-frame consistency and compute normalized average vector
    try:
        final_embedding, count_used = aggregate_enrollment_embeddings(valid_embeddings)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    # Persist directly into face_embeddings table
    saved = await storage.save_embedding(student_id, final_embedding, settings.MODEL_VERSION)
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist face embedding to database",
        )

    return EnrollmentResponse(
        model_version=settings.MODEL_VERSION,
        frames_used=count_used,
    )


@app.post("/verify", response_model=VerifyResponse, dependencies=[Depends(verify_service_token)])
async def verify_nightly_frames(
    student_id: Annotated[UUID, Form()],
    window_id: Annotated[UUID, Form()],
    mark_id: Annotated[UUID, Form()],
    frame_hashes: Annotated[str, Form(description="JSON-encoded list of expected frame SHA-256 hex hashes")],
    frames: Annotated[list[UploadFile], File()],
) -> VerifyResponse:
    """Score nightly frames for cosine similarity, anti-spoofing, and head pose.

    1. Validates frame SHA-256 hashes against backend hashes (FRAME_HASH_MISMATCH).
    2. Retrieves student's enrolled embedding from face_embeddings.
    3. Runs quality evaluation and head pose extraction.
    4. Runs anti-spoof inference on each usable frame.
    5. Computes best and median cosine similarity.
    6. Stores frames in the private frames bucket for 24-hour audit retention.
    """
    try:
        expected_hashes: list[str] = json.loads(frame_hashes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="frame_hashes must be a valid JSON array"
        ) from e

    if len(frames) != len(expected_hashes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Frame count ({len(frames)}) does not match hash count ({len(expected_hashes)})",
        )

    # 1. Fetch enrolled embedding
    enrolled_embedding = await storage.get_embedding(student_id)
    if enrolled_embedding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No enrolled face embedding found for student {student_id}",
        )

    raw_frame_bytes: list[tuple[int, bytes]] = []
    usable_embeddings: list[np.ndarray] = []
    antispoof_scores: list[float] = []
    head_poses: list[HeadPose] = []
    frame_issues: list[FrameIssue] = []

    # 2. Process frames
    for idx, (upload, expected_hash) in enumerate(zip(frames, expected_hashes, strict=True)):
        content = await upload.read()

        # SHA-256 check
        if not storage.verify_frame_hash(content, expected_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"FRAME_HASH_MISMATCH: Frame {idx} SHA-256 does not match expected hash",
            )

        raw_frame_bytes.append((idx, content))

        # Quality & Detection (do not reject pose outright during verify, capture pose for liveness challenge)
        q_res = evaluate_frame(frame_index=idx, image_bytes=content, face_app=face_app, require_neutral_pose=False)
        head_poses.append(q_res.head_pose)

        if not q_res.valid:
            frame_issues.extend(q_res.issues)
            continue

        # Embedding extraction
        try:
            emb = extract_unit_embedding(q_res.face)
            usable_embeddings.append(emb)
        except Exception as e:
            frame_issues.append(FrameIssue(frame_index=idx, code="BAD_EMBEDDING", detail=str(e)))
            continue

        # Anti-spoof inference
        if antispoof_classifier is not None and antispoof_classifier.is_available:
            bbox = q_res.face.bbox if hasattr(q_res.face, "bbox") else [0, 0, 100, 100]
            as_score = antispoof_classifier.score(q_res.img, bbox)
            antispoof_scores.append(round(as_score, 4))
        else:
            antispoof_scores.append(0.0)

    # 3. Match against enrolled template
    best_sim, median_sim, usable_count = evaluate_similarities(enrolled_embedding, usable_embeddings)
    median_antispoof = round(calculate_median_antispoof(antispoof_scores), 4)

    # 4. Save nightly dispute frames to private storage bucket
    frames_path = await storage.save_verified_frames(window_id, mark_id, raw_frame_bytes)

    return VerifyResponse(
        usable_frames=usable_count,
        best_similarity=best_sim,
        median_similarity=median_sim,
        antispoof_median=median_antispoof,
        antispoof_scores=antispoof_scores,
        head_poses=head_poses,
        frame_issues=frame_issues,
        frames_path=frames_path,
        model_version=settings.MODEL_VERSION,
    )


@app.delete("/students/{student_id}/embedding", dependencies=[Depends(verify_service_token)])
async def delete_student_embedding(student_id: UUID) -> dict[str, Any]:
    """Remove student face embedding from database upon consent withdrawal."""
    deleted = await storage.delete_embedding(student_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete embedding for student {student_id}",
        )
    return {"deleted": True, "student_id": str(student_id)}

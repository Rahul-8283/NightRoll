"""ArcFace face alignment, embedding extraction, and enrollment aggregation."""

from __future__ import annotations

import numpy as np

from worker.config import settings


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """Normalize a 512-d embedding to unit length (L2 norm)."""
    norm = np.linalg.norm(embedding)
    if norm == 0 or np.isnan(norm):
        raise ValueError("Cannot normalize a zero or NaN embedding")
    return embedding / norm


def extract_unit_embedding(face: any) -> np.ndarray:
    """Extract normalized 512-d embedding vector from an InsightFace face object."""
    if hasattr(face, "embedding") and face.embedding is not None:
        emb = np.array(face.embedding, dtype=np.float32)
    elif isinstance(face, dict) and "embedding" in face:
        emb = np.array(face["embedding"], dtype=np.float32)
    else:
        raise ValueError("Face object does not contain an embedding")

    if emb.shape[0] != 512:
        raise ValueError(f"Expected 512-dimension embedding, got {emb.shape[0]}")

    return normalize_embedding(emb)


def aggregate_enrollment_embeddings(embeddings: list[np.ndarray]) -> tuple[np.ndarray, int]:
    """Validate pairwise agreement and average multi-frame embeddings for enrollment.

    Rules:
    - At least ENROLL_MIN_VALID_FRAMES (3) must be provided.
    - Pairwise cosine similarity must meet or exceed ENROLL_MIN_AGREEMENT (0.55).
    - Resulting average embedding is normalized to unit length.
    """
    count = len(embeddings)
    if count < settings.ENROLL_MIN_VALID_FRAMES:
        raise ValueError(f"Enrollment requires at least {settings.ENROLL_MIN_VALID_FRAMES} valid frames, got {count}")

    # Check pairwise cosine agreement
    for i in range(count):
        for j in range(i + 1, count):
            similarity = float(np.dot(embeddings[i], embeddings[j]))
            if similarity < settings.ENROLL_MIN_AGREEMENT:
                raise ValueError(
                    f"Enrollment frames do not agree closely enough to be the same person "
                    f"(similarity between frame {i + 1} and {j + 1} is {similarity:.3f} "
                    f"< {settings.ENROLL_MIN_AGREEMENT})"
                )

    # Average embeddings and re-normalize to unit length
    mean_embedding = np.mean(embeddings, axis=0)
    final_embedding = normalize_embedding(mean_embedding)

    return final_embedding, count

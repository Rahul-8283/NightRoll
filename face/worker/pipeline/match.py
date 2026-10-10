"""Cosine similarity matching between nightly frames and enrolled face embeddings."""

from __future__ import annotations

import numpy as np


def compute_similarity(enrolled: np.ndarray, frame_embedding: np.ndarray) -> float:
    """Compute cosine similarity between two unit-normalized embeddings.

    Since both vectors are normalized to L2 norm == 1.0, cosine similarity is their dot product.
    """
    sim = float(np.dot(enrolled, frame_embedding))
    return float(np.clip(sim, -1.0, 1.0))


def evaluate_similarities(
    enrolled_embedding: np.ndarray,
    frame_embeddings: list[np.ndarray],
) -> tuple[float, float, int]:
    """Compute matching metrics across usable frames.

    Returns:
        (best_similarity, median_similarity, usable_frames_count)
    """
    if not frame_embeddings:
        return 0.0, 0.0, 0

    scores = [compute_similarity(enrolled_embedding, fe) for fe in frame_embeddings]
    best_sim = float(np.max(scores))
    median_sim = float(np.median(scores))

    return round(best_sim, 4), round(median_sim, 4), len(scores)
